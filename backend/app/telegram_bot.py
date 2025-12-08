"""
Telegram Bot для BlackMirrowMarket
Пока базовая структура, будет расширена для валидации заданий
"""
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_BOT_TOKEN = os.getenv("TELEGRAM_ADMIN_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "Добро пожаловать в BlackMirrowMarket!\n\n"
        "Используйте Mini App для работы с платформой."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text(
        "BlackMirrowMarket - маркетплейс микро-задач\n\n"
        "Команды:\n"
        "/start - Начать работу\n"
        "/help - Показать справку"
    )

def setup_bot(token: str):
    """Настройка и запуск бота"""
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    return application

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("Ошибка: TELEGRAM_BOT_TOKEN не установлен")
        exit(1)
    
    app = setup_bot(TELEGRAM_BOT_TOKEN)
    print("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)




