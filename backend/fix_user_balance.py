#!/usr/bin/env python3
"""
Скрипт для исправления баланса пользователя на основе созданных заданий.

Использование:
    python3 fix_user_balance.py <telegram_id> [DATABASE_URL]

Примеры:
    python3 fix_user_balance.py 8032604270
    python3 fix_user_balance.py 8032604270 postgresql://user:pass@host:5432/db
    DATABASE_URL=postgresql://... python3 fix_user_balance.py 8032604270
"""

import sys
import os
from decimal import Decimal
from app.database import SessionLocal, engine
from app import models
from sqlalchemy import func, create_engine
from sqlalchemy.orm import sessionmaker

def fix_user_balance(telegram_id: int, database_url: str = None):
    """Исправляет баланс пользователя на основе заданий и транзакций"""
    # Если передан DATABASE_URL, используем его
    if database_url:
        if database_url.startswith("sqlite"):
            db_engine = create_engine(database_url, connect_args={"check_same_thread": False})
        else:
            db_engine = create_engine(database_url)
        SessionLocalCustom = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        db = SessionLocalCustom()
    else:
        db = SessionLocal()
    
    try:
        # Находим пользователя
        user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
        if not user:
            print(f"❌ Пользователь с telegram_id {telegram_id} не найден")
            return
        
        print(f"✅ Пользователь найден: ID={user.id}, telegram_id={user.telegram_id}")
        
        # Находим баланс
        balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
        if not balance:
            print(f"❌ Баланс для пользователя {telegram_id} не найден")
            return
        
        # Вспомогательные функции
        def nano_to_ton(nano: Decimal) -> Decimal:
            return nano / Decimal(10**9)
        
        def ton_to_nano(ton: Decimal) -> Decimal:
            return ton * Decimal(10**9)
        
        # Текущий баланс
        current_balance_nano = Decimal(balance.ton_active_balance or 0)
        current_balance_ton = nano_to_ton(current_balance_nano)
        print(f"\n📊 Текущий баланс: {current_balance_ton:.4f} TON")
        
        # 1. Суммируем все обработанные депозиты
        deposits_nano = db.query(func.sum(models.Deposit.amount_nano)).filter(
            models.Deposit.user_id == user.id,
            models.Deposit.status == "processed"
        ).scalar() or Decimal(0)
        deposits_ton = nano_to_ton(deposits_nano)
        print(f"💰 Депозиты: {deposits_ton:.4f} TON")
        
        # 2. Суммируем все успешно отправленные выводы
        withdrawals_nano = db.query(func.sum(models.TonTransaction.amount_nano)).filter(
            models.TonTransaction.user_id == user.id,
            models.TonTransaction.tx_hash.isnot(None),
            models.TonTransaction.status.in_(["pending", "completed"])
        ).scalar() or Decimal(0)
        withdrawals_ton = nano_to_ton(withdrawals_nano)
        print(f"💸 Выводы: {withdrawals_ton:.4f} TON")
        
        # 3. Находим все активные задания (не отмененные)
        active_tasks = db.query(models.Task).filter(
            models.Task.creator_id == user.id,
            models.Task.status != models.TaskStatus.CANCELLED
        ).all()
        
        print(f"\n📋 Найдено активных заданий: {len(active_tasks)}")
        
        # 4. Считаем общий бюджет всех активных заданий
        total_spent_on_tasks_ton = Decimal(0)
        
        for task in active_tasks:
            # Цена за слот в БД хранится в нано-TON, конвертируем в TON
            price_per_slot_ton = nano_to_ton(Decimal(task.price_per_slot_ton))
            # Бюджет задания = все слоты × цена за слот
            task_budget_ton = Decimal(task.total_slots) * price_per_slot_ton
            total_spent_on_tasks_ton += task_budget_ton
            
            print(f"  - Задание #{task.id}: '{task.title}'")
            print(f"    Слотов: {task.total_slots}, Цена за слот: {price_per_slot_ton:.4f} TON")
            print(f"    Бюджет задания: {task_budget_ton:.4f} TON")
        
        print(f"\n💵 Всего потрачено на активные задания: {total_spent_on_tasks_ton:.4f} TON")
        
        # 5. Правильный баланс = депозиты - выводы - потрачено на активные задания
        correct_balance_ton = deposits_ton - withdrawals_ton - total_spent_on_tasks_ton
        correct_balance_nano = ton_to_nano(correct_balance_ton)
        
        print(f"\n📈 Правильный баланс: {correct_balance_ton:.4f} TON")
        print(f"   (Депозиты {deposits_ton:.4f} - Выводы {withdrawals_ton:.4f} - Задания {total_spent_on_tasks_ton:.4f})")
        
        # 6. Разница
        difference_ton = correct_balance_ton - current_balance_ton
        print(f"\n🔍 Разница: {difference_ton:.4f} TON")
        
        if abs(difference_ton) < Decimal("0.0001"):
            print("✅ Баланс уже правильный, изменений не требуется")
            return
        
        # 7. Обновляем баланс
        print(f"\n🔄 Обновляю баланс...")
        balance.ton_active_balance = correct_balance_nano
        db.commit()
        db.refresh(balance)
        
        new_balance_ton = nano_to_ton(Decimal(balance.ton_active_balance))
        print(f"✅ Баланс обновлен!")
        print(f"   Было: {current_balance_ton:.4f} TON")
        print(f"   Стало: {new_balance_ton:.4f} TON")
        print(f"   Изменение: {difference_ton:+.4f} TON")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python3 fix_user_balance.py <telegram_id> [DATABASE_URL]")
        print("Пример: python3 fix_user_balance.py 8032604270")
        print("Или: python3 fix_user_balance.py 8032604270 postgresql://user:pass@host:5432/db")
        print("Или: DATABASE_URL=postgresql://... python3 fix_user_balance.py 8032604270")
        sys.exit(1)
    
    try:
        telegram_id = int(sys.argv[1])
        # DATABASE_URL может быть передан как аргумент или через переменную окружения
        database_url = sys.argv[2] if len(sys.argv) > 2 else os.getenv("DATABASE_URL")
        fix_user_balance(telegram_id, database_url)
    except ValueError:
        print(f"❌ Ошибка: '{sys.argv[1]}' не является числом")
        sys.exit(1)

