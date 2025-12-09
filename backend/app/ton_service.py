import os
import sys
import uuid
import ssl
import asyncio
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
        if not self.seed_phrase:
            raise Exception("TON_WALLET_SEED is not configured. Please set TON_WALLET_SEED environment variable with your 24-word mnemonic phrase.")
        
        # Очищаем мнемонику от лишних символов и пробелов
        cleaned_seed = self.seed_phrase.strip()
        # Убираем кавычки, если они есть
        if cleaned_seed.startswith('"') and cleaned_seed.endswith('"'):
            cleaned_seed = cleaned_seed[1:-1].strip()
        if cleaned_seed.startswith("'") and cleaned_seed.endswith("'"):
            cleaned_seed = cleaned_seed[1:-1].strip()
        
        # Разбиваем на слова, убирая множественные пробелы
        seed_words = [w.strip() for w in cleaned_seed.split() if w.strip()]
        
        # Проверяем на склеенные слова (слишком длинные слова могут быть несколькими словами)
        # BIP39 слова обычно 3-8 символов, если слово длиннее 10 - возможно это склеенные слова
        fixed_words = []
        for word in seed_words:
            if len(word) > 10:
                # Попытка разделить длинное слово (но это сложно без словаря)
                # Пока просто предупреждаем
                print(f"⚠️ Подозрительно длинное слово в мнемонике: {word[:20]}... (длина: {len(word)})", file=sys.stderr, flush=True)
                fixed_words.append(word)
            else:
                fixed_words.append(word)
        
        seed_words = fixed_words
        
        # Детальная диагностика
        word_count = len(seed_words)
        if word_count != 24:
            # Показываем первые и последние слова для диагностики (без раскрытия всей мнемоники)
            preview = f"{' '.join(seed_words[:3])} ... {''.join(seed_words[-3:])}" if word_count > 6 else ' '.join(seed_words)
            raise Exception(
                f"Invalid mnemonic format. Expected 24 words, got {word_count}. "
                f"Please check TON_WALLET_SEED environment variable. "
                f"Make sure it contains exactly 24 words separated by single spaces. "
                f"Preview (first 3 and last 3 words): {preview}"
            )
        
        # Проверяем, что слова не пустые
        if any(not word for word in seed_words):
            raise Exception(
                "Invalid mnemonic: contains empty words. "
                "Please check TON_WALLET_SEED - there might be multiple spaces or invalid characters."
            )
        
        if self._client is None:
            # Публичный mainnet конфиг. Для продакшена можно поменять на собственный endpoint.
            self._client = LiteBalancer.from_mainnet_config()
            # Начинаем подключение (неблокирующее)
            try:
                await asyncio.wait_for(self._client.start_up(), timeout=15.0)
            except asyncio.TimeoutError:
                raise Exception("Timeout connecting to TON blockchain. Please check your internet connection.")
            except Exception as e:
                raise Exception(f"Failed to connect to TON blockchain: {str(e)}")
        
        if self._wallet is None:
            # Кошелек V4R2 из сид-фразы. Ключи остаются в памяти процесса.
            # Сигнатура: from_mnemonic(provider, mnemonics, wc=0, wallet_id=None, version="v3r2")
            try:
                # Пробуем сначала V4R2
                self._wallet = await asyncio.wait_for(
                    WalletV4R2.from_mnemonic(self._client, seed_words),
                    timeout=10.0
                )
                
                # Проверяем, что адрес кошелька соответствует TON_WALLET_ADDRESS
                if self.wallet_address:
                    wallet_addr = await self._wallet.get_address()
                    wallet_addr_str = str(wallet_addr)
                    expected_addr = self.wallet_address.strip()
                    
                    # Нормализуем адреса для сравнения
                    try:
                        wallet_addr_normalized = str(Address(wallet_addr_str))
                        expected_addr_normalized = str(Address(expected_addr))
                        
                        # Сравниваем без учета формата (UQ vs EQ)
                        if wallet_addr_normalized != expected_addr_normalized:
                            # Пробуем сравнить в разных форматах
                            wallet_addr_user = wallet_addr.to_str(is_user_friendly=True, is_bounceable=True)
                            expected_addr_user = Address(expected_addr).to_str(is_user_friendly=True, is_bounceable=True)
                            
                            if wallet_addr_user != expected_addr_user:
                                print(f"⚠️ Warning: Wallet address mismatch!", file=sys.stderr, flush=True)
                                print(f"  Expected: {expected_addr}", file=sys.stderr, flush=True)
                                print(f"  Got from mnemonic: {wallet_addr_str}", file=sys.stderr, flush=True)
                                print(f"  This mnemonic may not match TON_WALLET_ADDRESS", file=sys.stderr, flush=True)
                    except Exception as addr_check_error:
                        print(f"⚠️ Could not verify wallet address match: {addr_check_error}", file=sys.stderr, flush=True)
            except asyncio.TimeoutError:
                raise Exception("Timeout initializing wallet. Please try again.")
            except ValueError as e:
                # ValueError обычно означает неверную мнемонику
                error_msg = str(e)
                if "mnemonics" in error_msg.lower() or "invalid" in error_msg.lower():
                    # Показываем количество слов и первые/последние слова для диагностики
                    preview = f"{' '.join(seed_words[:3])} ... {' '.join(seed_words[-3:])}"
                    
                    error_details = []
                    error_details.append(f"Invalid mnemonic phrase (ValueError).")
                    error_details.append(f"Current word count: {word_count}.")
                    error_details.append(f"Preview: {preview}.")
                    
                    if suspicious_words:
                        error_details.append(f"⚠️ Suspicious long words detected (possibly merged words without spaces):")
                        for sw in suspicious_words[:3]:  # Показываем максимум 3
                            error_details.append(f"  - {sw}")
                        error_details.append("Please check if words are separated by spaces. Each word should be 3-8 characters long.")
                    
                    error_details.append(f"Error: {error_msg}.")
                    error_details.append("Make sure:")
                    error_details.append("  1. All 24 words are from BIP39 wordlist (English)")
                    error_details.append("  2. Words are separated by SINGLE spaces (no multiple spaces)")
                    error_details.append("  3. No words are merged together (check for words longer than 12 characters)")
                    error_details.append("  4. No quotes around the mnemonic phrase")
                    error_details.append("  5. The mnemonic phrase matches your TON wallet")
                    
                    raise Exception("\n".join(error_details))
                raise Exception(f"Failed to initialize wallet: {error_msg}")
            except AssertionError as e:
                # AssertionError от pytoniq означает невалидную мнемонику
                error_msg = str(e)
                preview = f"{' '.join(seed_words[:3])} ... {' '.join(seed_words[-3:])}"
                
                # Пробуем альтернативный способ - может быть проблема с версией кошелька
                try:
                    print("🔄 Trying alternative wallet initialization (V3R2)...", file=sys.stderr, flush=True)
                    from pytoniq.contract.wallets.wallet import WalletV3R2
                    self._wallet = await asyncio.wait_for(
                        WalletV3R2.from_mnemonic(self._client, seed_words),
                        timeout=10.0
                    )
                    print("✅ Successfully initialized wallet as V3R2", file=sys.stderr, flush=True)
                    return  # Успешно инициализировали как V3R2
                except Exception as alt_error:
                    print(f"⚠️ Alternative initialization (V3R2) also failed: {alt_error}", file=sys.stderr, flush=True)
                
                # Формируем детальное сообщение об ошибке
                error_details = []
                error_details.append(f"Invalid mnemonic phrase (AssertionError).")
                error_details.append(f"Current word count: {word_count}.")
                error_details.append(f"Preview: {preview}.")
                
                if suspicious_words:
                    error_details.append(f"⚠️ Suspicious long words detected (possibly merged words without spaces):")
                    for sw in suspicious_words[:3]:  # Показываем максимум 3
                        error_details.append(f"  - {sw}")
                    error_details.append("Please check if words are separated by spaces. Each word should be 3-8 characters long.")
                
                error_details.append(f"Error: {error_msg}.")
                error_details.append("")
                error_details.append("Possible solutions:")
                error_details.append("  1. Verify that TON_WALLET_SEED matches TON_WALLET_ADDRESS")
                error_details.append("  2. Check if all words are from BIP39 English wordlist")
                error_details.append("  3. Ensure the mnemonic is for the correct wallet type (V4R2 or V3R2)")
                error_details.append("  4. Try regenerating the mnemonic from your wallet if possible")
                error_details.append("  5. Verify the mnemonic phrase in your wallet app")
                
                raise Exception("\n".join(error_details))
            except Exception as e:
                error_msg = str(e)
                if "mnemonics" in error_msg.lower() or "invalid" in error_msg.lower():
                    preview = f"{' '.join(seed_words[:3])} ... {''.join(seed_words[-3:])}"
                    raise Exception(
                        f"Invalid mnemonic phrase. Please check TON_WALLET_SEED. "
                        f"The mnemonic phrase must be exactly 24 valid BIP39 words. "
                        f"Current word count: {word_count}. "
                        f"Preview (first 3 and last 3 words): {preview}. "
                        f"Error details: {error_msg}. "
                        f"Make sure all words are from the BIP39 wordlist (English)."
                    )
                raise Exception(f"Failed to initialize wallet: {error_msg}")

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
        import traceback
        
        if amount_nano <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")

        # Проверяем, что TON_WALLET_SEED настроен
        if not self.seed_phrase:
            raise HTTPException(
                status_code=500, 
                detail="TON wallet not configured. TON_WALLET_SEED is not set."
            )

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
            available_ton = float(balance.ton_active_balance) / 10**9
            raise HTTPException(
                status_code=400, 
                detail=f"Insufficient funds. Available: {available_ton:.4f} TON, Requested: {float(amount_nano) / 10**9:.4f} TON"
            )

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
            # Валидация адреса
            try:
                Address(to_address)
            except Exception as addr_error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid TON address: {to_address}. Error: {str(addr_error)}"
                )
            
            # Отправка транзакции
            tx_hash = await self._send_raw(to_address, int(amount_nano))
            tx.tx_hash = tx_hash
            tx.status = "pending"
            db.commit()
            db.refresh(tx)
        except HTTPException:
            # Пробрасываем HTTPException как есть
            raise
        except Exception as exc:
            # Возврат средств при неуспехе
            error_msg = str(exc)
            error_trace = traceback.format_exc()
            print(f"❌ Ошибка при выводе средств: {error_msg}", file=sys.stderr, flush=True)
            print(f"❌ Traceback: {error_trace}", file=sys.stderr, flush=True)
            
            tx.status = "failed"
            tx.error_message = error_msg[:500]  # Ограничиваем длину сообщения об ошибке
            balance.ton_active_balance += amount_nano
            db.commit()
            db.refresh(tx)
            raise HTTPException(
                status_code=500, 
                detail=f"TON send failed: {error_msg}"
            )

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

    async def _check_deposits_via_api(self, db: Session, normalized_address: str):
        """Резервный метод: проверка депозитов через TON Center API"""
        import sys
        print("🔄 Пробуем через TON Center API (toncenter.com)...", file=sys.stderr, flush=True)
        
        try:
            import aiohttp
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=connector
            ) as session:
                url = "https://toncenter.com/api/v2/getTransactions"
                params = {
                    "address": normalized_address,
                    "limit": 50,
                    "archival": "true"  # TON Center API требует строку, а не булево значение
                }
                
                # TON Center API может работать без ключа для публичных запросов
                # Но если ключ есть, используем его
                if self.api_key:
                    params["api_key"] = self.api_key
                    print(f"🔑 Используем API ключ для TON Center", file=sys.stderr, flush=True)
                else:
                    print(f"ℹ️ API ключ не установлен, пробуем публичный запрос", file=sys.stderr, flush=True)
                
                print(f"🌐 Запрос к TON Center: {url} с адресом {normalized_address[:20]}...", file=sys.stderr, flush=True)
                
                async with session.get(url, params=params) as resp:
                    print(f"📡 TON Center API ответ: статус {resp.status}", file=sys.stderr, flush=True)
                    
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("ok"):
                            transactions = data.get("result", [])
                            print(f"📊 Найдено транзакций через TON Center: {len(transactions)}", file=sys.stderr, flush=True)
                            
                            if len(transactions) == 0:
                                print("ℹ️ Новых транзакций не найдено", file=sys.stderr, flush=True)
                                return
                            
                            # Обрабатываем транзакции
                            for tx in transactions:
                                tx_hash = tx.get("transaction_id", {}).get("hash", "")
                                if not tx_hash:
                                    continue
                                
                                existing = db.query(models.Deposit).filter(
                                    models.Deposit.tx_hash == tx_hash
                                ).first()
                                if existing:
                                    continue
                                
                                in_msg = tx.get("in_msg")
                                if not in_msg:
                                    continue
                                
                                value = int(in_msg.get("value", 0))
                                if value <= 0:
                                    continue
                                
                                source = in_msg.get("source", "")
                                
                                # Получаем комментарий
                                msg_text_str = ""
                                msg_body = in_msg.get("message", "")
                                if msg_body:
                                    try:
                                        import base64
                                        decoded = base64.b64decode(msg_body)
                                        msg_text_str = decoded.decode('utf-8', errors='ignore').strip()
                                    except:
                                        msg_text_str = str(msg_body)
                                
                                # Ищем Telegram ID
                                telegram_id = None
                                if msg_text_str:
                                    print(f"📝 Комментарий: {msg_text_str[:100]}", file=sys.stderr, flush=True)
                                    match_id = re.search(r'(?:tg:)?(\d{8,12})', msg_text_str)
                                    if match_id:
                                        telegram_id = match_id.group(1)
                                        print(f"✅ Найден Telegram ID: {telegram_id}", file=sys.stderr, flush=True)
                                
                                # Создаем депозит
                                deposit = models.Deposit(
                                    tx_hash=tx_hash,
                                    from_address=source,
                                    amount_nano=value,
                                    telegram_id_from_comment=telegram_id,
                                    status="pending"
                                )
                                db.add(deposit)
                                db.commit()
                                
                                # Зачисляем на баланс если нашли ID
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
                                            
                                            print(f"✅ Автоматически зачислено {value / 10**9:.4f} TON пользователю {telegram_id}", file=sys.stderr, flush=True)
                                    except Exception as e:
                                        print(f"⚠️ Ошибка обработки: {e}", file=sys.stderr, flush=True)
                        else:
                            error_msg = data.get('error', 'Unknown')
                            print(f"⚠️ TON Center API ошибка: {error_msg}", file=sys.stderr, flush=True)
                    elif resp.status == 401:
                        # 401 - Unauthorized, возможно API ключ неверный или не требуется
                        text = await resp.text()
                        print(f"⚠️ TON Center API 401 Unauthorized. Ответ: {text[:200]}", file=sys.stderr, flush=True)
                        print(f"💡 Попробуйте проверить TONAPI_KEY в Railway или оставьте его пустым для публичных запросов", file=sys.stderr, flush=True)
                    else:
                        text = await resp.text()
                        print(f"⚠️ TON Center API статус {resp.status}. Ответ: {text[:200]}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"❌ Ошибка TON Center API: {e}", file=sys.stderr, flush=True)

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
        
        # Используем tonapi.io для проверки депозитов (у нас уже есть API ключ)
        print("🔄 Используем tonapi.io для проверки депозитов...", file=sys.stderr, flush=True)
        return await self._check_deposits_via_tonapi(db, normalized_address)
    
    async def _check_deposits_via_tonapi(self, db: Session, normalized_address: str):
        """
        Проверяет входящие депозиты через tonapi.io.
        Парсит комментарии транзакций для извлечения Telegram ID и автоматически зачисляет средства.
        """
        import sys
        
        if not self.api_key:
            print("⚠️ TONAPI_KEY не установлен, пропускаем проверку через tonapi.io", file=sys.stderr, flush=True)
            return
        
        try:
            # Нормализуем адрес: конвертируем user-friendly (UQ...) в raw (EQ...)
            clean_address = normalized_address.strip()
            
            # Собираем все возможные варианты адреса
            addresses_to_try = []
            
            # 1. Исходный адрес
            addresses_to_try.append(clean_address)
            
            # 2. Пробуем конвертировать через pytoniq
            try:
                from pytoniq import Address as PytoniqAddress
                addr_obj = PytoniqAddress(clean_address)
                # Получаем raw формат (EQ...)
                raw_bounceable = addr_obj.to_str(is_user_friendly=False, is_bounceable=True)
                raw_non_bounceable = addr_obj.to_str(is_user_friendly=False, is_bounceable=False)
                if raw_bounceable not in addresses_to_try:
                    addresses_to_try.append(raw_bounceable)
                if raw_non_bounceable not in addresses_to_try:
                    addresses_to_try.append(raw_non_bounceable)
                print(f"✅ Адрес нормализован через pytoniq: {clean_address[:20]}... → {raw_bounceable[:20]}...", file=sys.stderr, flush=True)
            except Exception as addr_error:
                print(f"⚠️ Не удалось нормализовать адрес через pytoniq: {addr_error}", file=sys.stderr, flush=True)
            
            # 3. Простая конвертация UQ -> EQ
            if clean_address.startswith("UQ"):
                eq_address = "EQ" + clean_address[2:]
                if eq_address not in addresses_to_try:
                    addresses_to_try.append(eq_address)
                    print(f"🔄 Добавлен вариант адреса: {eq_address[:30]}...", file=sys.stderr, flush=True)
            
            # 4. Пробуем без дефисов (URL encoding может требовать)
            for addr in addresses_to_try[:]:  # Копируем список
                addr_no_dash = addr.replace("-", "")
                if addr_no_dash not in addresses_to_try:
                    addresses_to_try.append(addr_no_dash)
            
            print(f"📋 Всего вариантов адреса для проверки: {len(addresses_to_try)}", file=sys.stderr, flush=True)
            
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=connector
            ) as session:
                success = False
                transactions = []
                
                # Пробуем разные endpoints и форматы адресов
                endpoints_to_try = [
                    "/v2/accounts/{}/transactions",
                    "/v2/blockchain/accounts/{}/transactions",
                ]
                
                for endpoint_template in endpoints_to_try:
                    if success:
                        break
                    
                    for addr in addresses_to_try:
                        if success:
                            break
                            
                        url = f"https://tonapi.io{endpoint_template.format(addr)}"
                        headers = {
                            "Authorization": f"Bearer {self.api_key}",
                            "Accept": "application/json"
                        }
                        
                        params = {
                            "limit": 100,  # Получаем последние 100 транзакций
                            "min_lt": 0  # Можно добавить фильтр по логическому времени
                        }
                        
                        print(f"🌐 Запрос к tonapi.io: {url}", file=sys.stderr, flush=True)
                        print(f"🔑 Используем TONAPI_KEY: {'*' * (len(self.api_key) - 4) + self.api_key[-4:] if len(self.api_key) > 4 else '***'}", file=sys.stderr, flush=True)
                        
                        try:
                            async with session.get(url, headers=headers, params=params) as resp:
                                print(f"📡 tonapi.io ответ: статус {resp.status} для адреса {addr[:30]}... (endpoint: {endpoint_template})", file=sys.stderr, flush=True)
                                
                                if resp.status == 200:
                                    data = await resp.json()
                                    transactions = data.get("transactions", [])
                                    if transactions:
                                        print(f"✅✅✅ УСПЕШНО получены транзакции через адрес {addr[:30]}... (endpoint: {endpoint_template})", file=sys.stderr, flush=True)
                                        success = True
                                        break
                                    else:
                                        print(f"⚠️ Ответ 200, но транзакций нет. Пробуем следующий вариант...", file=sys.stderr, flush=True)
                                elif resp.status == 404:
                                    print(f"⚠️ 404 для адреса {addr[:30]}... (endpoint: {endpoint_template}), пробуем следующий вариант...", file=sys.stderr, flush=True)
                                    continue
                                else:
                                    text = await resp.text()
                                    print(f"⚠️ tonapi.io ошибка: статус {resp.status}. Ответ: {text[:200]}", file=sys.stderr, flush=True)
                                    continue
                        except Exception as req_error:
                            print(f"⚠️ Ошибка запроса к tonapi.io: {req_error}. Пробуем следующий вариант...", file=sys.stderr, flush=True)
                            continue
                
                if not success:
                    print(f"❌❌❌ Не удалось получить транзакции через tonapi.io ни для одного формата адреса/endpoint", file=sys.stderr, flush=True)
                    print(f"🔄 Пробуем fallback через TON Center API...", file=sys.stderr, flush=True)
                    # Fallback на TON Center API
                    await self._check_deposits_via_api(db, clean_address)
                    return
                
                if len(transactions) == 0:
                    print("ℹ️ Новых транзакций не найдено", file=sys.stderr, flush=True)
                    return
                
                print(f"📊 Найдено транзакций через tonapi.io: {len(transactions)}", file=sys.stderr, flush=True)
                
                processed_count = 0
                # Обрабатываем транзакции (они идут от новых к старым)
                for tx in transactions:
                    try:
                        # Получаем хэш транзакции
                        tx_hash = tx.get("hash", "")
                        if not tx_hash:
                            print(f"⚠️ Транзакция без hash, пропускаем", file=sys.stderr, flush=True)
                            continue
                        
                        # Проверяем, не обрабатывали ли мы уже эту транзакцию
                        existing = db.query(models.Deposit).filter(
                            models.Deposit.tx_hash == tx_hash
                        ).first()
                        if existing:
                            print(f"ℹ️ Транзакция {tx_hash[:16]}... уже обработана (статус: {existing.status})", file=sys.stderr, flush=True)
                            continue
                        
                        # Получаем входящие сообщения (incoming transactions)
                        in_msg = tx.get("in_msg")
                        if not in_msg:
                            print(f"⚠️ Транзакция {tx_hash[:16]}... без in_msg, пропускаем", file=sys.stderr, flush=True)
                            continue
                        
                        # Получаем сумму транзакции
                        value = int(in_msg.get("value", 0))
                        if value <= 0:
                            print(f"⚠️ Транзакция {tx_hash[:16]}... с нулевой суммой, пропускаем", file=sys.stderr, flush=True)
                            continue
                        
                        print(f"💰 Найдена транзакция: {tx_hash[:16]}... Сумма: {value / 10**9:.4f} TON", file=sys.stderr, flush=True)
                        
                        # Получаем адрес отправителя
                        source = in_msg.get("source", {})
                        if isinstance(source, dict):
                            source = source.get("address", "") or source.get("raw_form", "")
                        if not source:
                            source = str(in_msg.get("source", ""))
                        
                        print(f"📤 Отправитель: {source[:30]}...", file=sys.stderr, flush=True)
                        
                        # Получаем комментарий из тела сообщения - пробуем все возможные варианты
                        telegram_id = None
                        msg_text_str = ""
                        
                        # Вариант 1: msg_data.text
                        msg_data = in_msg.get("msg_data", {})
                        if isinstance(msg_data, dict):
                            msg_text_str = msg_data.get("text", "") or msg_data.get("body", "") or msg_data.get("comment", "")
                            if not msg_text_str and "text" in msg_data:
                                msg_text_str = str(msg_data["text"])
                        
                        # Вариант 2: decoded_body
                        if not msg_text_str:
                            decoded = in_msg.get("decoded_body", {})
                            if isinstance(decoded, dict):
                                msg_text_str = decoded.get("text", "") or decoded.get("comment", "") or decoded.get("body", "")
                        
                        # Вариант 3: body (base64)
                        if not msg_text_str:
                            body_b64 = in_msg.get("body", "")
                            if body_b64:
                                try:
                                    import base64
                                    decoded_bytes = base64.b64decode(body_b64)
                                    # Пропускаем первые 4 байта (обычно это op code)
                                    if len(decoded_bytes) > 4:
                                        msg_text_str = decoded_bytes[4:].decode('utf-8', errors='ignore').strip()
                                    elif len(decoded_bytes) > 0:
                                        # Если меньше 4 байт, пробуем декодировать всё
                                        msg_text_str = decoded_bytes.decode('utf-8', errors='ignore').strip()
                                except Exception as decode_err:
                                    print(f"⚠️ Ошибка декодирования body: {decode_err}", file=sys.stderr, flush=True)
                        
                        # Вариант 4: comment напрямую
                        if not msg_text_str:
                            msg_text_str = in_msg.get("comment", "") or in_msg.get("text", "")
                        
                        # Вариант 5: пробуем из msg_data как строку
                        if not msg_text_str and isinstance(msg_data, str):
                            msg_text_str = msg_data
                        
                        # Логируем структуру для диагностики
                        if not msg_text_str:
                            print(f"🔍 Структура in_msg для диагностики: {str(in_msg)[:500]}", file=sys.stderr, flush=True)
                        
                        # Ищем Telegram ID в комментарии
                        if msg_text_str:
                            print(f"📝 Комментарий транзакции: {msg_text_str[:200]}", file=sys.stderr, flush=True)
                            # Ищем паттерн: числа от 8 до 12 цифр (Telegram ID)
                            match_id = re.search(r'(?:tg:)?(\d{8,12})', msg_text_str)
                            if match_id:
                                telegram_id = match_id.group(1)
                                print(f"✅✅✅ Найден Telegram ID в комментарии: {telegram_id}", file=sys.stderr, flush=True)
                            else:
                                print(f"⚠️ Telegram ID не найден в комментарии. Комментарий: '{msg_text_str[:100]}'", file=sys.stderr, flush=True)
                        else:
                            print(f"⚠️ Комментарий не найден в транзакции {tx_hash[:16]}...", file=sys.stderr, flush=True)
                        
                        # Создаем запись о депозите (даже если Telegram ID не найден)
                        deposit = models.Deposit(
                            tx_hash=tx_hash,
                            from_address=source,
                            amount_nano=value,
                            telegram_id_from_comment=telegram_id,
                            status="pending"
                        )
                        db.add(deposit)
                        db.commit()
                        print(f"💾 Создана запись о депозите: ID={deposit.id}, TX={tx_hash[:16]}..., сумма={value / 10**9:.4f} TON, Telegram ID={telegram_id or 'не найден'}", file=sys.stderr, flush=True)
                        
                        # Зачисляем на баланс если нашли ID
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
                                        print(f"✅ Создан новый баланс для пользователя {telegram_id}", file=sys.stderr, flush=True)
                                    else:
                                        balance.ton_active_balance += value
                                        print(f"✅ Обновлен баланс пользователя {telegram_id}: +{value / 10**9:.4f} TON", file=sys.stderr, flush=True)
                                    
                                    deposit.user_id = user.id
                                    deposit.status = "processed"
                                    deposit.processed_at = datetime.utcnow()
                                    db.commit()
                                    
                                    print(f"✅✅✅ АВТОМАТИЧЕСКИ ЗАЧИСЛЕНО {value / 10**9:.4f} TON пользователю {telegram_id} (ID в БД: {user.id})", file=sys.stderr, flush=True)
                                    processed_count += 1
                                else:
                                    print(f"⚠️ Пользователь с Telegram ID {telegram_id} не найден в БД", file=sys.stderr, flush=True)
                            except Exception as e:
                                import traceback
                                print(f"❌ Ошибка обработки депозита для {telegram_id}: {e}", file=sys.stderr, flush=True)
                                traceback.print_exc(file=sys.stderr)
                        else:
                            print(f"⚠️ Telegram ID не найден в комментарии транзакции {tx_hash[:16]}...", file=sys.stderr, flush=True)
                        
                    except Exception as tx_error:
                        import traceback
                        print(f"❌ Ошибка обработки транзакции: {tx_error}", file=sys.stderr, flush=True)
                        traceback.print_exc(file=sys.stderr)
                        continue
                
                print(f"✅ Обработано новых депозитов: {processed_count}", file=sys.stderr, flush=True)
                        
        except Exception as e:
            import traceback
            print(f"❌ Критическая ошибка при проверке депозитов через tonapi.io: {e}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
    
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

