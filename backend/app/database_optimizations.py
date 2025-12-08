"""
Оптимизации для работы с базой данных
Включает безопасное обновление балансов и кэширование
"""
from sqlalchemy.orm import Session
from sqlalchemy import select
from app import models
from decimal import Decimal
from typing import Optional
import redis
import os
import json

# Инициализация Redis (опционально, если установлен)
try:
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_client = redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None
except:
    redis_client = None


def get_balance_cached(db: Session, user_id: int) -> Optional[models.UserBalance]:
    """
    Получение баланса с кэшированием в Redis.
    Если Redis недоступен, работает напрямую с PostgreSQL.
    """
    cache_key = f"balance:user:{user_id}"
    
    # Пытаемся получить из кэша
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                # Создаем объект баланса из кэша (упрощенная версия)
                balance = db.query(models.UserBalance).filter(
                    models.UserBalance.user_id == user_id
                ).first()
                if balance:
                    return balance
        except Exception as e:
            print(f"Redis cache error: {e}")
    
    # Получаем из БД
    balance = db.query(models.UserBalance).filter(
        models.UserBalance.user_id == user_id
    ).first()
    
    # Сохраняем в кэш (TTL 5 минут)
    if balance and redis_client:
        try:
            cache_data = {
                "ton_active_balance": str(balance.ton_active_balance),
                "ton_escrow_balance": str(balance.ton_escrow_balance),
                "ton_referral_earnings": str(balance.ton_referral_earnings),
            }
            redis_client.setex(cache_key, 300, json.dumps(cache_data))
        except Exception as e:
            print(f"Redis cache set error: {e}")
    
    return balance


def update_balance_safely(
    db: Session,
    user_id: int,
    amount: Decimal,
    balance_type: str = "active"  # active, escrow, referral
) -> bool:
    """
    Безопасное обновление баланса с защитой от race conditions.
    Использует SELECT FOR UPDATE для блокировки строки.
    
    Args:
        db: SQLAlchemy session
        user_id: ID пользователя
        amount: Сумма для изменения (может быть отрицательной)
        balance_type: Тип баланса (active, escrow, referral)
    
    Returns:
        True если успешно, False если ошибка
    """
    try:
        # Блокируем строку для обновления (SELECT FOR UPDATE)
        # Это предотвращает race conditions при одновременных обновлениях
        balance = db.execute(
            select(models.UserBalance)
            .where(models.UserBalance.user_id == user_id)
            .with_for_update()
        ).scalar_one_or_none()
        
        if not balance:
            return False
        
        # Обновляем соответствующий баланс
        if balance_type == "active":
            balance.ton_active_balance += amount
        elif balance_type == "escrow":
            balance.ton_escrow_balance += amount
        elif balance_type == "referral":
            balance.ton_referral_earnings += amount
        
        db.commit()
        
        # Инвалидируем кэш
        if redis_client:
            cache_key = f"balance:user:{user_id}"
            try:
                redis_client.delete(cache_key)
            except:
                pass
        
        return True
    except Exception as e:
        db.rollback()
        print(f"Error updating balance: {e}")
        return False


def invalidate_balance_cache(user_id: int):
    """Инвалидация кэша баланса пользователя"""
    if redis_client:
        cache_key = f"balance:user:{user_id}"
        try:
            redis_client.delete(cache_key)
        except:
            pass

