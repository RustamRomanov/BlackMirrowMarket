#!/usr/bin/env python3
"""
Скрипт для проверки депозитов и баланса пользователя
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app import models
from decimal import Decimal

TELEGRAM_ID = 8032604270

def check_user_deposits():
    db = SessionLocal()
    try:
        # Найти пользователя
        user = db.query(models.User).filter(models.User.telegram_id == TELEGRAM_ID).first()
        if not user:
            print(f"❌ Пользователь с Telegram ID {TELEGRAM_ID} не найден")
            return
        
        print(f"✅ Пользователь найден: ID={user.id}, Telegram ID={user.telegram_id}")
        
        # Проверить баланс
        balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
        if balance:
            print(f"💰 Текущий баланс: {float(balance.ton_active_balance) / 10**9:.4f} TON")
            print(f"   В эскроу: {float(balance.ton_escrow_balance) / 10**9:.4f} TON")
        else:
            print("⚠️ Баланс не найден (создан автоматически при первом депозите)")
        
        # Проверить депозиты
        deposits = db.query(models.Deposit).filter(models.Deposit.user_id == user.id).all()
        if not deposits:
            # Проверить депозиты по Telegram ID из комментария
            deposits = db.query(models.Deposit).filter(
                models.Deposit.telegram_id_from_comment == str(TELEGRAM_ID)
            ).all()
        
        print(f"\n📥 Найдено депозитов: {len(deposits)}")
        for dep in deposits:
            print(f"   - TX: {dep.tx_hash[:20]}...")
            print(f"     Сумма: {float(dep.amount_nano) / 10**9:.4f} TON")
            print(f"     Статус: {dep.status}")
            print(f"     Создан: {dep.created_at}")
            if dep.processed_at:
                print(f"     Обработан: {dep.processed_at}")
            print()
        
        # Проверить все депозиты (включая без user_id)
        all_deposits = db.query(models.Deposit).filter(
            models.Deposit.telegram_id_from_comment == str(TELEGRAM_ID)
        ).all()
        
        if all_deposits:
            print(f"\n📋 Все депозиты с Telegram ID {TELEGRAM_ID} в комментарии:")
            for dep in all_deposits:
                print(f"   - TX: {dep.tx_hash[:20]}...")
                print(f"     Сумма: {float(dep.amount_nano) / 10**9:.4f} TON")
                print(f"     Статус: {dep.status}")
                print(f"     User ID: {dep.user_id}")
                print(f"     Telegram ID из комментария: {dep.telegram_id_from_comment}")
                print()
        
        # Проверить последние депозиты (без фильтра)
        recent_deposits = db.query(models.Deposit).order_by(
            models.Deposit.created_at.desc()
        ).limit(10).all()
        
        print(f"\n📊 Последние 10 депозитов (все):")
        for dep in recent_deposits:
            print(f"   - TX: {dep.tx_hash[:20]}...")
            print(f"     Сумма: {float(dep.amount_nano) / 10**9:.4f} TON")
            print(f"     Статус: {dep.status}")
            print(f"     Telegram ID из комментария: {dep.telegram_id_from_comment}")
            print(f"     User ID: {dep.user_id}")
            print()
        
    finally:
        db.close()

if __name__ == "__main__":
    check_user_deposits()



