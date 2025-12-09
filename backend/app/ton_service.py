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
from pytoniq import Address as PytoniqAddress

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
        Использует прямой запрос к блокчейну через pytoniq вместо TON API.
        """
        import sys
        
        # Проверяем, что wallet_address установлен
        if not self.wallet_address:
            print("⚠️ TON_WALLET_ADDRESS не настроен", file=sys.stderr, flush=True)
            return
        
        # Нормализуем адрес
        normalized_address = self.wallet_address.strip()
        print(f"🔍 Проверка депозитов для кошелька: {normalized_address[:20]}...", file=sys.stderr, flush=True)
        
        try:
            # Создаем адрес объект
            wallet_addr = PytoniqAddress(normalized_address)
            print(f"✅ Адрес валиден: {wallet_addr.to_str(is_user_friendly=True)[:30]}...", file=sys.stderr, flush=True)
            
            # Подключаемся к блокчейну напрямую
            print("🌐 Подключение к TON блокчейну...", file=sys.stderr, flush=True)
            client = LiteBalancer.from_mainnet_config()
            
            # Подключаемся с таймаутом
            import asyncio
            try:
                await asyncio.wait_for(client.start_up(), timeout=10.0)
                print("✅ Подключено к блокчейну", file=sys.stderr, flush=True)
            except asyncio.TimeoutError:
                print("❌ Таймаут подключения к блокчейну (10 сек)", file=sys.stderr, flush=True)
                await client.close_all()
                return
            except Exception as e:
                print(f"❌ Ошибка подключения к блокчейну: {e}", file=sys.stderr, flush=True)
                try:
                    await client.close_all()
                except:
                    pass
                return
            
            # Получаем транзакции напрямую из блокчейна
            print("📡 Получение транзакций из блокчейна...", file=sys.stderr, flush=True)
            try:
                transactions = await asyncio.wait_for(
                    client.get_transactions(wallet_addr, count=50),
                    timeout=15.0
                )
                print(f"📊 Найдено транзакций: {len(transactions)}", file=sys.stderr, flush=True)
            except asyncio.TimeoutError:
                print("❌ Таймаут получения транзакций (15 сек)", file=sys.stderr, flush=True)
                await client.close_all()
                return
            except Exception as e:
                print(f"❌ Ошибка получения транзакций: {e}", file=sys.stderr, flush=True)
                import traceback
                traceback.print_exc()
                await client.close_all()
                return
            
            if len(transactions) == 0:
                print("ℹ️ Новых транзакций не найдено", file=sys.stderr, flush=True)
                await client.close_all()
                return
            
            # Обрабатываем транзакции
            for tx in transactions:
                # Получаем хеш транзакции
                tx_hash = tx.hash.hex() if hasattr(tx, 'hash') and hasattr(tx.hash, 'hex') else (str(tx.hash) if hasattr(tx, 'hash') else None)
                if not tx_hash:
                    # Пробуем другой способ получения хеша
                    if hasattr(tx, 'lt') and hasattr(tx, 'account'):
                        tx_hash = f"{tx.account.address.to_str()}_{tx.lt}"
                    else:
                        continue
                
                # Проверяем, обрабатывали ли мы уже эту транзакцию
                existing = db.query(models.Deposit).filter(
                    models.Deposit.tx_hash == tx_hash
                ).first()
                if existing:
                    continue
                
                # Получаем входящие сообщения
                in_msg = None
                value = 0
                source = ""
                
                # В pytoniq транзакция имеет структуру Transaction
                if hasattr(tx, 'in_msg') and tx.in_msg:
                    in_msg = tx.in_msg
                    # Получаем сумму из сообщения
                    if hasattr(in_msg, 'value'):
                        value = int(in_msg.value)
                    # Получаем отправителя
                    if hasattr(in_msg, 'source'):
                        source_addr = in_msg.source
                        if hasattr(source_addr, 'to_str'):
                            source = source_addr.to_str(is_user_friendly=False)
                        else:
                            source = str(source_addr)
                
                if value <= 0:
                    continue
                
                # Проверяем, что транзакция на наш кошелек
                if hasattr(tx, 'account') and hasattr(tx.account, 'address'):
                    tx_account_addr = tx.account.address.to_str(is_user_friendly=False)
                    wallet_addr_str = wallet_addr.to_str(is_user_friendly=False)
                    if tx_account_addr != wallet_addr_str:
                        continue
                
                # Пытаемся извлечь Telegram ID из комментария
                telegram_id = None
                msg_text_str = ""
                
                if in_msg and hasattr(in_msg, 'body'):
                    # Пробуем декодировать тело сообщения
                    try:
                        body = in_msg.body
                        # Пробуем получить текст из body (это Cell в pytoniq)
                        if hasattr(body, 'to_boc'):
                            boc_bytes = body.to_boc()
                            # Пробуем декодировать как текст
                            try:
                                # Пропускаем первые 32 бита (op code для text message)
                                if len(boc_bytes) > 4:
                                    text_bytes = boc_bytes[4:]
                                    msg_text_str = text_bytes.decode('utf-8', errors='ignore').strip()
                            except:
                                # Если не получилось, пробуем весь BOC
                                try:
                                    msg_text_str = boc_bytes.decode('utf-8', errors='ignore').strip()
                                except:
                                    msg_text_str = str(boc_bytes)[:200]
                    except Exception as e:
                        print(f"⚠️ Ошибка декодирования сообщения: {e}", file=sys.stderr, flush=True)
                
                if msg_text_str:
                    msg_text_str = str(msg_text_str).strip()
                    if msg_text_str:
                        print(f"📝 Комментарий транзакции {tx_hash[:20]}...: {msg_text_str[:100]}", file=sys.stderr, flush=True)
                        
                        # Ищем Telegram ID в комментарии
                        match_id = re.search(r'(?:tg:)?(\d{8,12})', msg_text_str)
                        if match_id:
                            telegram_id = match_id.group(1)
                            print(f"✅ Найден Telegram ID в комментарии: {telegram_id}", file=sys.stderr, flush=True)
                        else:
                            print(f"⚠️ Telegram ID не найден в комментарии: {msg_text_str[:50]}", file=sys.stderr, flush=True)
                
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
                print(f"💾 Создана запись о депозите: {tx_hash[:20]}..., сумма: {value / 10**9:.4f} TON, Telegram ID: {telegram_id or 'не указан'}", file=sys.stderr, flush=True)
                
                # Если нашли Telegram ID, зачисляем на баланс
                if telegram_id:
                    print(f"🔄 Попытка зачисления депозита для Telegram ID: {telegram_id}", file=sys.stderr, flush=True)
                    try:
                        user = db.query(models.User).filter(
                            models.User.telegram_id == int(telegram_id)
                        ).first()
                        
                        if user:
                            print(f"👤 Пользователь найден: ID={user.id}, Telegram ID={user.telegram_id}", file=sys.stderr, flush=True)
                            balance = db.query(models.UserBalance).filter(
                                models.UserBalance.user_id == user.id
                            ).first()
                            
                            if not balance:
                                print(f"💰 Создание нового баланса для пользователя {user.id}", file=sys.stderr, flush=True)
                                balance = models.UserBalance(
                                    user_id=user.id,
                                    ton_active_balance=value,
                                    last_fiat_rate=Decimal("250"),
                                    fiat_currency="RUB"
                                )
                                db.add(balance)
                            else:
                                old_balance = float(balance.ton_active_balance) / 10**9
                                balance.ton_active_balance += value
                                new_balance = float(balance.ton_active_balance) / 10**9
                                print(f"💰 Обновление баланса: {old_balance:.4f} → {new_balance:.4f} TON", file=sys.stderr, flush=True)
                            
                            deposit.user_id = user.id
                            deposit.status = "processed"
                            deposit.processed_at = datetime.utcnow()
                            db.commit()
                            
                            print(f"✅ Автоматически зачислено {value / 10**9:.4f} TON пользователю {telegram_id} (ID: {user.id})", file=sys.stderr, flush=True)
                        else:
                            print(f"⚠️ Пользователь с Telegram ID {telegram_id} не найден в базе данных", file=sys.stderr, flush=True)
                    except (ValueError, Exception) as e:
                        print(f"⚠️ Ошибка обработки депозита {tx_hash}: {e}", file=sys.stderr, flush=True)
                        import traceback
                        traceback.print_exc()
                        deposit.status = "failed"
                        db.commit()
                else:
                    print(f"⚠️ Депозит {tx_hash[:20]}... без Telegram ID в комментарии, требуется ручная обработка", file=sys.stderr, flush=True)
            
            print(f"✅ Обработано транзакций: {len(transactions)}", file=sys.stderr, flush=True)
            await client.close_all()
            
        except Exception as e:
            import sys, traceback
            print(f"❌ Ошибка при проверке депозитов через блокчейн: {e}", file=sys.stderr, flush=True)
            traceback.print_exc()
            try:
                if 'client' in locals():
                    await client.close_all()
            except:
                pass
        except Exception as e:
            import sys
            print(f"❌ Error checking deposits: {e}", file=sys.stderr, flush=True)
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
            # Проверяем, что хотя бы api_key и wallet_address установлены для проверки депозитов
            if not ton_service_singleton.api_key or not ton_service_singleton.wallet_address:
                import sys
                print("⚠️ TON сервис создан, но api_key или wallet_address не установлены. Проверка депозитов будет пропущена.", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"⚠️ Ошибка создания TON сервиса: {e}")
            return None
    return ton_service_singleton

