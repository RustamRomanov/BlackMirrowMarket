"""
Модуль для проверки комментариев в Telegram через Bot API
"""
import os
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from telegram import Bot
from telegram.error import TelegramError
from app.database import SessionLocal
from app import models
from decimal import Decimal

TELEGRAM_ADMIN_BOT_TOKEN = os.getenv("TELEGRAM_ADMIN_BOT_TOKEN")

async def check_comment_exists(bot: Bot, post_link: str, user_telegram_id: int) -> bool:
    """
    Проверяет, существует ли комментарий пользователя под постом.
    
    ВАЖНО: Telegram Bot API не предоставляет прямой метод для получения комментариев к посту в канале.
    Для проверки комментариев нужно использовать один из следующих подходов:
    1. Использовать Telegram Client API (MTProto) - требует дополнительных библиотек
    2. Попросить пользователя переслать комментарий боту
    3. Использовать уникальный идентификатор в комментарии
    
    Текущая реализация использует упрощенный подход через getUpdates.
    В продакшене рекомендуется использовать более надежный метод.
    
    Args:
        bot: Экземпляр Telegram Bot
        post_link: Ссылка на пост (например, https://t.me/channel/123)
        user_telegram_id: Telegram ID пользователя
    
    Returns:
        True если комментарий найден, False если нет
    """
    try:
        # Парсим ссылку на пост
        message_id = None
        channel_username = None
        channel_id = None
        
        if '/c/' in post_link:
            # Приватный канал: https://t.me/c/3503023298/3
            parts = post_link.replace('https://t.me/c/', '').split('/')
            if len(parts) >= 2:
                channel_id = parts[0]
                message_id = int(parts[1])
        else:
            # Публичный канал: https://t.me/channel/123
            parts = post_link.replace('https://t.me/', '').split('/')
            if len(parts) >= 2:
                channel_username = parts[0]
                message_id = int(parts[1])
        
        if not message_id:
            print(f"[COMMENT VALIDATOR] Could not parse message_id from post_link: {post_link}")
            return False
        
        # Пытаемся получить обновления через getUpdates
        # ВАЖНО: getUpdates возвращает только новые обновления, поэтому этот метод не очень надежен
        # Для более надежной проверки нужно использовать webhook или другой подход
        
        try:
            # Получаем последние обновления
            updates = await bot.get_updates(offset=-10, timeout=5, allowed_updates=['message'])
            
            # Ищем комментарии к нужному сообщению
            for update in updates:
                if update.message:
                    # Проверяем, является ли это комментарием к нужному посту
                    if update.message.reply_to_message:
                        if update.message.reply_to_message.message_id == message_id:
                            # Проверяем, что комментарий от нужного пользователя
                            if update.message.from_user and update.message.from_user.id == user_telegram_id:
                                print(f"[COMMENT VALIDATOR] Comment found for user {user_telegram_id} on post {message_id}")
                                return True
                    
                    # Также проверяем, если сообщение содержит ссылку на пост
                    if update.message.text and post_link in update.message.text:
                        if update.message.from_user and update.message.from_user.id == user_telegram_id:
                            print(f"[COMMENT VALIDATOR] Comment with post link found for user {user_telegram_id}")
                            return True
        except Exception as e:
            print(f"[COMMENT VALIDATOR] Error getting updates: {e}")
        
        # ВАЖНО: В текущей реализации мы не можем надежно проверить комментарии через Bot API
        # Для продакшена рекомендуется использовать другой подход:
        # 1. Попросить пользователя переслать комментарий боту
        # 2. Использовать уникальный идентификатор в комментарии
        # 3. Использовать Telegram Client API (MTProto)
        
        # Временно возвращаем False, так как надежная проверка невозможна через Bot API
        print(f"[COMMENT VALIDATOR] Comment not found for user {user_telegram_id} on post {message_id} (Bot API limitation)")
        return False
        
    except Exception as e:
        print(f"[COMMENT VALIDATOR] Error checking comment: {e}")
        return False

async def validate_comment_task(user_task_id: int, db: Session):
    """
    Валидирует комментарий для задания и переводит средства из эскроу на баланс.
    
    Args:
        user_task_id: ID записи UserTask
        db: Сессия базы данных
    """
    user_task = db.query(models.UserTask).filter(models.UserTask.id == user_task_id).first()
    if not user_task or user_task.status != models.UserTaskStatus.IN_PROGRESS:
        return
    
    task = db.query(models.Task).filter(models.Task.id == user_task.task_id).first()
    if not task or task.task_type != models.TaskType.COMMENT:
        return
    
    user = db.query(models.User).filter(models.User.id == user_task.user_id).first()
    if not user:
        return
    
    if not TELEGRAM_ADMIN_BOT_TOKEN:
        print(f"[COMMENT VALIDATOR] TELEGRAM_ADMIN_BOT_TOKEN not set, skipping validation")
        return
    
    bot = Bot(token=TELEGRAM_ADMIN_BOT_TOKEN)
    post_link = task.telegram_channel_id  # Для комментариев ссылка хранится здесь
    
    # Проверяем наличие комментария
    comment_exists = await check_comment_exists(bot, post_link, user.telegram_id)
    
    if comment_exists:
        # Комментарий найден - переводим средства из эскроу на баланс
        from app.database_optimizations import update_balance_safely
        
        # Вычитаем 10% комиссию приложения
        def deduct_app_commission(user_id: int, reward_ton: Decimal, db: Session) -> Decimal:
            app_commission = reward_ton * Decimal("0.10")
            user_reward = reward_ton - app_commission
            
            # Начисляем комиссию на баланс приложения (сервисный кошелек)
            # Здесь можно добавить логику начисления на сервисный кошелек
            return user_reward
        
        user_reward = deduct_app_commission(user.id, user_task.reward_ton, db)
        
        # Переводим средства из эскроу в активный баланс
        update_balance_safely(db, user.id, -user_task.reward_ton, "escrow")
        update_balance_safely(db, user.id, user_reward, "active")
        
        # Обновляем статус задания
        user_task.status = models.UserTaskStatus.COMPLETED
        user_task.validated_at = datetime.utcnow()
        user_task.validation_result = True
        
        # Начисляем 5% рефереру
        from app.routers.tasks import add_referral_commission
        add_referral_commission(user.id, user_task.reward_ton, db)
        
        # Обновляем счетчик выполненных слотов
        task.completed_slots += 1
        
        db.commit()
        print(f"[COMMENT VALIDATOR] Comment validated for user_task {user_task_id}, funds transferred")
    else:
        print(f"[COMMENT VALIDATOR] Comment not found for user_task {user_task_id}")

async def check_comment_periodically(user_task_id: int, db: Session):
    """
    Периодически проверяет комментарий (каждые 5 минут в течение часа).
    Если комментарий удален - банит пользователя и списывает средства.
    
    Args:
        user_task_id: ID записи UserTask
        db: Сессия базы данных
    """
    user_task = db.query(models.UserTask).filter(models.UserTask.id == user_task_id).first()
    if not user_task:
        return
    
    # Проверяем, прошло ли меньше часа с момента валидации
    if not user_task.validated_at:
        return
    
    time_since_validation = datetime.utcnow() - user_task.validated_at.replace(tzinfo=None) if user_task.validated_at.tzinfo else user_task.validated_at
    
    if time_since_validation > timedelta(hours=1):
        # Прошло больше часа - прекращаем проверку
        return
    
    task = db.query(models.Task).filter(models.Task.id == user_task.task_id).first()
    if not task or task.task_type != models.TaskType.COMMENT:
        return
    
    user = db.query(models.User).filter(models.User.id == user_task.user_id).first()
    if not user:
        return
    
    if not TELEGRAM_ADMIN_BOT_TOKEN:
        return
    
    bot = Bot(token=TELEGRAM_ADMIN_BOT_TOKEN)
    post_link = task.telegram_channel_id
    
    # Проверяем наличие комментария
    comment_exists = await check_comment_exists(bot, post_link, user.telegram_id)
    
    if not comment_exists:
        # Комментарий удален - баним пользователя и списываем средства
        from app.database_optimizations import update_balance_safely
        
        # Списываем средства с баланса пользователя на счет приложения
        # ВАЖНО: Средства списываются с активного баланса, но нужно убедиться, что баланс достаточен
        balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
        if balance:
            # Списываем средства (если баланс достаточен)
            if balance.ton_active_balance >= user_task.reward_ton:
                update_balance_safely(db, user.id, -user_task.reward_ton, "active")
                # Средства списываются с баланса пользователя (не начисляются на счет приложения явно)
                # Можно добавить логику начисления на сервисный кошелек, если нужно
            else:
                # Если баланс недостаточен, списываем все что есть
                update_balance_safely(db, user.id, -balance.ton_active_balance, "active")
        
        # Баним пользователя на 7 дней
        user.is_banned = True
        user.ban_until = datetime.utcnow() + timedelta(days=7)
        user.ban_reason = "Удален комментарий после валидации"
        
        # Обновляем статус задания
        user_task.status = models.UserTaskStatus.FAILED
        user_task.validation_result = False
        
        db.commit()
        print(f"[COMMENT VALIDATOR] Comment deleted for user_task {user_task_id}, user {user.telegram_id} banned for 7 days")

async def check_all_comment_tasks():
    """
    Проверяет все задания с комментариями, которые находятся в статусе IN_PROGRESS или COMPLETED.
    """
    db = SessionLocal()
    try:
        # Находим все задания с комментариями в статусе IN_PROGRESS
        in_progress_tasks = db.query(models.UserTask).join(models.Task).filter(
            and_(
                models.Task.task_type == models.TaskType.COMMENT,
                models.UserTask.status == models.UserTaskStatus.IN_PROGRESS
            )
        ).all()
        
        for user_task in in_progress_tasks:
            await validate_comment_task(user_task.id, db)
        
        # Находим все задания с комментариями в статусе COMPLETED (для периодической проверки)
        completed_tasks = db.query(models.UserTask).join(models.Task).filter(
            and_(
                models.Task.task_type == models.TaskType.COMMENT,
                models.UserTask.status == models.UserTaskStatus.COMPLETED,
                models.UserTask.validated_at.isnot(None)
            )
        ).all()
        
        for user_task in completed_tasks:
            await check_comment_periodically(user_task.id, db)
            
    finally:
        db.close()

async def run_comment_checker_periodically():
    """
    Запускает периодическую проверку комментариев (каждые 5 минут).
    """
    while True:
        try:
            await asyncio.sleep(300)  # 5 минут
            await check_all_comment_tasks()
        except Exception as e:
            print(f"[COMMENT VALIDATOR] Error in periodic check: {e}")
            await asyncio.sleep(60)  # При ошибке ждем минуту

