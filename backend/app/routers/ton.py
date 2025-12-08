from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from decimal import Decimal
from app.database import get_db
from app.schemas import (
    TonWithdrawRequest, TonWithdrawResponse, TonTransactionResponse,
    TonAdminWithdrawRequest
)
from app.ton_service import get_ton_service
from app import models

router = APIRouter()


@router.post("/withdraw", response_model=TonWithdrawResponse)
async def withdraw(payload: TonWithdrawRequest, db: Session = Depends(get_db)):
    """
    Автоматический вывод без лимитов и ручного аппрува.
    Защита от двойных списаний через idempotency_key.
    """
    service = get_ton_service()
    tx, created = await service.create_withdrawal(
        db=db,
        telegram_id=payload.telegram_id,
        to_address=payload.to_address,
        amount_nano=payload.amount_nano,
        idempotency_key=payload.idempotency_key,
    )
    message = "created" if created else "exists"
    return TonWithdrawResponse(
        transaction_id=tx.id, status=tx.status, tx_hash=tx.tx_hash, message=message
    )


@router.get("/transactions", response_model=list[TonTransactionResponse])
async def list_transactions(db: Session = Depends(get_db)):
    """Журнал всех TON-транзакций."""
    records = (
        db.query(models.TonTransaction)
        .order_by(models.TonTransaction.created_at.desc())
        .all()
    )
    return records


@router.get("/transactions/{transaction_id}", response_model=TonTransactionResponse)
async def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Получение конкретной транзакции по ID."""
    tx = db.query(models.TonTransaction).filter(models.TonTransaction.id == transaction_id).first()
    if not tx:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@router.get("/transactions/user/{telegram_id}", response_model=list[TonTransactionResponse])
async def get_user_transactions(telegram_id: int, db: Session = Depends(get_db)):
    """Получение всех транзакций пользователя."""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")
    
    records = (
        db.query(models.TonTransaction)
        .filter(models.TonTransaction.user_id == user.id)
        .order_by(models.TonTransaction.created_at.desc())
        .all()
    )
    return records


@router.post("/admin/withdraw", response_model=TonWithdrawResponse)
async def admin_withdraw(payload: TonAdminWithdrawRequest, db: Session = Depends(get_db)):
    """
    Вывод с сервисного кошелька на любой адрес.
    Используется администратором для прямого вывода средств.
    Не требует Telegram ID - это прямой вывод с кошелька приложения.
    """
    service = get_ton_service()
    # Конвертируем TON в нано-TON
    amount_nano = Decimal(int(payload.amount_ton * Decimal(10**9)))
    
    tx = await service.send_from_service_wallet(
        db=db,
        to_address=payload.to_address,
        amount_nano=amount_nano,
        notes=payload.notes,
        idempotency_key=payload.idempotency_key,
    )
    
    return TonWithdrawResponse(
        transaction_id=tx.id,
        status=tx.status,
        tx_hash=tx.tx_hash,
        message="created"
    )


@router.post("/transactions/{transaction_id}/check-status")
async def check_transaction_status(transaction_id: int, db: Session = Depends(get_db)):
    """Проверяет и обновляет статус транзакции через tonapi."""
    tx = db.query(models.TonTransaction).filter(models.TonTransaction.id == transaction_id).first()
    if not tx:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    service = get_ton_service()
    new_status = await service.check_transaction_status(tx.tx_hash)
    
    if new_status == "completed" and tx.status != "completed":
        tx.status = "completed"
        db.commit()
    elif new_status == "failed" and tx.status != "failed":
        tx.status = "failed"
        # Возвращаем средства пользователю только если это был пользовательский вывод
        if tx.user_id:
            user = db.query(models.User).filter(models.User.id == tx.user_id).first()
            if user:
                balance = db.query(models.UserBalance).filter(
                    models.UserBalance.user_id == user.id
                ).first()
                if balance:
                    balance.ton_active_balance += tx.amount_nano
        db.commit()
    
    db.refresh(tx)
    return {"transaction_id": tx.id, "status": tx.status, "checked_status": new_status}

