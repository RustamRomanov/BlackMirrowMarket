"""
Скрипт для первоначальной авторизации Telegram клиента
Запустите этот скрипт один раз локально для создания сессии
"""
import asyncio
import os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

load_dotenv()

async def main():
    api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash = os.getenv("TELEGRAM_API_HASH", "")
    phone = os.getenv("TELEGRAM_PHONE", "")
    
    if not api_id or not api_hash or not phone:
        print("❌ Ошибка: TELEGRAM_API_ID, TELEGRAM_API_HASH и TELEGRAM_PHONE должны быть установлены в .env")
        return
    
    print(f"📱 Подключение к Telegram для номера {phone}...")
    client = TelegramClient('comment_validator_session', api_id, api_hash)
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            print("📨 Отправка кода подтверждения...")
            await client.send_code_request(phone)
            code = input('Введите код из Telegram: ')
            
            try:
                await client.sign_in(phone, code)
                print("✅ Авторизация успешна!")
            except SessionPasswordNeededError:
                password = input('Введите пароль 2FA (если включен): ')
                await client.sign_in(password=password)
                print("✅ Авторизация с 2FA успешна!")
        else:
            print("✅ Уже авторизован!")
        
        # Проверяем подключение
        me = await client.get_me()
        print(f"✅ Подключен как: {me.first_name} (@{me.username})")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await client.disconnect()
        print("📁 Сессия сохранена в файл comment_validator_session.session")
        print("💡 Теперь можно загрузить этот файл на сервер (Railway)")

if __name__ == '__main__':
    asyncio.run(main())
