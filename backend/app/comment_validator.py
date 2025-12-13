"""
Модуль для автоматической проверки комментариев через Telegram Bot API
"""
import os
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_
from telegram import Bot
from telegram.error import TelegramError

from app.models import UserTask, UserTaskStatus, Task, TaskType, User, UserBalance
from app.routers.tasks import deduct_app_commission, add_referral_commission

TELEGRAM_ADMIN_BOT_TOKEN = os.getenv("TELEGRAM_ADMIN_BOT_TOKEN")


async def check_comment_exists(bot: Bot, channel_username: str, post_id: int, user_telegram_id: int) -> bool:
    """
    Проверяет, оставил ли пользователь комментарий под постом.
    
    Примечание: Telegram Bot API не позволяет напрямую получать комментарии к постам.
    Для полноценной работы нужен Telegram Client API (MTProto) через telethon или pyrogram.
    Пока возвращаем False - требуется реализация через MTProto.
    """
    try:
        # TODO: Реализовать через telethon или pyrogram для проверки комментариев
        # Временная заглушка
        return False
    except Exception as e:
        print(f"❌ Ошибка при проверке комментария: {e}", flush=True)
        return False


async def validate_comment_task(user_task: UserTask, task: Task, user: User, db: Session) -> bool:
    """Валидирует комментарий и переводит средства из эскроу в активный баланс."""
    if not TELEGRAM_ADMIN_BOT_TOKEN:
        return False
    
    try:
        bot = Bot(token=TELEGRAM_ADMIN_BOT_TOKEN)
        
        post_url = task.telegram_post_id
        if not post_url:
            return False
        
        channel_username = None
        post_id = None
        
        if "t.me/" in post_url:
            parts = post_url.split("t.me/")[1].split("/")
            if len(parts) >= 2:
                channel_username = parts[0].replace("@", "")
                try:
                    post_id = int(parts[-1])
                except ValueError:
                    return False
        
        if not channel_username or not post_id:
            return False
        
        comment_exists = await check_comment_exists(bot, channel_username, post_id, user.telegram_id)
        
        if comment_exists:
            user_reward = deduct_app_commission(user.id, user_task.reward_ton, db)
            balance = db.query(UserBalance).filter(UserBalance.user_id == user.id).first()
            if balance:
                balance.ton_escrow_balance -= user_task.reward_ton
                balance.ton_active_balance += user_reward
            
            add_referral_commission(user.id, user_task.reward_ton, db)
            user_task.status = UserTaskStatus.COMPLETED
            user_task.validated_at = datetime.now(timezone.utc)
            user_task.validation_result = True
            task.completed_slots += 1
            db.commit()
            print(f"✅ Комментарий пользователя {user.telegram_id} к заданию {task.id} подтвержден", flush=True)
            return True
        return False
    except Exception as e:
        print(f"❌ Ошибка при валидации комментария: {e}", flush=True)
        return False


async def check_comments_periodically(db: Session):
    """Проверяет комментарии: каждую минуту первые 10 минут, затем каждый час 24 часа."""
    try:
        now = datetime.now(timezone.utc)
        comment_tasks = db.query(UserTask).join(Task).filter(
            and_(
                UserTask.status == UserTaskStatus.IN_PROGRESS,
                Task.task_type == TaskType.COMMENT
            )
        ).all()
        
        for user_task in comment_tasks:
            task = db.query(Task).filter(Task.id == user_task.task_id).first()
            user = db.query(User).filter(User.id == user_task.user_id).first()
            if not task or not user or not user_task.created_at:
                continue
            
            created_at = user_task.created_at.replace(tzinfo=timezone.utc)
            time_since_creation = now - created_at
            
            should_check = False
            if time_since_creation <= timedelta(minutes=10):
                minutes_since = int(time_since_creation.total_seconds() / 60)
                if minutes_since <= 10:
                    should_check = True
            elif time_since_creation <= timedelta(hours=24):
                if time_since_creation.total_seconds() % 3600 < 60:
                    should_check = True
            else:
                if user_task.status == UserTaskStatus.IN_PROGRESS:
                    balance = db.query(UserBalance).filter(UserBalance.user_id == user.id).first()
                    if balance:
                        balance.ton_escrow_balance -= user_task.reward_ton
                    user_task.status = UserTaskStatus.FAILED
                    user_task.validation_result = False
                    db.commit()
                continue
            
            if should_check:
                await validate_comment_task(user_task, task, user, db)
    except Exception as e:
        print(f"❌ Ошибка в check_comments_periodically: {e}", flush=True)


async def check_deleted_comments(db: Session):
    """Проверяет удаленные комментарии и списывает средства."""
    try:
        now = datetime.now(timezone.utc)
        completed_tasks = db.query(UserTask).join(Task).filter(
            and_(
                UserTask.status == UserTaskStatus.COMPLETED,
                UserTask.validation_result == True,
                Task.task_type == TaskType.COMMENT,
                UserTask.validated_at.isnot(None)
            )
        ).all()
        
        for user_task in completed_tasks:
            task = db.query(Task).filter(Task.id == user_task.task_id).first()
            user = db.query(User).filter(User.id == user_task.user_id).first()
            if not task or not user or not user_task.validated_at:
                continue
            
            time_since_validation = now - user_task.validated_at.replace(tzinfo=timezone.utc)
            if time_since_validation <= timedelta(hours=24):
                if not TELEGRAM_ADMIN_BOT_TOKEN:
                    continue
                try:
                    bot = Bot(token=TELEGRAM_ADMIN_BOT_TOKEN)
                    post_url = task.telegram_post_id
                    if not post_url or "t.me/" not in post_url:
                        continue
                    
                    parts = post_url.split("t.me/")[1].split("/")
                    if len(parts) >= 2:
                        channel_username = parts[0].replace("@", "")
                        try:
                            post_id = int(parts[-1])
                        except ValueError:
                            continue
                        
                        comment_exists = await check_comment_exists(bot, channel_username, post_id, user.telegram_id)
                        if not comment_exists:
                            balance = db.query(UserBalance).filter(UserBalance.user_id == user.id).first()
                            if balance and balance.ton_active_balance >= user_task.reward_ton:
                                balance.ton_active_balance -= user_task.reward_ton
                            user_task.status = UserTaskStatus.FAILED
                            user_task.validation_result = False
                            db.commit()
                            print(f"⚠️ Комментарий удален, средства списаны для пользователя {user.telegram_id}", flush=True)
                except Exception as e:
                    print(f"❌ Ошибка при проверке удаленного комментария: {e}", flush=True)
    except Exception as e:
        print(f"❌ Ошибка в check_deleted_comments: {e}", flush=True)
