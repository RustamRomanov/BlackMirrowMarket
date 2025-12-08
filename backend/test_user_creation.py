#!/usr/bin/env python3
"""Тестовый скрипт для проверки создания пользователя"""

from app.database import SessionLocal, engine, Base
from app import models
from decimal import Decimal

# Создаем таблицы
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # Проверяем, есть ли пользователь
    user = db.query(models.User).filter(models.User.telegram_id == 123456789).first()
    
    if user:
        print(f"✅ Пользователь уже существует: {user.username}")
        print(f"   ID: {user.id}")
        print(f"   Возраст: {user.age}")
        print(f"   Пол: {user.gender}")
        print(f"   Страна: {user.country}")
    else:
        print("❌ Пользователь не найден, создаем...")
        
        # Создаем пользователя
        new_user = models.User(
            telegram_id=123456789,
            username="test_user",
            first_name="Test"
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        print(f"✅ Пользователь создан: {new_user.username} (ID: {new_user.id})")
        
        # Создаем баланс
        balance = models.UserBalance(
            user_id=new_user.id,
            ton_active_balance=100 * 10**9,
            last_fiat_rate=Decimal("250"),
            fiat_currency="RUB"
        )
        db.add(balance)
        db.commit()
        print(f"✅ Баланс создан: 100 TON")
    
    # Проверяем баланс
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id if user else new_user.id).first()
    if balance:
        print(f"✅ Баланс найден: {float(balance.ton_active_balance) / 10**9} TON")
    else:
        print("❌ Баланс не найден")
    
    # Проверяем задания
    tasks = db.query(models.Task).filter(models.Task.status == models.TaskStatus.ACTIVE).all()
    print(f"✅ Найдено активных заданий: {len(tasks)}")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()




