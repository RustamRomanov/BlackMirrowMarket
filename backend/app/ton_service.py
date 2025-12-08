import os
import uuid
import ssl
import aiohttp
import re
from decimal import Decimal
from typing import Optional, Tuple
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from pytoniq.liteclient import LiteBalancer
from pytoniq.contract.wallets.wallet import WalletV4R2, Address

from app import models


class TonService:
    """
    Сервис для работы с TON mainnet.
    Делает отправку транзакций, ведет учет в БД и защищает от двойных списаний через idempotency_key.
    """

    def __init__(self):
        self.api_key = os.getenv("TONAPI_KEY")
        self.seed_phrase = os.getenv("TON_WALLET_SEED")
        self.wallet_address = os.getenv("TON_WALLET_ADDRESS")
        self._client = None
        self._wallet = None

        # Делаем переменные опциональными, чтобы приложение могло запуститься без них
        # (TON функции просто не будут работать)
        if not self.api_key:
            print("⚠️ Warning: TONAPI_KEY is not set. TON API features will be disabled.")
        if not self.seed_phrase:
            print("⚠️ Warning: TON_WALLET_SEED is not set. TON wallet features will be disabled.")
        if not self.wallet_address:
            print("⚠️ Warning: TON_WALLET_ADDRESS is not set. TON deposit checking will be disabled.")

    async def _ensure_client(self):
        """Инициализирует клиент и кошелек только при необходимости."""
        if self._client is None:
            # Публичный mainnet конфиг. Для продакшена можно поменять на собственный endpoint.
            self._client = LiteBalancer.from_mainnet_config()
            # Начинаем подключение (неблокирующее)
            await self._client.start_up()
        if self._wallet is None:
            # Кошелек V4R2 из сид-фразы. Ключи остаются в памяти процесса.
            # Сигнатура: from_mnemonic(provider, mnemonics, wc=0, wallet_id=None, version="v3r2")
            self._wallet = await WalletV4R2.from_mnemonic(
                self._client, self.seed_phrase.split()
            )

    async def get_wallet_balance(self) -> int:
        """Возвращает баланс сервисного кошелька в нано-TON через tonapi.io."""
        try:
            # Создаем SSL контекст без проверки сертификатов (для разработки на macOS)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Используем SSL контекст в connector
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=connector
            ) as session:
                url = f"https://tonapi.io/v2/accounts/{self.wallet_address}"
                headers = {"Authorization": f"Bearer {self.api_key}"}
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise Exception(f"TON API error: {resp.status} - {text}")
                    data = await resp.json()
                    balance = data.get("balance", 0)
                    # tonapi возвращает баланс в нано-TON как строку
                    return int(balance) if balance else 0
        except Exception as e:
            raise Exception(f"Failed to get balance from tonapi: {e}")

    async def _send_raw(self, to_address: str, amount_nano: int) -> str:
        """
        Отправка TON. Возвращает tx_hash.
        Использует таймауты, чтобы не зависать.
        """
        import asyncio
        await self._ensure_client()
        destination = Address(to_address)
        try:
            # Таймаут 30 секунд на всю операцию
            seqno = await asyncio.wait_for(self._wallet.get_seqno(), timeout=10.0)
            msg = await asyncio.wait_for(
                self._wallet.transfer(destination=destination, amount=amount_nano),
                timeout=10.0
            )
            result = await asyncio.wait_for(
                self._wallet.raw_transfer([msg], seqno_from_get_meth=True),
                timeout=10.0
            )
            tx_hash = getattr(result, "hash", None)
            return tx_hash.hex() if tx_hash else "unknown"
        except asyncio.TimeoutError:
            raise Exception("TON transaction timeout")

    async def create_withdrawal(
        self,
        db: Session,
        telegram_id: int,
        to_address: str,
        amount_nano: Decimal,
        idempotency_key: Optional[str] = None,
    ) -> Tuple[models.TonTransaction, bool]:
        """
        Создает запись о выводе и пытается отправить транзакцию.
        Возвращает (tx_record, created_new: bool).
        """
        if amount_nano <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")

        user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
        if not balance:
            raise HTTPException(status_code=404, detail="Balance not found")

        key = idempotency_key or str(uuid.uuid4())

        existing = (
            db.query(models.TonTransaction)
            .filter(models.TonTransaction.idempotency_key == key)
            .first()
        )
        if existing:
            return existing, False

        if balance.ton_active_balance < amount_nano:
            raise HTTPException(status_code=400, detail="Insufficient funds")

        tx = models.TonTransaction(
            user_id=user.id,
            to_address=to_address,
            amount_nano=amount_nano,
            status="pending",
            idempotency_key=key,
        )

        # Резервируем средства
        balance.ton_active_balance -= amount_nano
        db.add(tx)
        db.commit()
        db.refresh(tx)

        try:
            tx_hash = await self._send_raw(to_address, int(amount_nano))
            tx.tx_hash = tx_hash
            tx.status = "pending"
            db.commit()
            db.refresh(tx)
        except Exception as exc:
            # Возврат средств при неуспехе
            tx.status = "failed"
            tx.error_message = str(exc)
            balance.ton_active_balance += amount_nano
            db.commit()
            db.refresh(tx)
            raise HTTPException(status_code=500, detail=f"TON send failed: {exc}")

        return tx, True

    async def send_from_service_wallet(
        self,
        db: Session,
        to_address: str,
        amount_nano: Decimal,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> models.TonTransaction:
        """
        Прямой вывод с сервисного кошелька на любой адрес.
        Используется администратором для вывода средств.
        Не требует user_id - это прямой вывод с кошелька приложения.
        """
        if amount_nano <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")

        # Проверяем баланс сервисного кошелька
        try:
            balance_nano = await self.get_wallet_balance()
            if balance_nano < int(amount_nano):
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient funds. Balance: {balance_nano / 10**9:.4f} TON, Requested: {amount_nano / 10**9:.4f} TON"
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to check balance: {e}")

        key = idempotency_key or f"admin-{uuid.uuid4()}"

        # Проверяем идемпотентность
        existing = (
            db.query(models.TonTransaction)
            .filter(models.TonTransaction.idempotency_key == key)
            .first()
        )
        if existing:
            return existing

        # Создаем транзакцию без user_id (админский вывод)
        tx = models.TonTransaction(
            user_id=None,  # Админский вывод
            to_address=to_address,
            amount_nano=amount_nano,
            status="pending",
            idempotency_key=key,
            notes=notes,
        )

        db.add(tx)
        db.commit()
        db.refresh(tx)

        try:
            # Отправляем транзакцию
            tx_hash = await self._send_raw(to_address, int(amount_nano))
            tx.tx_hash = tx_hash
            tx.status = "pending"
            db.commit()
            db.refresh(tx)
        except Exception as exc:
            # При ошибке помечаем как failed
            tx.status = "failed"
            tx.error_message = str(exc)
            db.commit()
            db.refresh(tx)
            raise HTTPException(status_code=500, detail=f"TON send failed: {exc}")

        return tx

    async def check_transaction_status(self, tx_hash: str) -> str:
        """
        Проверяет статус транзакции через tonapi.io.
        Возвращает: 'completed', 'pending', или 'failed'
        """
        if not tx_hash or tx_hash == "unknown":
            return "pending"
        
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=connector
            ) as session:
                url = f"https://tonapi.io/v2/blockchain/transactions/{tx_hash}"
                headers = {"Authorization": f"Bearer {self.api_key}"}
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Если транзакция найдена - она completed
                        return "completed"
                    elif resp.status == 404:
                        # Транзакция еще не найдена в блокчейне
                        return "pending"
                    else:
                        return "pending"
        except Exception:
            # При ошибке считаем pending
            return "pending"

    async def check_incoming_deposits(self, db: Session):
        """
        Проверяет входящие транзакции на сервисный кошелек и автоматически зачисляет на балансы пользователей.
        Ищет Telegram ID в комментарии транзакции.
        """
        # Проверяем, что необходимые переменные установлены
        if not self.api_key or not self.wallet_address:
            return  # Пропускаем, если не настроено
        
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=connector
            ) as session:
                # Получаем последние транзакции на сервисный кошелек
                url = f"https://tonapi.io/v2/accounts/{self.wallet_address}/transactions"
                headers = {"Authorization": f"Bearer {self.api_key}"}
                params = {"limit": 50}
                
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        # Не спамим логи, если это обычная ошибка (404 может быть если нет транзакций)
                        if resp.status == 404:
                            # 404 может означать, что адрес не найден или нет транзакций - это нормально
                            return
                        print(f"TON API error getting transactions: {resp.status} - {text}")
                        return
                    
                    data = await resp.json()
                    transactions = data.get("transactions", [])
                    
                    for tx in transactions:
                        tx_hash = tx.get("hash")
                        if not tx_hash:
                            continue
                        
                        # Проверяем, обрабатывали ли мы уже эту транзакцию
                        existing = db.query(models.Deposit).filter(
                            models.Deposit.tx_hash == tx_hash
                        ).first()
                        if existing:
                            continue
                        
                        # Проверяем входящие сообщения
                        in_msg = tx.get("in_msg")
                        if not in_msg:
                            continue
                        
                        # Получаем адрес получателя (должен быть наш кошелек)
                        destination_addr = in_msg.get("destination", {})
                        if isinstance(destination_addr, dict):
                            destination = destination_addr.get("address", "")
                        else:
                            destination = str(destination_addr)
                        
                        # Нормализуем адрес для сравнения
                        if destination and destination != self.wallet_address:
                            # Проверяем, может быть это другой формат адреса
                            continue
                        
                        # Получаем сумму
                        value = int(in_msg.get("value", 0))
                        if value <= 0:
                            continue
                        
                        # Получаем отправителя
                        source_addr = in_msg.get("source", {})
                        if isinstance(source_addr, dict):
                            source = source_addr.get("address", "")
                        else:
                            source = str(source_addr) if source_addr else ""
                        
                        # Пытаемся извлечь Telegram ID из комментария
                        telegram_id = None
                        # Комментарий может быть в разных полях
                        msg_text = in_msg.get("msg_data", {}).get("text", "")
                        if not msg_text:
                            msg_text = in_msg.get("message", "")
                        if not msg_text:
                            msg_text = in_msg.get("decoded_body", {}).get("text", "")
                        
                        if msg_text:
                            msg_text_str = str(msg_text).strip()
                            
                            # Ищем только Telegram ID в комментарии (формат: "123456789" или "tg:123456789")
                            match_id = re.search(r'(?:tg:)?(\d{8,12})', msg_text_str)
                            if match_id:
                                telegram_id = match_id.group(1)
                        
                        # Создаем запись о депозите
                        deposit = models.Deposit(
                            tx_hash=tx_hash,
                            from_address=source,
                            amount_nano=value,
                            telegram_id_from_comment=telegram_id,
                            status="pending"
                        )
                        db.add(deposit)
                        db.commit()
                        
                        # Если нашли Telegram ID, зачисляем на баланс
                        if telegram_id:
                            try:
                                user = db.query(models.User).filter(
                                    models.User.telegram_id == int(telegram_id)
                                ).first()
                                
                                if user:
                                    balance = db.query(models.UserBalance).filter(
                                        models.UserBalance.user_id == user.id
                                    ).first()
                                    
                                    if not balance:
                                        balance = models.UserBalance(
                                            user_id=user.id,
                                            ton_active_balance=value,
                                            last_fiat_rate=Decimal("250"),
                                            fiat_currency="RUB"
                                        )
                                        db.add(balance)
                                    else:
                                        balance.ton_active_balance += value
                                    
                                    deposit.user_id = user.id
                                    deposit.status = "processed"
                                    deposit.processed_at = datetime.utcnow()
                                    db.commit()
                                    
                                    print(f"✅ Автоматически зачислено {value / 10**9:.4f} TON пользователю {telegram_id}")
                            except (ValueError, Exception) as e:
                                print(f"⚠️ Ошибка обработки депозита {tx_hash}: {e}")
                                deposit.status = "failed"
                                db.commit()
        except Exception as e:
            print(f"Error checking deposits: {e}")
            import traceback
            traceback.print_exc()

    async def update_pending_transactions(self, db: Session):
        """
        Обновляет статусы всех pending транзакций через tonapi.
        Вызывается периодически (например, каждые 30 секунд).
        """
        pending_txs = (
            db.query(models.TonTransaction)
            .filter(models.TonTransaction.status == "pending")
            .filter(models.TonTransaction.tx_hash.isnot(None))
            .all()
        )
        
        for tx in pending_txs:
            try:
                new_status = await self.check_transaction_status(tx.tx_hash)
                if new_status == "completed" and tx.status != "completed":
                    tx.status = "completed"
                    db.commit()
                elif new_status == "failed" and tx.status != "failed":
                    tx.status = "failed"
                    # Возвращаем средства пользователю при ошибке
                    user = db.query(models.User).filter(models.User.id == tx.user_id).first()
                    if user:
                        balance = db.query(models.UserBalance).filter(
                            models.UserBalance.user_id == user.id
                        ).first()
                        if balance:
                            balance.ton_active_balance += tx.amount_nano
                    db.commit()
            except Exception as e:
                # Логируем ошибку, но продолжаем обработку других транзакций
                print(f"Error updating tx {tx.id}: {e}")


ton_service_singleton: Optional[TonService] = None


def get_ton_service() -> Optional[TonService]:
    """Получает экземпляр TON сервиса. Возвращает None, если не настроен."""
    global ton_service_singleton
    if ton_service_singleton is None:
        try:
            ton_service_singleton = TonService()
        except RuntimeError:
            # Если переменные не установлены, возвращаем None
            return None
    return ton_service_singleton

