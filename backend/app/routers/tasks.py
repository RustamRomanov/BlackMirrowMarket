from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.database import get_db
from app import models, schemas
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Optional

router = APIRouter()

def add_referral_commission(user_id: int, reward_ton: Decimal, db: Session):
    """Начисление 5% комиссии рефереру с каждого выполненного задания"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.referrer_id:
        return
    
    # Вычисляем 5% от награды (после вычета комиссии приложения)
    commission = reward_ton * Decimal("0.05")
    
    # Находим реферальную запись
    referral = db.query(models.Referral).filter(
        and_(
            models.Referral.referrer_id == user.referrer_id,
            models.Referral.referred_id == user.id
        )
    ).first()
    
    if referral:
        # Обновляем статистику реферала
        referral.total_earned_ton += reward_ton
        referral.referral_commission_ton += commission
        
        # Начисляем комиссию рефереру
        referrer_balance = db.query(models.UserBalance).filter(
            models.UserBalance.user_id == user.referrer_id
        ).first()
        
        if referrer_balance:
            referrer_balance.ton_active_balance += commission
            referrer_balance.ton_referral_earnings += commission

def deduct_app_commission(user_id: int, reward_ton: Decimal, db: Session) -> Decimal:
    """
    Вычитает 10% комиссию приложения с исполнителя задания.
    Возвращает сумму, которую получит исполнитель после вычета комиссии.
    Комиссия начисляется на баланс приложения (сервисный кошелек).
    """
    # Вычисляем 10% комиссию приложения
    app_commission = reward_ton * Decimal("0.10")
    
    # Сумма, которую получит исполнитель
    user_reward = reward_ton - app_commission
    
    # Комиссия уже учтена в user_reward, поэтому баланс исполнителя будет обновлён правильно
    # TODO: В будущем можно добавить запись в таблицу app_profit для отслеживания комиссий
    # или напрямую начислять на сервисный кошелек
    
    return user_reward

@router.get("/", response_model=List[schemas.TaskListItem])
async def get_tasks(
    telegram_id: int,
    db: Session = Depends(get_db),
    task_type: Optional[str] = None
):
    """Получение списка доступных заданий для пользователя"""
    # Получаем пользователя
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверяем баланс (только для блокировки при отрицательном балансе)
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    if balance and balance.ton_active_balance < 0:
        return []  # Заблокирован доступ при отрицательном балансе
    
    # Получаем курс валют
    fiat_rate = float(balance.last_fiat_rate) if balance and balance.last_fiat_rate else 250.0
    
    # Исключаем тестового пользователя (telegram_id=0) - это примеры заданий
    test_creator = db.query(models.User).filter(models.User.telegram_id == 0).first()
    test_creator_id = test_creator.id if test_creator else None
    
    # Формируем запрос - строго исключаем тестовые задания и примеры
    query = db.query(models.Task).filter(
        models.Task.status == models.TaskStatus.ACTIVE
    )
    
    # Исключаем тестовые задания (is_test=True или is_test IS NULL с проверкой)
    query = query.filter(
        or_(
            models.Task.is_test == False,
            models.Task.is_test.is_(None)
        )
    )
    
    # Исключаем примеры заданий (созданные тестовым пользователем)
    if test_creator_id:
        query = query.filter(models.Task.creator_id != test_creator_id)
    
    # Дополнительная проверка: исключаем задания, созданные пользователями с telegram_id <= 0
    # (на случай, если есть другие тестовые пользователи)
    test_users = db.query(models.User).filter(models.User.telegram_id <= 0).all()
    if test_users:
        test_user_ids = [u.id for u in test_users]
        query = query.filter(~models.Task.creator_id.in_(test_user_ids))
    
    # ВАЖНО: Исключаем собственные задания пользователя из "Заработок"
    # Пользователь не должен видеть свои задания в списке доступных для выполнения
    query = query.filter(models.Task.creator_id != user.id)
    
    # Фильтр по типу задания
    if task_type:
        query = query.filter(models.Task.task_type == task_type)
    
    # Фильтр по таргетингу (только если профиль заполнен)
    if user.age and user.gender and user.country:
        query = query.filter(
            or_(
                models.Task.target_country.is_(None),
                models.Task.target_country == user.country
            )
        ).filter(
            or_(
                models.Task.target_gender.is_(None),
                models.Task.target_gender == user.gender
            )
        )
        
        # Фильтр по возрасту
        query = query.filter(
            or_(
                models.Task.target_age_min.is_(None),
                models.Task.target_age_min <= user.age
            )
        ).filter(
            or_(
                models.Task.target_age_max.is_(None),
                models.Task.target_age_max >= user.age
            )
        )
    
    # Фильтр по лимиту подписок (только если профиль заполнен)
    if balance and user.age and user.gender and user.country:
        # Проверяем, нужно ли скрывать задания на подписку
        if balance.subscriptions_used_24h >= balance.subscription_limit_24h:
            query = query.filter(models.Task.task_type != models.TaskType.SUBSCRIPTION)
    
    tasks = query.order_by(models.Task.price_per_slot_ton.desc()).all()
    
    # Формируем ответ
    result = []
    for task in tasks:
        remaining_slots = task.total_slots - task.completed_slots
        if remaining_slots <= 0:
            continue
        
        price_fiat = float(task.price_per_slot_ton) / 10**9 * fiat_rate
        
        result.append(schemas.TaskListItem(
            id=task.id,
            title=task.title,
            description=task.description,
            task_type=task.task_type,
            price_per_slot_ton=task.price_per_slot_ton,
            price_per_slot_fiat=Decimal(str(price_fiat)),
            fiat_currency=fiat_currency,
            total_slots=task.total_slots,
            completed_slots=task.completed_slots,
            remaining_slots=remaining_slots,
            telegram_channel_id=task.telegram_channel_id,
            comment_instruction=task.comment_instruction,
            is_test=task.is_test or False
        ))
    
    return result

@router.get("/my", response_model=List[schemas.TaskResponse])
async def get_my_tasks(telegram_id: int = Query(..., description="Telegram ID пользователя"), db: Session = Depends(get_db)):
    """Получение списка заданий, созданных пользователем"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Исключаем тестовые задания из списка "моих заданий"
    tasks = db.query(models.Task).filter(
        models.Task.creator_id == user.id,
        models.Task.is_test == False  # Исключаем тестовые задания
    ).order_by(models.Task.created_at.desc()).all()
    return tasks

@router.get("/{task_id}", response_model=schemas.TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    """Получение детальной информации о задании"""
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/", response_model=schemas.TaskResponse)
async def create_task(task: schemas.TaskCreate, telegram_id: int, db: Session = Depends(get_db)):
    """
    Создание нового задания.
    Списание средств с баланса заказчика (total_slots * price_per_slot_ton).
    """
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверяем баланс заказчика
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")
    
    # Вычисляем общую стоимость задания
    total_cost = task.total_slots * task.price_per_slot_ton
    
    # Проверяем достаточность средств
    if balance.ton_active_balance < total_cost:
        required_ton = float(total_cost) / 10**9
        available_ton = float(balance.ton_active_balance) / 10**9
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds. Required: {required_ton:.4f} TON, Available: {available_ton:.4f} TON"
        )
    
    # Списываем средства с баланса заказчика
    balance.ton_active_balance -= total_cost
    
    # Создаем задание
    db_task = models.Task(creator_id=user.id, **task.dict())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    return db_task

@router.patch("/{task_id}/pause")
async def pause_task(task_id: int, telegram_id: int, db: Session = Depends(get_db)):
    """Остановка задания"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    task = db.query(models.Task).filter(
        and_(
            models.Task.id == task_id,
            models.Task.creator_id == user.id
        )
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status == models.TaskStatus.ACTIVE:
        task.status = models.TaskStatus.PAUSED
        db.commit()
        return {"status": "paused", "message": "Задание остановлено"}
    else:
        raise HTTPException(status_code=400, detail="Задание уже остановлено или завершено")

@router.patch("/{task_id}/resume")
async def resume_task(task_id: int, telegram_id: int, db: Session = Depends(get_db)):
    """Возобновление задания"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    task = db.query(models.Task).filter(
        and_(
            models.Task.id == task_id,
            models.Task.creator_id == user.id
        )
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status == models.TaskStatus.PAUSED:
        task.status = models.TaskStatus.ACTIVE
        db.commit()
        return {"status": "active", "message": "Задание возобновлено"}
    else:
        raise HTTPException(status_code=400, detail="Задание не может быть возобновлено")

@router.patch("/{task_id}/cancel")
async def cancel_task(task_id: int, telegram_id: int, db: Session = Depends(get_db)):
    """Остановка задания с возвратом остатка на баланс"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    task = db.query(models.Task).filter(
        and_(
            models.Task.id == task_id,
            models.Task.creator_id == user.id
        )
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status == models.TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Задание уже завершено")
    
    # Вычисляем остаток (невыполненные слоты)
    remaining_slots = task.total_slots - task.completed_slots
    refund_amount = remaining_slots * task.price_per_slot_ton
    
    # Возвращаем средства на баланс
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    if balance:
        balance.ton_active_balance += refund_amount
    
    # Останавливаем задание
    task.status = models.TaskStatus.CANCELLED
    db.commit()
    
    return {
        "status": "cancelled",
        "message": "Задание остановлено",
        "refund_amount": str(refund_amount / 10**9) + " TON"
    }

@router.post("/{task_id}/start", response_model=schemas.UserTaskResponse)
async def start_task(task_id: int, telegram_id: int, db: Session = Depends(get_db)):
    """Начало выполнения задания пользователем"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status != models.TaskStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Task is not active")
    
    if task.completed_slots >= task.total_slots:
        raise HTTPException(status_code=400, detail="No available slots")
    
    # Проверяем, не выполнял ли пользователь уже это задание
    existing = db.query(models.UserTask).filter(
        and_(
            models.UserTask.user_id == user.id,
            models.UserTask.task_id == task_id
        )
    ).first()
    
    if existing and existing.status != models.UserTaskStatus.FAILED:
        raise HTTPException(status_code=400, detail="Task already started")
    
    # Для просмотра - сразу зачисляем средства (имитация)
    if task.task_type == models.TaskType.VIEW:
        # Вычитаем 10% комиссию приложения с исполнителя
        user_reward = deduct_app_commission(user.id, task.price_per_slot_ton, db)
        
        # Создаем запись о выполнении (сохраняем оригинальную награду для статистики)
        user_task = models.UserTask(
            user_id=user.id,
            task_id=task_id,
            reward_ton=task.price_per_slot_ton,  # Оригинальная награда для статистики
            status=models.UserTaskStatus.COMPLETED,
            validated_at=datetime.utcnow(),
            validation_result=True
        )
        db.add(user_task)
        
        # Начисляем исполнителю награду после вычета комиссии (безопасно, с блокировкой)
        from app.database_optimizations import update_balance_safely
        update_balance_safely(db, user.id, user_reward, "active")
        
        # Начисляем 5% рефереру (от оригинальной награды)
        add_referral_commission(user.id, task.price_per_slot_ton, db)
        
        # Обновляем счетчик выполненных слотов
        task.completed_slots += 1
        
        db.commit()
        db.refresh(user_task)
        return user_task
    
    # Для подписки и комментария - создаем запись со статусом IN_PROGRESS
    user_task = models.UserTask(
        user_id=user.id,
        task_id=task_id,
        reward_ton=task.price_per_slot_ton,
        status=models.UserTaskStatus.IN_PROGRESS,
        escrow_started_at=datetime.utcnow(),
        escrow_ends_at=datetime.utcnow() + timedelta(days=7)
    )
    db.add(user_task)
    
    # Резервируем средства в эскроу (безопасно, с блокировкой)
    from app.database_optimizations import update_balance_safely
    update_balance_safely(db, user.id, -task.price_per_slot_ton, "active")
    update_balance_safely(db, user.id, task.price_per_slot_ton, "escrow")
    
    # Обновляем счетчик подписок, если это подписка
    if task.task_type == models.TaskType.SUBSCRIPTION and balance:
        balance.subscriptions_used_24h += 1
    
    db.commit()
    db.refresh(user_task)
    return user_task

@router.post("/{task_id}/validate-comment")
async def validate_comment(task_id: int, telegram_id: int, db: Session = Depends(get_db)):
    """Валидация комментария (имитация проверки ботом)"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_task = db.query(models.UserTask).filter(
        and_(
            models.UserTask.user_id == user.id,
            models.UserTask.task_id == task_id,
            models.UserTask.status == models.UserTaskStatus.IN_PROGRESS
        )
    ).first()
    
    if not user_task:
        raise HTTPException(status_code=404, detail="User task not found")
    
    # Имитация проверки - всегда успешно для тестирования
    user_task.status = models.UserTaskStatus.COMPLETED
    user_task.validated_at = datetime.utcnow()
    user_task.validation_result = True
    
    # Вычитаем 10% комиссию приложения с исполнителя
    user_reward = deduct_app_commission(user.id, user_task.reward_ton, db)
    
    # Переводим средства из эскроу в активный баланс (после вычета комиссии)
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    if balance:
        balance.ton_escrow_balance -= user_task.reward_ton  # Списываем полную сумму из эскроу
        balance.ton_active_balance += user_reward  # Начисляем сумму после вычета комиссии
    
    # Начисляем 5% рефереру (от оригинальной награды)
    add_referral_commission(user.id, user_task.reward_ton, db)
    
    # Обновляем счетчик выполненных слотов
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        task.completed_slots += 1
    
    db.commit()
    return {"status": "validated", "message": "Comment validated successfully"}

@router.post("/{task_id}/report")
async def report_task(task_id: int, telegram_id: int, reason: str = None, db: Session = Depends(get_db)):
    """Жалоба на задание (отправка сигнала модератору)"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Находим запись о выполнении задания
    user_task = db.query(models.UserTask).filter(
        and_(
            models.UserTask.user_id == user.id,
            models.UserTask.task_id == task_id,
            models.UserTask.status == models.UserTaskStatus.IN_PROGRESS
        )
    ).first()
    
    if not user_task:
        raise HTTPException(status_code=404, detail="User task not found")
    
    # Помечаем задание как завершенное (пользователь пожаловался)
    user_task.status = models.UserTaskStatus.FAILED
    user_task.validation_result = False
    
    # Возвращаем средства из эскроу на баланс пользователя
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    if balance:
        balance.ton_escrow_balance -= user_task.reward_ton
        balance.ton_active_balance += user_task.reward_ton
    
    # Создаем запись о жалобе в базе данных
    report = models.TaskReport(
        task_id=task_id,
        reporter_id=user.id,
        reason=reason or "Жалоба на задание",
        status=models.TaskReportStatus.PENDING
    )
    db.add(report)
    
    db.commit()
    return {
        "status": "reported",
        "message": "Жалоба отправлена модератору. Средства возвращены на ваш баланс."
    }
