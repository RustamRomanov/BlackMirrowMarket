from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app import models, schemas
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Any

router = APIRouter()

@router.get("/{telegram_id}", response_model=schemas.BalanceResponse)
async def get_balance(telegram_id: int, db: Session = Depends(get_db)):
    """Получение баланса пользователя"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    if not balance:
        # Создаем баланс с нулевым балансом (реальные TON)
        balance = models.UserBalance(
            user_id=user.id,
            ton_active_balance=0,  # Начальный баланс 0 TON
            last_fiat_rate=Decimal("250"),
            fiat_currency="RUB"
        )
        db.add(balance)
        db.commit()
        db.refresh(balance)
    
    # Вычисляем фиатный баланс (реальные значения, без виртуальных)
    ton_active = float(balance.ton_active_balance or 0)
    fiat_balance = (ton_active / 10**9) * float(balance.last_fiat_rate or 250)
    
    return schemas.BalanceResponse(
        ton_active_balance=balance.ton_active_balance,
        ton_escrow_balance=balance.ton_escrow_balance,
        fiat_balance=Decimal(str(fiat_balance)),
        fiat_currency=balance.fiat_currency,
        subscription_limit_24h=balance.subscription_limit_24h,
        subscriptions_used_24h=balance.subscriptions_used_24h
    )

@router.patch("/{telegram_id}/currency")
async def change_currency(telegram_id: int, currency: str = Query(...), db: Session = Depends(get_db)):
    """Изменение валюты отображения баланса"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")
    
    # Обновляем курс в зависимости от валюты (примерные курсы)
    currency_rates = {
        "RUB": Decimal("250"),
        "USD": Decimal("3.5"),
        "EUR": Decimal("3.2")
    }
    
    balance.fiat_currency = currency
    balance.last_fiat_rate = currency_rates.get(currency, Decimal("250"))
    db.commit()
    
    return {"message": "Currency updated", "currency": currency}

@router.get("/{telegram_id}/task-stats")
async def get_task_stats(telegram_id: int, db: Session = Depends(get_db)):
    """Получение статистики выполненных заданий пользователя"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Начало сегодняшнего дня
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Получаем все выполненные задания пользователя
    completed_tasks = db.query(
        models.UserTask,
        models.Task
    ).join(
        models.Task, models.UserTask.task_id == models.Task.id
    ).filter(
        models.UserTask.user_id == user.id,
        models.UserTask.status == models.UserTaskStatus.COMPLETED
    ).all()
    
    # Статистика по типам заданий
    stats: Dict[str, Dict[str, Any]] = {
        'subscription': {'today_count': 0, 'total_count': 0, 'today_earned': Decimal(0), 'total_earned': Decimal(0)},
        'comment': {'today_count': 0, 'total_count': 0, 'today_earned': Decimal(0), 'total_earned': Decimal(0)},
        'view': {'today_count': 0, 'total_count': 0, 'today_earned': Decimal(0), 'total_earned': Decimal(0)}
    }
    
    for user_task, task in completed_tasks:
        task_type = task.task_type.value
        reward = user_task.reward_ton
        
        # Общая статистика
        stats[task_type]['total_count'] += 1
        stats[task_type]['total_earned'] += reward
        
        # Статистика за сегодня
        if user_task.validated_at and user_task.validated_at >= today_start:
            stats[task_type]['today_count'] += 1
            stats[task_type]['today_earned'] += reward
    
    # Преобразуем в строки для JSON
    result = {}
    for task_type, data in stats.items():
        result[task_type] = {
            'today_count': data['today_count'],
            'total_count': data['total_count'],
            'today_earned': str(data['today_earned']),
            'total_earned': str(data['total_earned'])
        }
    
    return result


@router.get("/{telegram_id}/deposit-info")
async def get_deposit_info(telegram_id: int, db: Session = Depends(get_db)):
    """
    Получение информации для пополнения баланса.
    Возвращает адрес сервисного кошелька для перевода TON.
    Пользователь переводит TON на этот адрес, затем администратор пополняет баланс через админку.
    """
    import os
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    service_wallet = os.getenv("TON_WALLET_ADDRESS", "")
    if not service_wallet:
        raise HTTPException(status_code=500, detail="Service wallet not configured")
    
    return {
        "service_wallet_address": service_wallet,
        "telegram_id": user.telegram_id,
        "instructions": "Переведите TON на указанный адрес с вашего внешнего кошелька. ВАЖНО: В комментарии к транзакции (Тег/Мемо) укажите ваш Telegram ID для автоматического зачисления.",
        "note": f"Минимальная сумма пополнения: 0.01 TON. В комментарии укажите ваш Telegram ID: {user.telegram_id}. Баланс будет зачислен автоматически в течение 1-2 минут после подтверждения транзакции."
    }


@router.post("/{telegram_id}/withdraw", response_model=schemas.UserWithdrawResponse)
async def user_withdraw(
    telegram_id: int,
    payload: schemas.UserWithdrawRequest,
    db: Session = Depends(get_db)
):
    """
    Вывод средств пользователя на внешний кошелек.
    Средства списываются с баланса пользователя и отправляются с сервисного кошелька.
    """
    from app.ton_service import get_ton_service
    
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")
    
    # Конвертируем TON в нано-TON
    amount_nano = int(payload.amount_ton * Decimal(10**9))
    
    # Проверяем баланс
    if balance.ton_active_balance < amount_nano:
        available_ton = float(balance.ton_active_balance) / 10**9
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds. Available: {available_ton:.4f} TON, Requested: {float(payload.amount_ton):.4f} TON"
        )
    
    # Создаем транзакцию вывода
    service = get_ton_service()
    tx, created = await service.create_withdrawal(
        db=db,
        telegram_id=telegram_id,
        to_address=payload.to_address,
        amount_nano=Decimal(amount_nano),
        idempotency_key=f"user-{telegram_id}-{int(datetime.utcnow().timestamp())}"
    )
    
    return schemas.UserWithdrawResponse(
        transaction_id=tx.id,
        status=tx.status,
        tx_hash=tx.tx_hash,
        message="Withdrawal created successfully" if created else "Transaction already exists",
        amount_ton=float(payload.amount_ton)
    )

