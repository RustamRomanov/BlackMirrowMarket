import os
import sys
import uuid
import ssl
import asyncio
import aiohttp
import json
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
        # Читаем seed phrase и сразу убираем кавычки, если они есть
        raw_seed = os.getenv("TON_WALLET_SEED", "").strip()
        # Убираем кавычки в начале и конце, если они есть
        if raw_seed.startswith('"') and raw_seed.endswith('"'):
            raw_seed = raw_seed[1:-1].strip()
        if raw_seed.startswith("'") and raw_seed.endswith("'"):
            raw_seed = raw_seed[1:-1].strip()
        self.seed_phrase = raw_seed
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
        # Кавычки уже должны быть удалены в __init__, но на всякий случай проверяем еще раз
        cleaned_seed = self.seed_phrase.strip()
        # Убираем кавычки, если они есть (могут остаться, если переменная была задана с кавычками в Railway)
        while (cleaned_seed.startswith('"') and cleaned_seed.endswith('"')) or \
              (cleaned_seed.startswith("'") and cleaned_seed.endswith("'")):
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
        
        seed_words = fixed_words

        # Дополнительная валидация: проверяем, что все слова есть в BIP39 wordlist
        try:
            from mnemonic import Mnemonic
            mnemo = Mnemonic("english")
            wordlist = set(mnemo.wordlist)
            invalid_words = [w for w in seed_words if w not in wordlist]
            if invalid_words:
                preview = f"{' '.join(seed_words[:3])} ... {' '.join(seed_words[-3:])}"
                raise Exception(
                    "Invalid mnemonic: some words are not in the BIP39 English wordlist. "
                    f"Invalid words (first 5): {invalid_words[:5]}. "
                    f"Word count: {len(seed_words)}. Preview: {preview}"
                )
            # Дополнительно проверяем checksum; если не сходится, не падаем, а предупреждаем.
            seed_string = " ".join(seed_words)
            if not mnemo.check(seed_string):
                preview = f"{' '.join(seed_words[:3])} ... {' '.join(seed_words[-3:])}"
                print(
                    f"⚠️ Mnemonic checksum failed (BIP39). "
                    f"Word count: {len(seed_words)}. Preview: {preview}",
                    file=sys.stderr,
                    flush=True,
                )
        except ImportError:
            # Если mnemonic не установлен, продолжаем (но в requirements он есть)
            pass
        
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
            # Используем более надежные настройки для Railway
            # Пробуем подключиться несколько раз с увеличенными таймаутами
            max_connection_attempts = 5
            last_conn_error = None
            
            for conn_attempt in range(1, max_connection_attempts + 1):
                try:
                    print(f"🔄 Connection attempt {conn_attempt}/{max_connection_attempts} to TON blockchain...", file=sys.stderr, flush=True)
                    
                    # Создаем клиент
                    self._client = LiteBalancer.from_mainnet_config()
                    
                    # Увеличиваем таймаут для Railway (может быть медленное подключение)
                    # Также даем больше времени на поиск пиров
                    print(f"🔄 Starting up LiteBalancer (this may take up to 60 seconds)...", file=sys.stderr, flush=True)
                    await asyncio.wait_for(self._client.start_up(), timeout=60.0)
                    
                    # Проверяем, что клиент действительно подключен и имеет активные пиры
                    print(f"🔄 Verifying connection...", file=sys.stderr, flush=True)
                    try:
                        # Пробуем сделать простой запрос для проверки подключения
                        masterchain_info = await asyncio.wait_for(
                            self._client.get_masterchain_info(), 
                            timeout=15.0
                        )
                        print(f"✅ Connected to TON blockchain! Block seqno: {masterchain_info.last.seqno if hasattr(masterchain_info, 'last') else 'N/A'}", file=sys.stderr, flush=True)
                        break  # Успешно подключились
                    except Exception as verify_error:
                        print(f"⚠️ Connection established but verification failed: {verify_error}", file=sys.stderr, flush=True)
                        # Закрываем клиент и пробуем снова
                        try:
                            await self._client.close_all()
                        except:
                            pass
                        self._client = None
                        raise Exception(f"Connection verification failed: {verify_error}")
                        
                except asyncio.TimeoutError:
                    last_conn_error = "Timeout connecting to TON blockchain (60s timeout exceeded)"
                    print(f"❌ Attempt {conn_attempt} failed: {last_conn_error}", file=sys.stderr, flush=True)
                    if self._client:
                        try:
                            await self._client.close_all()
                        except:
                            pass
                        self._client = None
                    if conn_attempt < max_connection_attempts:
                        wait_time = min(conn_attempt * 3, 15)  # Увеличиваем время ожидания
                        print(f"🔄 Retrying connection in {wait_time} seconds...", file=sys.stderr, flush=True)
                        await asyncio.sleep(wait_time)
                    else:
                        raise Exception(f"Failed to connect to TON blockchain after {max_connection_attempts} attempts. "
                                      f"Last error: {last_conn_error}. "
                                      f"This may be due to network restrictions on Railway. "
                                      f"Please check Railway network settings or try again later.")
                except Exception as e:
                    last_conn_error = str(e)
                    print(f"❌ Attempt {conn_attempt} failed: {last_conn_error}", file=sys.stderr, flush=True)
                    if self._client:
                        try:
                            await self._client.close_all()
                        except:
                            pass
                        self._client = None
                    if conn_attempt < max_connection_attempts:
                        wait_time = min(conn_attempt * 3, 15)  # Увеличиваем время ожидания
                        print(f"🔄 Retrying connection in {wait_time} seconds...", file=sys.stderr, flush=True)
                        await asyncio.sleep(wait_time)
                    else:
                        raise Exception(f"Failed to connect to TON blockchain after {max_connection_attempts} attempts: {last_conn_error}")
        
        if self._wallet is None:
            # Кошелек V4R2 из сид-фразы. Ключи остаются в памяти процесса.
            # Сигнатура: from_mnemonic(provider, mnemonics, wc=0, wallet_id=None, version="v3r2")
            
            # Детальное логирование для диагностики
            print(f"🔍 Debug: Initializing wallet with {len(seed_words)} words", file=sys.stderr, flush=True)
            print(f"🔍 Debug: First 3 words: {seed_words[:3]}", file=sys.stderr, flush=True)
            print(f"🔍 Debug: Last 3 words: {seed_words[-3:]}", file=sys.stderr, flush=True)
            print(f"🔍 Debug: Word lengths: {[len(w) for w in seed_words]}", file=sys.stderr, flush=True)
            
            # Пробуем сначала валидировать через библиотеку mnemonic
            try:
                from mnemonic import Mnemonic
                mnemo = Mnemonic("english")
                seed_string = " ".join(seed_words)
                if not mnemo.check(seed_string):
                    print("⚠️ WARNING: Mnemonic validation failed with 'mnemonic' library", file=sys.stderr, flush=True)
                else:
                    print("✅ Mnemonic is valid according to BIP39 standard", file=sys.stderr, flush=True)
                    # Генерируем seed из мнемоники
                    seed_bytes = mnemo.to_seed(seed_string)
                    print(f"✅ Generated seed from mnemonic (length: {len(seed_bytes)})", file=sys.stderr, flush=True)
            except ImportError:
                print("⚠️ 'mnemonic' library not installed, skipping BIP39 validation", file=sys.stderr, flush=True)
            except Exception as mnemonic_error:
                print(f"⚠️ Mnemonic library check error: {mnemonic_error}", file=sys.stderr, flush=True)
            
            try:
                # Пробуем сначала V4R2
                self._wallet = await asyncio.wait_for(
                    WalletV4R2.from_mnemonic(self._client, seed_words),
                    timeout=10.0
                )
                print("✅ Successfully initialized wallet as V4R2", file=sys.stderr, flush=True)
                
                # Проверяем, что адрес кошелька соответствует TON_WALLET_ADDRESS (если можем получить адрес)
                if self.wallet_address:
                    expected_addr = self.wallet_address.strip()
                    try:
                        if hasattr(self._wallet, "get_address"):
                            wallet_addr = await self._wallet.get_address()
                        elif hasattr(self._wallet, "address"):
                            wallet_addr = self._wallet.address
                        else:
                            wallet_addr = None
                        
                        if wallet_addr:
                            wallet_addr_str = str(wallet_addr)
                            # Нормализуем адреса для сравнения
                            try:
                                wallet_addr_normalized = str(Address(wallet_addr_str))
                                expected_addr_normalized = str(Address(expected_addr))
                                
                                # Сравниваем без учета формата (UQ vs EQ)
                                if wallet_addr_normalized != expected_addr_normalized:
                                    # Пробуем сравнить в разных форматах
                                    try:
                                        wallet_addr_user = Address(wallet_addr_str).to_str(is_user_friendly=True, is_bounceable=True)
                                        expected_addr_user = Address(expected_addr).to_str(is_user_friendly=True, is_bounceable=True)
                                        if wallet_addr_user != expected_addr_user:
                                            print(f"⚠️ Warning: Wallet address mismatch!", file=sys.stderr, flush=True)
                                            print(f"  Expected: {expected_addr}", file=sys.stderr, flush=True)
                                            print(f"  Got from mnemonic: {wallet_addr_str}", file=sys.stderr, flush=True)
                                            print(f"  This mnemonic may not match TON_WALLET_ADDRESS", file=sys.stderr, flush=True)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        else:
                            print("ℹ️ Skip address verification: wallet address not available from client", file=sys.stderr, flush=True)
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
                
                # Проверяем suspicious_words (определяем здесь, если еще не определено)
                if 'suspicious_words' not in locals():
                    suspicious_words = []
                    for i, word in enumerate(seed_words):
                        if len(word) > 12:
                            suspicious_words.append(f"word {i+1}: '{word[:30]}...' (length: {len(word)})")
                
                # Пробуем использовать библиотеку mnemonic для валидации
                try:
                    print("🔄 Trying to validate mnemonic with 'mnemonic' library...", file=sys.stderr, flush=True)
                    try:
                        from mnemonic import Mnemonic
                        mnemo = Mnemonic("english")
                        seed_string = " ".join(seed_words)
                        if not mnemo.check(seed_string):
                            print("⚠️ Mnemonic validation failed with 'mnemonic' library", file=sys.stderr, flush=True)
                        else:
                            print("✅ Mnemonic is valid according to 'mnemonic' library", file=sys.stderr, flush=True)
                            # Генерируем seed из мнемоники
                            seed_bytes = mnemo.to_seed(seed_string)
                            print(f"✅ Generated seed from mnemonic (length: {len(seed_bytes)})", file=sys.stderr, flush=True)
                    except ImportError:
                        print("⚠️ 'mnemonic' library not installed, skipping validation", file=sys.stderr, flush=True)
                except Exception as mnemonic_error:
                    print(f"⚠️ Mnemonic library check failed: {mnemonic_error}", file=sys.stderr, flush=True)
                
                # Пробуем альтернативный способ - генерируем приватный ключ из мнемоники
                try:
                    print("🔄 Trying alternative: generate private key from mnemonic...", file=sys.stderr, flush=True)
                    from mnemonic import Mnemonic
                    import hashlib
                    from pytoniq_core.crypto.keys import PrivateKey
                    
                    mnemo = Mnemonic("english")
                    seed_string = " ".join(seed_words)
                    
                    # Генерируем seed из мнемоники
                    seed_bytes = mnemo.to_seed(seed_string)
                    print(f"✅ Generated seed from mnemonic (length: {len(seed_bytes)})", file=sys.stderr, flush=True)
                    
                    # Генерируем приватный ключ из seed (первые 32 байта)
                    private_key_bytes = seed_bytes[:32]
                    private_key = PrivateKey(private_key_bytes)
                    
                    # Пробуем инициализировать кошелек из приватного ключа
                    print("🔄 Initializing wallet from private key...", file=sys.stderr, flush=True)
                    self._wallet = await asyncio.wait_for(
                        WalletV4R2.from_private_key(self._client, private_key),
                        timeout=10.0
                    )
                    print("✅ Successfully initialized wallet from private key!", file=sys.stderr, flush=True)
                    return  # Успешно инициализировали из приватного ключа
                except ImportError as import_err:
                    print(f"⚠️ Cannot use private key method: {import_err}", file=sys.stderr, flush=True)
                except Exception as pk_error:
                    print(f"⚠️ Private key initialization failed: {pk_error}", file=sys.stderr, flush=True)
                    print(f"⚠️ PK error type: {type(pk_error).__name__}", file=sys.stderr, flush=True)
                
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
                    print(f"⚠️ V3R2 error type: {type(alt_error).__name__}", file=sys.stderr, flush=True)
                    print(f"⚠️ V3R2 error message: {str(alt_error)}", file=sys.stderr, flush=True)
                    
                # Пробуем еще один вариант - может быть нужно передать как строку
                try:
                    print("🔄 Trying alternative: passing mnemonic as string...", file=sys.stderr, flush=True)
                    seed_string = " ".join(seed_words)
                    # Некоторые библиотеки ожидают строку, а не список
                    self._wallet = await asyncio.wait_for(
                        WalletV4R2.from_mnemonic(self._client, seed_string.split()),
                        timeout=10.0
                    )
                    print("✅ Successfully initialized wallet with string mnemonic", file=sys.stderr, flush=True)
                    return
                except Exception as str_error:
                    print(f"⚠️ String mnemonic initialization also failed: {str_error}", file=sys.stderr, flush=True)
                
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
                error_details.append("⚠️ CRITICAL: pytoniq cannot validate this mnemonic, but words appear correct.")
                error_details.append("This may be a compatibility issue with pytoniq library.")
                error_details.append("")
                error_details.append("Possible solutions:")
                error_details.append("  1. Verify that TON_WALLET_SEED matches TON_WALLET_ADDRESS")
                error_details.append("  2. Check if all words are from BIP39 English wordlist")
                error_details.append("  3. Ensure the mnemonic is for the correct wallet type (V4R2 or V3R2)")
                error_details.append("  4. Try regenerating the mnemonic from your wallet if possible")
                error_details.append("  5. Verify the mnemonic phrase in your wallet app")
                error_details.append("  6. Consider using a different TON wallet library")
                
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

    async def _get_seqno_via_api(self) -> int:
        """Получает seqno кошелька через tonapi.io HTTP API."""
        if not self.wallet_address or not self.api_key:
            raise Exception("TON_WALLET_ADDRESS and TONAPI_KEY must be set")
        
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=connector
            ) as session:
                # Пробуем разные форматы адреса
                addresses_to_try = [self.wallet_address]
                if self.wallet_address.startswith("UQ"):
                    addresses_to_try.append("EQ" + self.wallet_address[2:])
                
                for addr in addresses_to_try:
                    url = f"https://tonapi.io/v2/accounts/{addr}"
                    headers = {"Authorization": f"Bearer {self.api_key}"}
                    try:
                        async with session.get(url, headers=headers) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                print(f"🔍 Debug: API response structure: {str(data)[:500]}", file=sys.stderr, flush=True)
                                
                                # Получаем seqno из состояния кошелька
                                # Для uninit кошелька seqno = 0, но это нормально
                                status = data.get("status", "")
                                
                                # Пробуем получить seqno через runGetMethod
                                # Используем другой endpoint для получения seqno
                                try:
                                    # Пробуем получить seqno через runGetMethod
                                    # Используем правильный endpoint для вызова метода
                                    method_url = f"https://tonapi.io/v2/blockchain/accounts/{addr}/methods/seqno"
                                    # Пробуем GET сначала
                                    async with session.get(method_url, headers=headers) as method_resp:
                                        if method_resp.status == 200:
                                            method_data = await method_resp.json()
                                            print(f"🔍 Debug: runGetMethod GET response: {str(method_data)[:500]}", file=sys.stderr, flush=True)
                                            
                                            if "stack" in method_data and len(method_data["stack"]) > 0:
                                                stack_item = method_data["stack"][0]
                                                # stack_item может быть словарем с ключами "type" и "value"
                                                if isinstance(stack_item, dict):
                                                    # Проверяем разные варианты структуры
                                                    seqno_value = stack_item.get("value")
                                                    if seqno_value is None:
                                                        # Может быть вложенная структура
                                                        if "num" in stack_item:
                                                            seqno_value = stack_item["num"]
                                                        elif "dec" in stack_item:
                                                            seqno_value = stack_item["dec"]
                                                        else:
                                                            seqno_value = stack_item
                                                else:
                                                    seqno_value = stack_item
                                                
                                                # Преобразуем в int
                                                if isinstance(seqno_value, str):
                                                    seqno = int(seqno_value, 16) if seqno_value.startswith("0x") else int(seqno_value)
                                                elif isinstance(seqno_value, (int, float)):
                                                    seqno = int(seqno_value)
                                                elif isinstance(seqno_value, dict):
                                                    # Если это словарь, пробуем получить значение из него
                                                    seqno = int(seqno_value.get("value", seqno_value.get("num", 0)))
                                                else:
                                                    seqno = 0
                                                
                                                print(f"✅ Got seqno via runGetMethod: {seqno}", file=sys.stderr, flush=True)
                                                return seqno
                                    
                                    # Если GET не сработал, пробуем POST
                                    async with session.post(method_url, headers=headers, json={}) as method_resp:
                                        if method_resp.status == 200:
                                            method_data = await method_resp.json()
                                            print(f"🔍 Debug: runGetMethod response: {str(method_data)[:500]}", file=sys.stderr, flush=True)
                                            
                                            if "stack" in method_data and len(method_data["stack"]) > 0:
                                                stack_item = method_data["stack"][0]
                                                # stack_item может быть словарем с ключами "type" и "value"
                                                if isinstance(stack_item, dict):
                                                    # Проверяем разные варианты структуры
                                                    seqno_value = stack_item.get("value")
                                                    if seqno_value is None:
                                                        # Может быть вложенная структура
                                                        if "num" in stack_item:
                                                            seqno_value = stack_item["num"]
                                                        elif "dec" in stack_item:
                                                            seqno_value = stack_item["dec"]
                                                        else:
                                                            seqno_value = stack_item
                                                else:
                                                    seqno_value = stack_item
                                                
                                                # Преобразуем в int
                                                if isinstance(seqno_value, str):
                                                    seqno = int(seqno_value, 16) if seqno_value.startswith("0x") else int(seqno_value)
                                                elif isinstance(seqno_value, (int, float)):
                                                    seqno = int(seqno_value)
                                                elif isinstance(seqno_value, dict):
                                                    # Если это словарь, пробуем получить значение из него
                                                    seqno = int(seqno_value.get("value", seqno_value.get("num", 0)))
                                                else:
                                                    seqno = 0
                                                
                                                print(f"✅ Got seqno via runGetMethod: {seqno}", file=sys.stderr, flush=True)
                                                return seqno
                                except Exception as method_error:
                                    print(f"⚠️ Error getting seqno via runGetMethod: {method_error}", file=sys.stderr, flush=True)
                                
                                # Получаем seqno из состояния кошелька
                                # interfaces может быть списком или словарем
                                interfaces = data.get("interfaces", [])
                                if isinstance(interfaces, list):
                                    # Если это список, ищем wallet_v5r1, wallet_v4r2, wallet_v3r1
                                    for interface in interfaces:
                                        if isinstance(interface, dict):
                                            interface_name = interface.get("name", "")
                                            if interface_name in ["wallet_v5r1", "wallet_v4r2", "wallet_v3r1"]:
                                                seqno = interface.get("seqno")
                                                if seqno is not None:
                                                    print(f"✅ Got seqno via API from {interface_name}: {seqno}", file=sys.stderr, flush=True)
                                                    return int(seqno)
                                        elif isinstance(interface, str):
                                            # Если interface - это строка (например, "wallet_v5r1")
                                            if interface in ["wallet_v5r1", "wallet_v4r2", "wallet_v3r1"]:
                                                # Пробуем получить seqno через runGetMethod еще раз
                                                pass
                                elif isinstance(interfaces, dict):
                                    # Если это словарь, пробуем напрямую
                                    for wallet_type in ["wallet_v5r1", "wallet_v4r2", "wallet_v3r1"]:
                                        seqno = interfaces.get(wallet_type, {}).get("seqno")
                                        if seqno is not None:
                                            print(f"✅ Got seqno via API from {wallet_type}: {seqno}", file=sys.stderr, flush=True)
                                            return int(seqno)
                                
                                # Для uninit кошелька seqno = 0
                                if status == "uninit":
                                    print(f"ℹ️ Wallet is uninit, using seqno = 0", file=sys.stderr, flush=True)
                                    return 0
                                
                                # Если кошелек active, но seqno не получен, пробуем еще раз через runGetMethod
                                if status == "active":
                                    print(f"⚠️ Wallet is active but seqno not found in interfaces, trying runGetMethod again...", file=sys.stderr, flush=True)
                                    # Уже пробовали выше, но если не получилось, возвращаем 0
                                    # Это может быть проблемой - active кошелек должен иметь seqno > 0
                                
                                # Пробуем получить seqno напрямую из data
                                seqno = data.get("seqno")
                                if seqno is not None:
                                    print(f"✅ Got seqno via API (direct): {seqno}", file=sys.stderr, flush=True)
                                    return int(seqno)
                    except Exception as e:
                        print(f"⚠️ Error getting seqno for {addr}: {e}", file=sys.stderr, flush=True)
                        continue
                
                # Если не получили seqno, возвращаем 0 (для новых кошельков)
                print("⚠️ Could not get seqno via API, using 0", file=sys.stderr, flush=True)
                return 0
        except Exception as e:
            print(f"⚠️ Error getting seqno via API: {e}, using 0", file=sys.stderr, flush=True)
            return 0
    
    async def _create_wallet_transaction_manually(self, seed_words: list, to_address: str, amount_nano: int, seqno: int, comment: str = None) -> str:
        """
        Создает транзакцию используя pytoniq create_transfer_message БЕЗ подключения к блокчейну.
        Использует правильный способ создания транзакции через готовые методы pytoniq.
        """
        try:
            from pytoniq import LiteClient, WalletV4R2, Address as PytoniqAddress
            from pytoniq_core.boc import Builder
            
            print(f"🔄 Using pytoniq create_transfer_message (NEW approach - no blockchain connection)", file=sys.stderr, flush=True)
            
            # Создаем LiteClient БЕЗ подключения к блокчейну
            # Используем фиктивный провайдер, который не требует подключения
            client = LiteClient.from_mainnet_config()
            
            # Пробуем создать кошелек из мнемоники БЕЗ подключения к блокчейну
            # Используем правильный способ - создаем кошелек локально
            try:
                # Создаем кошелек из мнемоники - НЕ подключаемся к блокчейну
                # from_mnemonic может работать без подключения для создания транзакции
                wallet = await WalletV4R2.from_mnemonic(client, seed_words, wc=0)
                print(f"✅ Created wallet from mnemonic (local, no connection)", file=sys.stderr, flush=True)
            except Exception as wallet_error:
                print(f"⚠️ Error creating wallet: {wallet_error}", file=sys.stderr, flush=True)
                # Если не получилось, используем fallback
                return await self._create_wallet_transaction_fallback(seed_words, to_address, amount_nano, seqno, comment)
            
            # Создаем адрес получателя
            dest_addr = PytoniqAddress(to_address)
            
            # Создаем body с комментарием
            body = None
            if comment:
                body_builder = Builder()
                body_builder.store_uint(0, 32)  # op = 0 для текстового комментария
                body_builder.store_bytes(comment.encode('utf-8'))
                body = body_builder.end_cell()
            
            # Используем готовый метод create_transfer_message БЕЗ подключения к блокчейну
            # Этот метод создает транзакцию локально и возвращает правильный BOC
            try:
                message = await wallet.create_transfer_message(
                    destination=dest_addr,
                    amount=amount_nano,
                    seqno=seqno,
                    body=body
                )
                
                # Используем готовый метод to_boc_base64() для правильной сериализации BOC
                boc_base64 = message.to_boc_base64()
                
                print(f"✅ Created transaction using pytoniq create_transfer_message (seqno={seqno}, NEW approach)", file=sys.stderr, flush=True)
                return boc_base64
                
            except Exception as transfer_error:
                print(f"⚠️ Error creating transfer message: {transfer_error}, using fallback", file=sys.stderr, flush=True)
                # Если не получилось, используем fallback
                return await self._create_wallet_transaction_fallback(seed_words, to_address, amount_nano, seqno, comment)
            
        except Exception as e:
            print(f"⚠️ Error with pytoniq create_transfer_message: {e}, using fallback", file=sys.stderr, flush=True)
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}", file=sys.stderr, flush=True)
            return await self._create_wallet_transaction_fallback(seed_words, to_address, amount_nano, seqno, comment)
    
    async def _create_wallet_transaction_fallback(self, seed_words: list, to_address: str, amount_nano: int, seqno: int, comment: str = None) -> str:
        """
        Fallback метод для создания транзакции (старый способ).
        Используется если tonutils недоступен.
        """
        try:
            # Импортируем необходимые модули
            from mnemonic import Mnemonic
            from pytoniq_core.boc import Builder, Cell
            from pytoniq import Address as PytoniqAddress
            import hashlib
            import nacl.signing
            import nacl.encoding
            
            # Создаем приватный ключ из мнемоники
            mnemo = Mnemonic("english")
            seed_string = " ".join(seed_words)
            seed = mnemo.to_seed(seed_string)
            
            # Используем первые 32 байта seed для приватного ключа
            private_key_bytes = seed[:32]
            
            # Создаем приватный ключ используя PyNaCl (nacl.signing)
            signing_key = nacl.signing.SigningKey(private_key_bytes)
            # Получаем публичный ключ (32 байта) в raw формате
            verify_key = signing_key.verify_key
            public_key_bytes = verify_key.encode(encoder=nacl.encoding.RawEncoder)
            
            print(f"✅ Created private key from mnemonic using PyNaCl", file=sys.stderr, flush=True)
            
            # Получаем адрес кошелька из публичного ключа (WalletV4R2)
            # WalletV4R2 использует wallet_id = 698983191 (0x29A9A317)
            wallet_id = 698983191
            
            # Получаем код WalletV4R2 (стандартный код контракта)
            # Используем упрощенный подход: создаем StateInit без кода
            # Для WalletV4R2 код можно получить через API или использовать стандартный
            
            # Создаем адрес получателя
            dest_addr = PytoniqAddress(to_address)
            
            # Создаем body с комментарием, если он указан
            body = None
            if comment:
                body_builder = Builder()
                # Флаг 0 для текстового комментария (op = 0)
                body_builder.store_uint(0, 32)
                # Добавляем текст комментария как байты
                comment_bytes = comment.encode('utf-8')
                body_builder.store_bytes(comment_bytes)
                body = body_builder.end_cell()
            
            # Создаем внутреннее сообщение (InternalMessage)
            # Структура: (ihr_disabled, bounce, bounced, src, dest, value, ihr_fee, fwd_fee, created_lt, created_at, init?, body?)
            message_builder = Builder()
            message_builder.store_bit(1)  # ihr_disabled = 1 (IHR disabled)
            message_builder.store_bit(1)  # bounce = 1 (bounceable)
            message_builder.store_bit(0)  # bounced = 0 (not bounced yet)
            message_builder.store_address(None)  # src = None (internal from wallet)
            message_builder.store_address(dest_addr)  # destination
            message_builder.store_coins(amount_nano)  # value
            message_builder.store_coins(0)  # ihr_fee = 0
            message_builder.store_coins(0)  # fwd_fee = 0
            message_builder.store_uint(0, 64)  # created_lt = 0
            message_builder.store_uint(0, 32)  # created_at = 0
            message_builder.store_bit(0)  # no init
            
            # Добавляем body, если есть
            if body:
                message_builder.store_bit(1)  # has body
                message_builder.store_ref(body)
            else:
                message_builder.store_bit(0)  # no body
            
            message_cell = message_builder.end_cell()
            
            # Создаем тело транзакции WalletV4R2
            # Структура: (op, query_id, new_state, messages...)
            # op = 0 для transfer
            # query_id = 0 (можно использовать timestamp)
            # new_state = null для простого transfer
            # messages = список сообщений
            wallet_builder = Builder()
            wallet_builder.store_uint(0, 32)  # op = 0 (transfer)
            wallet_builder.store_uint(0, 64)  # query_id = 0
            wallet_builder.store_uint(seqno, 32)  # seqno
            
            # Для WalletV4R2: если есть new_state, то это отдельное поле
            # Для простого transfer: new_state = null
            wallet_builder.store_bit(0)  # no new_state
            
            # Добавляем сообщение
            wallet_builder.store_ref(message_cell)  # message
            
            wallet_body = wallet_builder.end_cell()
            
            # Подписываем транзакцию
            # Подпись = sign(private_key, wallet_body.hash())
            # Для WalletV4R2 подпись создается от hash(wallet_body)
            # В pytoniq_core hash может быть свойством (bytes) или методом
            try:
                if hasattr(wallet_body, 'hash'):
                    wallet_body_hash = wallet_body.hash
                    # Проверяем, это свойство (bytes) или метод
                    if callable(wallet_body_hash):
                        wallet_body_hash = wallet_body_hash()
                    # Если это уже bytes, используем как есть
                    if not isinstance(wallet_body_hash, bytes):
                        # Если это не bytes, конвертируем через serialize
                        wallet_body_hash = hashlib.sha256(wallet_body.serialize()).digest()
                else:
                    # Если hash не существует, используем serialize
                    wallet_body_hash = hashlib.sha256(wallet_body.serialize()).digest()
            except Exception as hash_error:
                # Fallback: используем serialize
                print(f"⚠️ Error getting hash from wallet_body: {hash_error}, using serialize", file=sys.stderr, flush=True)
                wallet_body_hash = hashlib.sha256(wallet_body.serialize()).digest()
            
            # Подписываем используя PyNaCl
            # PyNaCl.sign() возвращает SignedMessage, извлекаем только signature (64 байта)
            signed_message = signing_key.sign(wallet_body_hash)
            signature = signed_message.signature  # 64 bytes для Ed25519
            
            # Создаем полную транзакцию с подписью
            # Структура: (signature, body)
            signed_builder = Builder()
            signed_builder.store_bytes(signature)  # signature (512 bits = 64 bytes)
            signed_builder.store_ref(wallet_body)  # body
            
            signed_cell = signed_builder.end_cell()
            
            # Создаем внешнее сообщение (ExternalMessage)
            # Структура: (info, init?, body)
            external_builder = Builder()
            
            # info (ExtInMsgInfo)
            # Структура: (src, dest, import_fee)
            external_builder.store_bit(0)  # src = addr_extern (external)
            external_builder.store_address(None)  # src_addr = None (external)
            external_builder.store_address(PytoniqAddress(self.wallet_address))  # dest_addr
            
            # init (StateInit) - нужен только для uninit кошелька (seqno = 0)
            if seqno == 0:
                # Для uninit кошелька нужен StateInit
                # Но пока пропускаем, так как кошелек active (seqno = 1)
                external_builder.store_bit(0)  # no init
            else:
                external_builder.store_bit(0)  # no init
            
            # body
            external_builder.store_ref(signed_cell)  # body
            
            external_message = external_builder.end_cell()
            
            # Конвертируем в BOC base64
            # КРИТИЧЕСКИ ВАЖНО: используем pytoniq для правильной конвертации pytoniq_core Cell в pytoniq Cell
            # Проблема: pytoniq_core Cell не имеет метода to_boc_base64()
            # Решение: конвертируем через правильную сериализацию и используем pytoniq Cell.from_boc() + to_boc_base64()
            try:
                from pytoniq import Cell as PytoniqCell
                import base64 as base64_module
                
                # Собираем все cells рекурсивно
                def collect_cells(cell, cells_list):
                    """Собирает все cells рекурсивно в список"""
                    if cell in cells_list:
                        return
                    cells_list.append(cell)
                    try:
                        if hasattr(cell, 'refs'):
                            refs = cell.refs
                            if hasattr(refs, '__iter__') and not isinstance(refs, (str, bytes)):
                                for ref in refs:
                                    collect_cells(ref, cells_list)
                            elif hasattr(refs, '__getitem__'):
                                i = 0
                                while True:
                                    try:
                                        ref = refs[i]
                                        collect_cells(ref, cells_list)
                                        i += 1
                                    except (IndexError, KeyError, TypeError):
                                        break
                    except (AttributeError, TypeError):
                        pass
                
                cells_list = []
                collect_cells(external_message, cells_list)
                
                # Создаем indexes для всех cells
                indexes = {}
                for idx, cell in enumerate(cells_list):
                    indexes[cell] = idx
                
                # Сериализуем root cell с правильными indexes
                byte_len = 4
                cell_bytes = external_message.serialize(indexes=indexes, byte_len=byte_len)
                
                # Создаем правильный BOC формат вручную
                import struct
                
                # BOC magic bytes (правильный формат для TON)
                boc_magic = b'\xb5\xee\x9c\x72'
                
                # Flags: has_index (1 bit) + has_crc32c (1 bit) + has_cache_bits (1 bit) + flags (5 bits)
                # Для простого случая: 0b00000000 (no index, no crc32c, no cache bits)
                flags = 0b00000000
                
                # Size: количество bytes для индексов (обычно 4)
                size_bytes = 4
                
                # Количество root cells (обычно 1)
                root_count = 1
                
                # Количество всех cells
                total_cells = len(cells_list)
                
                # Вычисляем размер всех cells в байтах
                tot_cells_size = len(cell_bytes)
                
                # Создаем BOC заголовок
                boc_header = boc_magic
                boc_header += bytes([flags])
                boc_header += bytes([size_bytes])
                boc_header += struct.pack('>I', root_count)  # root count (big-endian, 4 bytes)
                boc_header += struct.pack('>I', total_cells)  # total cells (big-endian, 4 bytes)
                boc_header += struct.pack('>I', 0)  # absent cells (big-endian, 4 bytes)
                boc_header += struct.pack('>I', tot_cells_size)  # tot_cells_size (big-endian, 4 bytes)
                
                # Добавляем root cell index (обычно 0)
                boc_header += struct.pack('>I', 0)  # root cell index (big-endian, 4 bytes)
                
                # Добавляем сериализованные cells
                boc_bytes = boc_header + cell_bytes
                
                # КРИТИЧЕСКИ ВАЖНО: используем pytoniq Cell.from_boc() для правильной конвертации
                # Это создаст правильный pytoniq Cell из BOC bytes, который можно правильно сериализовать
                try:
                    # Пробуем создать pytoniq Cell из BOC bytes
                    pytoniq_cells = PytoniqCell.from_boc(boc_bytes)
                    if isinstance(pytoniq_cells, list):
                        pytoniq_cell = pytoniq_cells[0]
                    else:
                        pytoniq_cell = pytoniq_cells
                    
                    # Используем готовый метод to_boc_base64() из pytoniq Cell
                    boc_base64 = pytoniq_cell.to_boc_base64()
                    print(f"✅ Serialized BOC using pytoniq Cell.from_boc() + to_boc_base64() (proper conversion)", file=sys.stderr, flush=True)
                except Exception as conversion_error:
                    # Если конвертация не удалась, используем прямой base64
                    print(f"⚠️ Error converting via pytoniq: {conversion_error}, using direct base64", file=sys.stderr, flush=True)
                    boc_base64 = base64_module.b64encode(boc_bytes).decode('utf-8')
                    print(f"⚠️ Using direct base64 (may not work)", file=sys.stderr, flush=True)
                
            except Exception as boc_error:
                print(f"⚠️ Error creating BOC: {boc_error}, trying alternative method", file=sys.stderr, flush=True)
                import traceback
                print(f"❌ Traceback: {traceback.format_exc()}", file=sys.stderr, flush=True)
                raise Exception(f"Failed to create BOC: {boc_error}")
            
            print(f"✅ Created transaction manually (seqno={seqno})", file=sys.stderr, flush=True)
            return boc_base64
            
        except Exception as e:
            print(f"⚠️ Error creating transaction manually: {e}", file=sys.stderr, flush=True)
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}", file=sys.stderr, flush=True)
            raise Exception(f"Failed to create transaction manually: {e}")
    
    async def _send_raw_via_http(self, to_address: str, amount_nano: int, comment: str = None) -> str:
        """
        Отправка TON через HTTP API без прямого подключения к блокчейну.
        Создает и подписывает транзакцию локально, затем отправляет через HTTP.
        """
        if not self.seed_phrase:
            raise Exception("TON_WALLET_SEED is not set")
        
        # Получаем seqno через API
        print(f"🔄 Getting wallet seqno via HTTP API...", file=sys.stderr, flush=True)
        seqno = await self._get_seqno_via_api()
        print(f"✅ Seqno: {seqno}", file=sys.stderr, flush=True)
        
        # Очищаем и валидируем мнемонику
        cleaned_seed = self.seed_phrase.strip()
        while (cleaned_seed.startswith('"') and cleaned_seed.endswith('"')) or \
              (cleaned_seed.startswith("'") and cleaned_seed.endswith("'")):
            if cleaned_seed.startswith('"') and cleaned_seed.endswith('"'):
                cleaned_seed = cleaned_seed[1:-1].strip()
            if cleaned_seed.startswith("'") and cleaned_seed.endswith("'"):
                cleaned_seed = cleaned_seed[1:-1].strip()
        
        seed_words = [w.strip() for w in cleaned_seed.split() if w.strip()]
        if len(seed_words) != 24:
            raise Exception(f"Invalid mnemonic: expected 24 words, got {len(seed_words)}")
        
        # Создаем транзакцию вручную
        print(f"🔄 Creating transaction manually (no blockchain connection)...", file=sys.stderr, flush=True)
        if comment:
            print(f"📝 Adding comment to transaction: {comment}", file=sys.stderr, flush=True)
        try:
            boc_base64 = await self._create_wallet_transaction_manually(seed_words, to_address, amount_nano, seqno, comment)
            print(f"✅ Transaction created and signed manually", file=sys.stderr, flush=True)
            return await self._send_boc_via_http(boc_base64)
        except Exception as manual_error:
            print(f"⚠️ Manual transaction creation failed: {manual_error}", file=sys.stderr, flush=True)
            # Fallback на использование pytoniq (может потребовать подключения)
            raise Exception(f"Failed to create transaction manually: {manual_error}")
    
    async def _send_boc_via_http(self, boc_base64: str) -> str:
        """Отправляет подписанную транзакцию (BOC) через tonapi.io или toncenter.com API."""
        print(f"🔄 Sending transaction via HTTP API...", file=sys.stderr, flush=True)
        
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=connector
        ) as session:
            # Сначала пробуем tonapi.io (у нас есть TONAPI_KEY)
            if self.api_key:
                try:
                    # tonapi.io использует другой endpoint для отправки транзакций
                    # Пробуем через /v2/blockchain/message или используем toncenter.com через tonapi.io proxy
                    # Но проще использовать toncenter.com напрямую (он не требует API ключа для sendBoc)
                    print(f"🔄 Trying toncenter.com (no API key required for sendBoc)...", file=sys.stderr, flush=True)
                except Exception as tonapi_error:
                    print(f"⚠️ Error: {tonapi_error}", file=sys.stderr, flush=True)
            
            # Используем toncenter.com API
            # toncenter.com ожидает POST запрос с JSON body или form-data
            url = "https://toncenter.com/api/v2/sendBoc"
            
            # Пробуем POST с JSON body
            payload = {
                "boc": boc_base64
            }
            
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("ok"):
                        tx_hash = data.get("result", "")
                        print(f"✅ Transaction sent via toncenter.com! Hash: {tx_hash[:20]}...", file=sys.stderr, flush=True)
                        return tx_hash
                    else:
                        error_msg = data.get("error", "Unknown error")
                        raise Exception(f"TON Center API error: {error_msg}")
                else:
                    text = await resp.text()
                    raise Exception(f"TON Center API HTTP error: {resp.status} - {text}")
    
    async def _send_raw_via_api(self, to_address: str, amount_nano: int) -> str:
        """
        Альтернативный способ отправки через HTTP API.
        Пробует HTTP метод, если не получается - использует прямой метод.
        """
        try:
            return await self._send_raw_via_http(to_address, amount_nano)
        except Exception as http_error:
            print(f"⚠️ HTTP-based sending failed: {http_error}, trying direct method...", file=sys.stderr, flush=True)
            return await self._send_raw(to_address, amount_nano)
    
    async def _send_via_node(self, to_address: str, amount_nano: int, comment: str = None) -> str:
        """
        Отправка через Node-скрипт (ton_sender.js) с использованием @ton/ton (поддержка wallet v5r1).
        """
        base_dir = os.path.dirname(__file__)
        script_candidates = [
            os.path.normpath(os.path.join(base_dir, "..", "ton_sender.js")),            # /app/ton_sender.js (backend root)
            os.path.normpath(os.path.join(base_dir, "ton_sender.js")),                  # /app/app/ton_sender.js (same dir)
            os.path.normpath(os.path.join(base_dir, "..", "backend", "ton_sender.js")), # /app/backend/ton_sender.js (if repo root used)
        ]
        script_path = next((p for p in script_candidates if os.path.exists(p)), None)
        if not script_path:
            raise Exception(f"Node sender script not found. Tried: {script_candidates}")
        
        node_bin = shutil.which("node")
        if not node_bin:
            raise Exception("Node binary not found in PATH")
        
        cmd = [node_bin, script_path, "--to", to_address, "--amount", str(amount_nano)]
        if comment:
            cmd.extend(["--comment", str(comment)])
        
        env = os.environ.copy()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await proc.communicate()
        out_text = stdout.decode().strip()
        err_text = stderr.decode().strip()
        
        if proc.returncode != 0:
            raise Exception(f"Node sender failed (exit {proc.returncode}): {err_text or out_text}")
        
        try:
            data = json.loads(out_text)
        except Exception as parse_error:
            raise Exception(f"Failed to parse node sender output: {parse_error}. Raw: {out_text}")
        
        if not data.get("ok"):
            raise Exception(f"Node sender error: {data.get('error') or out_text}")
        
        tx_hash = data.get("txHash") or data.get("hash") or data.get("tx_hash")
        if not tx_hash:
            raise Exception(f"Node sender returned no tx_hash. Raw: {out_text}")
        
        return tx_hash
    
    async def _send_raw(self, to_address: str, amount_nano: int, comment: str = None) -> str:
        """
        Отправка TON. Возвращает tx_hash.
        Сначала пробует Node-отправку через @ton/ton (wallet v5r1), затем fallback на HTTP/manual.
        """
        # 1) Пробуем отправить через Node (@ton/ton) — новый подход
        try:
            print(f"🚀 Using Node sender (@ton/ton) with wallet v5r1 support...", file=sys.stderr, flush=True)
            return await self._send_via_node(to_address, amount_nano, comment)
        except Exception as node_error:
            print(f"⚠️ Node sender failed: {node_error}, falling back to HTTP/manual BOC", file=sys.stderr, flush=True)
        
        # 2) Fallback: старый HTTP/manual путь
        print(f"🚀 Using HTTP-based transaction sending (fallback)...", file=sys.stderr, flush=True)
        return await self._send_raw_via_http(to_address, amount_nano, comment)

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

        # Создаем запись о транзакции БЕЗ списания средств
        tx = models.TonTransaction(
            user_id=user.id,
            to_address=to_address,
            amount_nano=amount_nano,
            status="pending",
            idempotency_key=key,
        )
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
            
            # Создаем комментарий с Telegram ID пользователя
            comment = str(telegram_id)
            print(f"📝 Adding comment to transaction: Telegram ID {telegram_id}", file=sys.stderr, flush=True)
            
            # Отправка транзакции с несколькими попытками
            # ВАЖНО: Средства списываются ТОЛЬКО после успешной отправки (получения tx_hash)
            max_retries = 3
            last_error = None
            tx_hash = None
            
            for attempt in range(1, max_retries + 1):
                try:
                    print(f"🔄 Attempt {attempt}/{max_retries} to send transaction...", file=sys.stderr, flush=True)
                    tx_hash = await self._send_raw(to_address, int(amount_nano), comment)
                    # ТОЛЬКО после успешной отправки списываем средства
                    balance.ton_active_balance -= amount_nano
                    tx.tx_hash = tx_hash
                    tx.status = "pending"
                    db.commit()
                    db.refresh(tx)
                    print(f"✅ Transaction sent successfully on attempt {attempt}. Funds deducted from balance.", file=sys.stderr, flush=True)
                    break  # Успешно отправили
                except Exception as send_error:
                    last_error = send_error
                    error_msg = str(send_error)
                    print(f"⚠️ Attempt {attempt} failed: {error_msg}", file=sys.stderr, flush=True)
                    
                    # Если это не таймаут, не повторяем
                    if "timeout" not in error_msg.lower() and "connection" not in error_msg.lower():
                        raise
                    
                    # Если это последняя попытка - транзакция не отправлена, средства НЕ списывались
                    if attempt == max_retries:
                        print(f"⚠️ All {max_retries} attempts failed. Transaction not sent, funds NOT deducted.", file=sys.stderr, flush=True)
                        tx.status = "failed"
                        tx.error_message = f"All {max_retries} send attempts failed: {error_msg[:200]}. Transaction not sent, funds remain on balance."
                        db.commit()
                        db.refresh(tx)
                        # Возвращаем транзакцию, но не выбрасываем ошибку - средства не списывались
                        return tx, True
                    
                    # Ждем перед следующей попыткой
                    await asyncio.sleep(2)
            
            # Если не получили tx_hash после всех попыток - транзакция не отправлена
            if not tx_hash:
                tx.status = "failed"
                tx.error_message = f"Transaction not sent after {max_retries} attempts. Funds remain on balance."
                db.commit()
                db.refresh(tx)
                return tx, True
                
        except HTTPException:
            # Пробрасываем HTTPException как есть
            # Средства не списывались, так что просто удаляем транзакцию или помечаем как failed
            tx.status = "failed"
            tx.error_message = "Transaction validation failed. Funds not deducted."
            db.commit()
            raise
        except Exception as exc:
            # Ошибка при отправке - средства НЕ списывались
            error_msg = str(exc)
            error_trace = traceback.format_exc()
            print(f"❌ Ошибка при выводе средств: {error_msg}", file=sys.stderr, flush=True)
            print(f"❌ Traceback: {error_trace}", file=sys.stderr, flush=True)
            
            tx.status = "failed"
            tx.error_message = f"Transaction failed: {error_msg[:500]}. Funds NOT deducted."
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
                        
                        # Убрано логирование каждого запроса - это нормальный процесс поиска правильного endpoint
                        
                        try:
                            async with session.get(url, headers=headers, params=params) as resp:
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
                                    # 404 - это нормально, просто этот endpoint не поддерживает такой формат адреса
                                    # Не логируем, чтобы не пугать пользователя
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
    
    async def process_pending_withdrawals(self, db: Session):
        """
        Обрабатывает pending транзакции вывода, которые не удалось отправить сразу.
        Пробует отправить их снова. Средства списываются ТОЛЬКО после успешной отправки.
        """
        from app.models import TonTransaction
        import sys
        from datetime import datetime, timedelta
        
        # Находим все pending транзакции без tx_hash (средства еще не списаны)
        pending_txs = db.query(TonTransaction).filter(
            TonTransaction.status == "pending",
            TonTransaction.tx_hash.is_(None)
        ).limit(10).all()  # Обрабатываем максимум 10 за раз
        
        if not pending_txs:
            return
        
        print(f"🔄 Processing {len(pending_txs)} pending withdrawal transactions (funds not deducted yet)...", file=sys.stderr, flush=True)
        
        for tx in pending_txs:
            try:
                # Проверяем, сколько времени прошло с момента создания транзакции
                time_since_creation = datetime.utcnow() - (tx.created_at.replace(tzinfo=None) if tx.created_at and tx.created_at.tzinfo else tx.created_at) if tx.created_at else timedelta(0)
                max_wait_time = timedelta(minutes=10)  # Максимальное время ожидания - 10 минут
                
                # Если транзакция слишком старая и все еще не отправлена - помечаем как failed
                # Средства НЕ списывались, так что возвращать нечего
                if time_since_creation > max_wait_time:
                    print(f"⚠️ Transaction {tx.id} is too old ({time_since_creation}), marking as failed (funds were never deducted).", file=sys.stderr, flush=True)
                    tx.status = "failed"
                    tx.error_message = f"Transaction failed: could not send after {time_since_creation}. Funds were never deducted."
                    db.commit()
                    continue
                
                # Получаем пользователя для комментария
                user = None
                comment = None
                if tx.user_id:
                    user = db.query(models.User).filter(models.User.id == tx.user_id).first()
                    if user:
                        comment = str(user.telegram_id)
                
                # Пробуем отправить транзакцию
                print(f"🔄 Attempting to send pending transaction {tx.id}...", file=sys.stderr, flush=True)
                tx_hash = await self._send_raw(tx.to_address, int(tx.amount_nano), comment)
                
                # ТОЛЬКО после успешной отправки списываем средства
                if tx.user_id and user:
                    balance = db.query(models.UserBalance).filter(
                        models.UserBalance.user_id == user.id
                    ).first()
                    if balance:
                        balance.ton_active_balance -= tx.amount_nano
                        print(f"✅ Funds deducted from balance after successful send: {float(tx.amount_nano) / 10**9:.4f} TON", file=sys.stderr, flush=True)
                
                tx.tx_hash = tx_hash
                tx.status = "pending"  # Остается pending до подтверждения
                tx.error_message = None  # Очищаем ошибку
                db.commit()
                print(f"✅ Pending transaction {tx.id} sent successfully! Hash: {tx_hash[:20]}...", file=sys.stderr, flush=True)
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ Failed to send pending transaction {tx.id}: {error_msg}", file=sys.stderr, flush=True)
                
                # Подсчитываем количество попыток по error_message
                attempt_count = tx.error_message.count("attempt") if tx.error_message else 0
                max_auto_attempts = 5  # Максимум автоматических попыток
                
                # Проверяем время с момента создания
                time_since_creation = datetime.utcnow() - (tx.created_at.replace(tzinfo=None) if tx.created_at and tx.created_at.tzinfo else tx.created_at) if tx.created_at else timedelta(0)
                max_wait_time = timedelta(minutes=10)
                
                # Если попыток слишком много или транзакция слишком старая - помечаем как failed
                # Средства НЕ списывались, так что возвращать нечего
                if attempt_count >= max_auto_attempts or time_since_creation > max_wait_time:
                    print(f"⚠️ Too many failed attempts ({attempt_count}) or too old transaction {tx.id}, marking as failed (funds were never deducted).", file=sys.stderr, flush=True)
                    tx.status = "failed"
                    tx.error_message = f"Transaction failed after {attempt_count + 1} attempts: {error_msg[:200]}. Funds were never deducted."
                    db.commit()
                else:
                    # Обновляем error_message с информацией о попытке
                    new_error = f"Attempt {attempt_count + 1} failed: {error_msg[:200]}"
                    if tx.error_message:
                        tx.error_message = f"{tx.error_message}; {new_error}"
                    else:
                        tx.error_message = new_error
                    db.commit()
                # Продолжаем обработку других транзакций
    
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

