#!/usr/bin/env python3
"""
Скрипт для запуска Telegram бота отдельно
Используется для запуска бота через polling
"""
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем путь к app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.telegram_bot import setup_bot, TELEGRAM_BOT_TOKEN

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Ошибка: TELEGRAM_BOT_TOKEN не установлен")
        print("Установите переменную окружения TELEGRAM_BOT_TOKEN")
        sys.exit(1)
    
    print("🤖 Запуск Telegram бота...")
    print(f"✅ Токен найден: {TELEGRAM_BOT_TOKEN[:10]}...")
    
    app = setup_bot(TELEGRAM_BOT_TOKEN)
    print("✅ Бот настроен и запущен!")
    print("📱 Бот готов к работе. Нажмите Ctrl+C для остановки.")
    
    try:
        app.run_polling(allowed_updates=["message", "callback_query"])
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
        app.stop()
        print("✅ Бот остановлен")

