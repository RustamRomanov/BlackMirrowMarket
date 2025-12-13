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
    
    Бот @BlackMirrowAdminBot должен быть администратором канала для проверки комментариев.
    Использует Telegram Bot API для проверки комментариев к посту через getUpdates.
    
    Args:
        bot: Экземпляр Telegram Bot (@BlackMirrowAdminBot)
        post_link: Ссылка на пост (например, https://t.me/channel/123)
        user_telegram_id: Telegram ID пользователя
    
    Returns:
        True если комментарий найден, False если нет
    """
    try:
        # Парсим ссылку на пост
        message_id = None
        chat_id = None
        
        if '/c/' in post_link:
            # Приватный канал: https://t.me/c/3503023298/3
            parts = post_link.replace('https://t.me/c/', '').split('/')
            if len(parts) >= 2:
                # Для приватных каналов используем chat_id напрямую
                chat_id = int(parts[0])
                message_id = int(parts[1])
        else:
            # Публичный канал: https://t.me/channel/123
            parts = post_link.replace('https://t.me/', '').split('/')
            if len(parts) >= 2:
                channel_username = parts[0]
                message_id = int(parts[1])
                # Для публичных каналов используем @username
                chat_id = f"@{channel_username}"
        
        if not message_id or not chat_id:
            print(f"[COMMENT VALIDATOR] Could not parse post_link: {post_link}")
            return False
        
        # Получаем обновления через getUpdates
        # Бот должен получать обновления о комментариях в канале
        try:
            # Получаем больше обновлений для более надежной проверки
            updates = await bot.get_updates(
                offset=-500,  # Получаем последние 500 обновлений для более надежной проверки
                timeout=15,
                allowed_updates=['message']
            )
            
            # Ищем комментарии к нужному сообщению
            for update in updates:
                if update.message:
                    # Проверяем, что сообщение из нужного чата
                    msg_chat_id = update.message.chat.id if hasattr(update.message.chat, 'id') else None
                    msg_chat_username = update.message.chat.username if hasattr(update.message.chat, 'username') else None
                    
                    # Проверяем соответствие чата
                    chat_matches = False
                    if isinstance(chat_id, int):
                        chat_matches = (msg_chat_id == chat_id)
                    elif isinstance(chat_id, str) and chat_id.startswith('@'):
                        chat_matches = (msg_chat_username == chat_id[1:])
                    
                    if not chat_matches:
                        continue
                    
                    # Проверяем, является ли это комментарием к нужному посту
                    if update.message.reply_to_message:
                        reply_msg = update.message.reply_to_message
                        # Проверяем, что это ответ на нужное сообщение
                        if reply_msg.message_id == message_id:
                            # Проверяем, что комментарий от нужного пользователя
                            if update.message.from_user and update.message.from_user.id == user_telegram_id:
                                print(f"[COMMENT VALIDATOR] Comment found for user {user_telegram_id} on post {message_id} in chat {chat_id}")
                                return True
                    
                    # Также проверяем, если сообщение содержит ссылку на пост
                    if update.message.text and post_link in update.message.text:
                        if update.message.from_user and update.message.from_user.id == user_telegram_id:
                            print(f"[COMMENT VALIDATOR] Comment with post link found for user {user_telegram_id}")
                            return True
            
            print(f"[COMMENT VALIDATOR] Comment not found in recent updates for user {user_telegram_id} on post {message_id} in chat {chat_id}")
            return False
            
        except Exception as e:
            print(f"[COMMENT VALIDATOR] Error checking comment via Bot API: {e}")
            return False
        
    except Exception as e:
        print(f"[COMMENT VALIDATOR] Error checking comment: {e}")
        return False

async def check_subscription_exists(bot: Bot, channel_username: str, user_telegram_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на канал.
    
    Бот @BlackMirrowAdminBot должен быть администратором канала для проверки подписки.
    Использует Telegram Bot API метод get_chat_member.
    
    Args:
        bot: Экземпляр Telegram Bot (@BlackMirrowAdminBot)
        channel_username: Username канала (например, @channel или channel_id для приватных)
        user_telegram_id: Telegram ID пользователя
    
    Returns:
        True если пользователь подписан, False если нет
    """
    try:
        # Определяем chat_id
        if channel_username.startswith('@'):
            chat_id = channel_username
        else:
            # Если это числовой ID (приватный канал)
            try:
                chat_id = int(channel_username)
            except ValueError:
                chat_id = f"@{channel_username}"
        
        # Получаем информацию о члене чата
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_telegram_id)
            
            # Проверяем статус подписки
            # Статусы: member, administrator, creator, left, kicked, restricted
            if member.status in ['member', 'administrator', 'creator']:
                print(f"[COMMENT VALIDATOR] User {user_telegram_id} is subscribed to {chat_id}")
                return True
            else:
                print(f"[COMMENT VALIDATOR] User {user_telegram_id} is not subscribed to {chat_id} (status: {member.status})")
                return False
                
        except Exception as e:
            print(f"[COMMENT VALIDATOR] Error getting chat member: {e}")
            # Если бот не админ или нет доступа, возвращаем False
            return False
            
    except Exception as e:
        print(f"[COMMENT VALIDATOR] Error checking subscription: {e}")
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

async def validate_subscription_task(user_task_id: int, db: Session):
    """
    Валидирует подписку для задания и переводит средства из эскроу на баланс.
    
    Args:
        user_task_id: ID записи UserTask
        db: Сессия базы данных
    """
    user_task = db.query(models.UserTask).filter(models.UserTask.id == user_task_id).first()
    if not user_task or user_task.status != models.UserTaskStatus.IN_PROGRESS:
        return
    
    task = db.query(models.Task).filter(models.Task.id == user_task.task_id).first()
    if not task or task.task_type != models.TaskType.SUBSCRIPTION:
        return
    
    user = db.query(models.User).filter(models.User.id == user_task.user_id).first()
    if not user:
        return
    
    if not TELEGRAM_ADMIN_BOT_TOKEN:
        print(f"[COMMENT VALIDATOR] TELEGRAM_ADMIN_BOT_TOKEN not set, skipping validation")
        return
    
    bot = Bot(token=TELEGRAM_ADMIN_BOT_TOKEN)
    channel_id = task.telegram_channel_id  # Для подписок здесь хранится channel_id или @username
    
    # Проверяем наличие подписки
    subscription_exists = await check_subscription_exists(bot, channel_id, user.telegram_id)
    
    if subscription_exists:
        # Подписка найдена - переводим средства из эскроу на баланс
        from app.database_optimizations import update_balance_safely
        
        # Вычитаем 10% комиссию приложения
        def deduct_app_commission(user_id: int, reward_ton: Decimal, db: Session) -> Decimal:
            app_commission = reward_ton * Decimal("0.10")
            user_reward = reward_ton - app_commission
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
        print(f"[COMMENT VALIDATOR] Subscription validated for user_task {user_task_id}, funds transferred")
    else:
        print(f"[COMMENT VALIDATOR] Subscription not found for user_task {user_task_id}")

async def check_subscription_periodically(user_task_id: int, db: Session):
    """
    Периодически проверяет подписку (раз в день в течение 7 дней).
    Если подписка отменена - банит пользователя и списывает средства.
    
    Args:
        user_task_id: ID записи UserTask
        db: Сессия базы данных
    """
    user_task = db.query(models.UserTask).filter(models.UserTask.id == user_task_id).first()
    if not user_task:
        return
    
    # Проверяем, прошло ли меньше 7 дней с момента валидации
    if not user_task.validated_at:
        return
    
    time_since_validation = datetime.utcnow() - user_task.validated_at.replace(tzinfo=None) if user_task.validated_at.tzinfo else user_task.validated_at
    
    if time_since_validation > timedelta(days=7):
        # Прошло больше 7 дней - прекращаем проверку
        return
    
    task = db.query(models.Task).filter(models.Task.id == user_task.task_id).first()
    if not task or task.task_type != models.TaskType.SUBSCRIPTION:
        return
    
    user = db.query(models.User).filter(models.User.id == user_task.user_id).first()
    if not user:
        return
    
    if not TELEGRAM_ADMIN_BOT_TOKEN:
        return
    
    bot = Bot(token=TELEGRAM_ADMIN_BOT_TOKEN)
    channel_id = task.telegram_channel_id
    
    # Проверяем наличие подписки
    subscription_exists = await check_subscription_exists(bot, channel_id, user.telegram_id)
    
    if not subscription_exists:
        # Подписка отменена - баним пользователя и списываем средства
        from app.database_optimizations import update_balance_safely
        
        # Списываем средства с баланса пользователя
        balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
        if balance:
            if balance.ton_active_balance >= user_task.reward_ton:
                update_balance_safely(db, user.id, -user_task.reward_ton, "active")
            else:
                update_balance_safely(db, user.id, -balance.ton_active_balance, "active")
        
        # Баним пользователя на 7 дней
        user.is_banned = True
        user.ban_until = datetime.utcnow() + timedelta(days=7)
        user.ban_reason = "Отменена подписка после валидации"
        
        # Обновляем статус задания
        user_task.status = models.UserTaskStatus.FAILED
        user_task.validation_result = False
        
        db.commit()
        print(f"[COMMENT VALIDATOR] Subscription cancelled for user_task {user_task_id}, user {user.telegram_id} banned for 7 days")

async def check_all_comment_tasks():
    """
    Проверяет все задания с комментариями и подписками, которые находятся в статусе IN_PROGRESS или COMPLETED.
    """
    db = SessionLocal()
    try:
        # Находим все задания с комментариями в статусе IN_PROGRESS
        in_progress_comment_tasks = db.query(models.UserTask).join(models.Task).filter(
            and_(
                models.Task.task_type == models.TaskType.COMMENT,
                models.UserTask.status == models.UserTaskStatus.IN_PROGRESS
            )
        ).all()
        
        for user_task in in_progress_comment_tasks:
            await validate_comment_task(user_task.id, db)
        
        # Находим все задания с подписками в статусе IN_PROGRESS
        in_progress_subscription_tasks = db.query(models.UserTask).join(models.Task).filter(
            and_(
                models.Task.task_type == models.TaskType.SUBSCRIPTION,
                models.UserTask.status == models.UserTaskStatus.IN_PROGRESS
            )
        ).all()
        
        for user_task in in_progress_subscription_tasks:
            await validate_subscription_task(user_task.id, db)
        
        # Находим все задания с комментариями в статусе COMPLETED (для периодической проверки - каждые 5 минут в течение часа)
        completed_comment_tasks = db.query(models.UserTask).join(models.Task).filter(
            and_(
                models.Task.task_type == models.TaskType.COMMENT,
                models.UserTask.status == models.UserTaskStatus.COMPLETED,
                models.UserTask.validated_at.isnot(None)
            )
        ).all()
        
        for user_task in completed_comment_tasks:
            await check_comment_periodically(user_task.id, db)
        
        # Находим все задания с подписками в статусе COMPLETED (для периодической проверки - раз в день в течение 7 дней)
        completed_subscription_tasks = db.query(models.UserTask).join(models.Task).filter(
            and_(
                models.Task.task_type == models.TaskType.SUBSCRIPTION,
                models.UserTask.status == models.UserTaskStatus.COMPLETED,
                models.UserTask.validated_at.isnot(None)
            )
        ).all()
        
        for user_task in completed_subscription_tasks:
            await check_subscription_periodically(user_task.id, db)
            
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

async def run_subscription_checker_daily():
    """
    Запускает ежедневную проверку подписок (раз в день).
    """
    while True:
        try:
            await asyncio.sleep(86400)  # 24 часа (1 день)
            db = SessionLocal()
            try:
                # Находим все задания с подписками в статусе COMPLETED
                completed_subscription_tasks = db.query(models.UserTask).join(models.Task).filter(
                    and_(
                        models.Task.task_type == models.TaskType.SUBSCRIPTION,
                        models.UserTask.status == models.UserTaskStatus.COMPLETED,
                        models.UserTask.validated_at.isnot(None)
                    )
                ).all()
                
                for user_task in completed_subscription_tasks:
                    await check_subscription_periodically(user_task.id, db)
            finally:
                db.close()
        except Exception as e:
            print(f"[COMMENT VALIDATOR] Error in daily subscription check: {e}")
            await asyncio.sleep(3600)  # При ошибке ждем час

