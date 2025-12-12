from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app import models, schemas
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Any

router = APIRouter()

def recalculate_balance_from_transactions(user_id: int, db: Session) -> Decimal:
    """
    Пересчитывает баланс пользователя на основе:
    1. Всех транзакций (депозиты и выводы)
    2. Бюджета всех активных заданий (которые еще не отменены)
    
    Возвращает правильный баланс в нано-TON.
    """
    # Суммируем все обработанные депозиты
    deposits = db.query(func.sum(models.Deposit.amount_nano)).filter(
        models.Deposit.user_id == user_id,
        models.Deposit.status == "processed"
    ).scalar() or Decimal(0)
    
    # Суммируем все успешно отправленные выводы (только те, у которых есть tx_hash)
    withdrawals = db.query(func.sum(models.TonTransaction.amount_nano)).filter(
        models.TonTransaction.user_id == user_id,
        models.TonTransaction.tx_hash.isnot(None),  # Только отправленные транзакции
        models.TonTransaction.status.in_(["pending", "completed"])  # Успешные или в процессе
    ).scalar() or Decimal(0)
    
    # Находим все активные задания (не отмененные) и считаем их бюджет
    active_tasks = db.query(models.Task).filter(
        models.Task.creator_id == user_id,
        models.Task.status != models.TaskStatus.CANCELLED
    ).all()
    
    # Считаем общий бюджет всех активных заданий (в нано-TON)
    total_spent_on_tasks_nano = Decimal(0)
    for task in active_tasks:
        # price_per_slot_ton в БД хранится в нано-TON
        price_per_slot_nano = Decimal(task.price_per_slot_ton)
        task_budget_nano = Decimal(task.total_slots) * price_per_slot_nano
        total_spent_on_tasks_nano += task_budget_nano
    
    # Правильный баланс = депозиты - выводы - потрачено на активные задания
    correct_balance = deposits - withdrawals - total_spent_on_tasks_nano
    
    return correct_balance


@router.get("/{telegram_id}", response_model=schemas.BalanceResponse)
async def get_balance(telegram_id: int, db: Session = Depends(get_db)):
    """Получение баланса пользователя с автоматической проверкой и корректировкой"""
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
    
    # АВТОМАТИЧЕСКАЯ ПРОВЕРКА И КОРРЕКТИРОВКА БАЛАНСА
    correct_balance = recalculate_balance_from_transactions(user.id, db)
    current_balance = Decimal(balance.ton_active_balance or 0)
    
    # Если баланс не совпадает, корректируем
    if current_balance != correct_balance:
        difference = correct_balance - current_balance
        print(f"⚠️ Balance mismatch for user {telegram_id}: current={current_balance/10**9:.4f} TON, correct={correct_balance/10**9:.4f} TON, difference={difference/10**9:.4f} TON", flush=True)
        balance.ton_active_balance = correct_balance
        db.commit()
        db.refresh(balance)
        print(f"✅ Balance corrected for user {telegram_id}: {correct_balance/10**9:.4f} TON", flush=True)
    
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


@router.get("/{telegram_id}/deposits")
async def get_user_deposits(telegram_id: int, db: Session = Depends(get_db)):
    """Получение всех депозитов пользователя."""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    deposits = (
        db.query(models.Deposit)
        .filter(models.Deposit.user_id == user.id)
        .order_by(models.Deposit.created_at.desc())
        .all()
    )
    
    return [
        {
            "id": d.id,
            "tx_hash": d.tx_hash,
            "from_address": d.from_address,
            "amount_nano": str(d.amount_nano),
            "status": d.status,
            "created_at": d.created_at,
            "processed_at": d.processed_at,
        }
        for d in deposits
    ]


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


@router.post("/{telegram_id}/recalculate-from-tasks")
async def recalculate_balance_from_tasks(telegram_id: int, db: Session = Depends(get_db)):
    """
    Пересчитывает баланс пользователя на основе:
    1. Всех депозитов
    2. Всех выводов
    3. Бюджета всех активных заданий (которые еще не отменены)
    
    Правильный баланс = депозиты - выводы - потрачено на активные задания
    """
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")
    
    # Вспомогательные функции для работы с TON
    def nano_to_ton(nano: Decimal) -> Decimal:
        return nano / Decimal(10**9)
    
    def ton_to_nano(ton: Decimal) -> Decimal:
        return ton * Decimal(10**9)
    
    # 1. Суммируем все обработанные депозиты
    deposits_nano = db.query(func.sum(models.Deposit.amount_nano)).filter(
        models.Deposit.user_id == user.id,
        models.Deposit.status == "processed"
    ).scalar() or Decimal(0)
    deposits_ton = nano_to_ton(deposits_nano)
    
    # 2. Суммируем все успешно отправленные выводы
    withdrawals_nano = db.query(func.sum(models.TonTransaction.amount_nano)).filter(
        models.TonTransaction.user_id == user.id,
        models.TonTransaction.tx_hash.isnot(None),
        models.TonTransaction.status.in_(["pending", "completed"])
    ).scalar() or Decimal(0)
    withdrawals_ton = nano_to_ton(withdrawals_nano)
    
    # 3. Находим все активные задания (не отмененные)
    active_tasks = db.query(models.Task).filter(
        models.Task.creator_id == user.id,
        models.Task.status != models.TaskStatus.CANCELLED
    ).all()
    
    # 4. Считаем общий бюджет всех активных заданий
    total_spent_on_tasks_ton = Decimal(0)
    tasks_info = []
    
    for task in active_tasks:
        # Цена за слот в БД хранится в нано-TON, конвертируем в TON
        price_per_slot_ton = nano_to_ton(Decimal(task.price_per_slot_ton))
        # Бюджет задания = все слоты × цена за слот
        task_budget_ton = Decimal(task.total_slots) * price_per_slot_ton
        total_spent_on_tasks_ton += task_budget_ton
        
        tasks_info.append({
            "task_id": task.id,
            "title": task.title,
            "total_slots": task.total_slots,
            "price_per_slot_ton": float(price_per_slot_ton),
            "task_budget_ton": float(task_budget_ton),
            "status": task.status.value
        })
    
    # 5. Правильный баланс = депозиты - выводы - потрачено на активные задания
    correct_balance_ton = deposits_ton - withdrawals_ton - total_spent_on_tasks_ton
    correct_balance_nano = ton_to_nano(correct_balance_ton)
    
    # 6. Текущий баланс
    current_balance_nano = Decimal(balance.ton_active_balance or 0)
    current_balance_ton = nano_to_ton(current_balance_nano)
    
    # 7. Обновляем баланс (преобразуем в int для БД)
    balance.ton_active_balance = int(correct_balance_nano)
    db.flush()  # Принудительно сохраняем изменения перед commit
    db.commit()
    db.refresh(balance)
    
    # Проверяем, что баланс действительно обновился
    updated_balance_nano = Decimal(balance.ton_active_balance or 0)
    updated_balance_ton = nano_to_ton(updated_balance_nano)
    print(f"[RECALCULATE BALANCE] User {telegram_id}: Updated balance from {current_balance_ton:.4f} TON to {updated_balance_ton:.4f} TON", flush=True)
    
    return {
        "telegram_id": telegram_id,
        "current_balance_ton": float(current_balance_ton),
        "correct_balance_ton": float(correct_balance_ton),
        "difference_ton": float(correct_balance_ton - current_balance_ton),
        "deposits_ton": float(deposits_ton),
        "withdrawals_ton": float(withdrawals_ton),
        "spent_on_active_tasks_ton": float(total_spent_on_tasks_ton),
        "active_tasks_count": len(active_tasks),
        "active_tasks": tasks_info,
        "message": f"Balance recalculated and updated. New balance: {correct_balance_ton:.4f} TON"
    }

