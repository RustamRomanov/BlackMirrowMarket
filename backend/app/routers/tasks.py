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
    
    # Проверяем бан пользователя
    if user.is_banned:
        # Проверяем, истек ли срок бана
        if user.ban_until:
            if datetime.utcnow() < user.ban_until.replace(tzinfo=None) if user.ban_until.tzinfo else user.ban_until:
                # Пользователь все еще забанен - не показываем задания
                return []
            else:
                # Срок бана истек - снимаем бан
                user.is_banned = False
                user.ban_until = None
                user.ban_reason = None
                db.commit()
        else:
            # Бан без срока - не показываем задания
            return []
    
    # Проверяем баланс (только для блокировки при отрицательном балансе)
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    if balance and balance.ton_active_balance < 0:
        return []  # Заблокирован доступ при отрицательном балансе
    
    # Получаем курс валют и валюту пользователя
    fiat_rate = float(balance.last_fiat_rate) if balance and balance.last_fiat_rate else 250.0
    fiat_currency = balance.fiat_currency if balance and balance.fiat_currency else 'RUB'
    
    # Исключаем тестового пользователя (telegram_id=0) - это примеры заданий
    test_creator = db.query(models.User).filter(models.User.telegram_id == 0).first()
    test_creator_id = test_creator.id if test_creator else None
    
    # Формируем запрос - строго исключаем тестовые задания и примеры
    query = db.query(models.Task).filter(
        models.Task.status == models.TaskStatus.ACTIVE
    )
    
    # Исключаем тестовые задания (is_test=True)
    query = query.filter(
        or_(
            models.Task.is_test == False,
            models.Task.is_test.is_(None)
        )
    )
    
    # Исключаем примеры заданий (созданные тестовым пользователем)
    # Исключаем примеры заданий (созданные тестовым пользователем)
    if test_creator_id:
        query = query.filter(models.Task.creator_id != test_creator_id)
    
    # Дополнительная проверка: исключаем задания, созданные пользователями с telegram_id <= 0
    # (на случай, если есть другие тестовые пользователи)
    # (на случай, если есть другие тестовые пользователи)
    test_users = db.query(models.User).filter(models.User.telegram_id <= 0).all()
    if test_users:
        test_user_ids = [u.id for u in test_users]
        query = query.filter(~models.Task.creator_id.in_(test_user_ids))
    
    # Фильтр по типу задания
    if task_type:
        query = query.filter(models.Task.task_type == task_type)
    
    # Фильтр по таргетингу (только если профиль заполнен)
    print(f"[DEBUG] Before targeting filter: {db.query(models.Task).filter(models.Task.status == models.TaskStatus.ACTIVE).count()} active tasks")
    if user.age and user.gender and user.country:
        print(f"[DEBUG] Applying targeting filters for user: age={user.age}, gender={user.gender}, country={user.country}")
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
        print(f"[DEBUG] After targeting filters: {query.count()} tasks")
    
    # Фильтр по лимиту подписок (только если профиль заполнен)
    if balance and user.age and user.gender and user.country:
        # Проверяем, нужно ли скрывать задания на подписку
        if balance.subscriptions_used_24h >= balance.subscription_limit_24h:
            query = query.filter(models.Task.task_type != models.TaskType.SUBSCRIPTION)
    
    # Логируем количество заданий после всех фильтров
    tasks_before_order = query.all()
    print(f"[DEBUG] Tasks after all filters (before ordering): {len(tasks_before_order)}")
    tasks = query.order_by(models.Task.price_per_slot_ton.desc()).all()
    
    print(f"[DEBUG] User profile: age={user.age}, gender={user.gender}, country={user.country}")
    print(f"[DEBUG] Total active tasks in DB: {db.query(models.Task).filter(models.Task.status == models.TaskStatus.ACTIVE).count()}")
    print(f"[DEBUG] Tasks with is_test=False: {db.query(models.Task).filter(models.Task.status == models.TaskStatus.ACTIVE, or_(models.Task.is_test == False, models.Task.is_test.is_(None))).count()}")
    # DEBUG: Логируем количество найденных заданий
    print(f"[DEBUG] Found {len(tasks)} tasks for user {telegram_id}")
    
    # Формируем ответ
    result = []
    for task in tasks:
        remaining_slots = task.total_slots - task.completed_slots
        if remaining_slots <= 0:
            print(f"[DEBUG] Skipping task {task.id} - no remaining slots")
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
            telegram_post_id=str(task.telegram_post_id) if task.telegram_post_id else None,
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
    print(f"[GET TASK] Task {task_id} - telegram_channel_id={task.telegram_channel_id}, telegram_post_id={task.telegram_post_id}, task_type={task.task_type}")
    return task

@router.post("/", response_model=schemas.TaskResponse)
async def create_task(task: schemas.TaskCreate, telegram_id: int, db: Session = Depends(get_db)):
    """
    Создание нового задания.
    Списание средств с баланса заказчика (total_slots * price_per_slot_ton).
    """
    try:
        print(f"[CREATE TASK] Received request: telegram_id={telegram_id}, task_type={task.task_type}, price={task.price_per_slot_ton}, slots={task.total_slots}")
        print(f"[CREATE TASK] telegram_channel_id={task.telegram_channel_id}, telegram_post_id={task.telegram_post_id}")
    except Exception as e:
        print(f"[CREATE TASK] Error logging request: {e}")
    
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверяем баланс заказчика
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")
    
    # Вспомогательные функции для работы с TON (БД хранит в нано-TON)
    def ton_to_nano(ton: Decimal) -> Decimal:
        return ton * Decimal(10**9)
    
    def nano_to_ton(nano: Decimal) -> Decimal:
        return nano / Decimal(10**9)
    
    # Фронтенд отправляет цену в TON
    try:
        price_per_slot_ton = Decimal(str(task.price_per_slot_ton))
        if price_per_slot_ton <= 0:
            raise HTTPException(status_code=400, detail="Price per slot must be greater than 0")
    except (ValueError, TypeError) as e:
        print(f"[CREATE TASK] Error parsing price: {e}, received: {task.price_per_slot_ton}")
        raise HTTPException(status_code=400, detail=f"Invalid price format: {task.price_per_slot_ton}")
    
    # Вычисляем бюджет кампании в TON: количество слотов × цена за слот
    total_budget_ton = Decimal(task.total_slots) * price_per_slot_ton
    
    # Получаем текущий баланс в TON
    balance_ton = nano_to_ton(Decimal(balance.ton_active_balance))
    
    print(f"[CREATE TASK] User {user.id}: {task.total_slots} slots × {price_per_slot_ton} TON = {total_budget_ton} TON budget")
    print(f"[CREATE TASK] Balance before: {balance_ton} TON")
    
    # Проверяем достаточность средств
    if balance_ton < total_budget_ton:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds. Required: {total_budget_ton:.4f} TON, Available: {balance_ton:.4f} TON"
        )
    
    # Списываем бюджет кампании с баланса (конвертируем в нано-TON только для БД)
    balance.ton_active_balance -= ton_to_nano(total_budget_ton)
    
    # Сохраняем цену в нано-TON в базе данных (для совместимости)
    task_dict = task.dict()
    task_dict['price_per_slot_ton'] = str(int(ton_to_nano(price_per_slot_ton)))
    
    # Убеждаемся, что telegram_channel_id и telegram_post_id сохраняются правильно
    print(f"[CREATE TASK] Before creating - telegram_channel_id={task_dict.get('telegram_channel_id')}, telegram_post_id={task_dict.get('telegram_post_id')}")
    print(f"[CREATE TASK] task.telegram_channel_id={task.telegram_channel_id}, task.telegram_post_id={task.telegram_post_id}")
    
    # Создаем задание
    db_task = models.Task(creator_id=user.id, **task_dict)
    db.add(db_task)
    
    # Коммитим изменения
    db.commit()
    db.refresh(balance)
    db.refresh(db_task)
    
    new_balance_ton = nano_to_ton(Decimal(balance.ton_active_balance))
    print(f"[CREATE TASK] Balance after: {new_balance_ton} TON")
    print(f"[CREATE TASK] Task {db_task.id} created successfully")
    print(f"[CREATE TASK] Saved task - telegram_channel_id={db_task.telegram_channel_id}, telegram_post_id={db_task.telegram_post_id}, task_type={db_task.task_type}")
    
    # Убеждаемся, что для комментариев ссылка сохранена
    if db_task.task_type == models.TaskType.COMMENT:
        if not db_task.telegram_channel_id:
            print(f"[CREATE TASK] WARNING: Comment task created without telegram_channel_id!")
        else:
            print(f"[CREATE TASK] Comment task link saved: {db_task.telegram_channel_id}")
    
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
    
    # Получаем баланс заказчика
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    if not balance:
        raise HTTPException(status_code=404, detail="Balance not found")
    
    # Вспомогательные функции для работы с TON (БД хранит в нано-TON)
    def ton_to_nano(ton: Decimal) -> Decimal:
        return ton * Decimal(10**9)
    
    def nano_to_ton(nano: Decimal) -> Decimal:
        return nano / Decimal(10**9)
    
    # Вычисляем остаток (невыполненные слоты)
    remaining_slots = task.total_slots - task.completed_slots
    
    # Цена за слот в БД хранится в нано-TON, конвертируем в TON
    price_per_slot_ton = nano_to_ton(Decimal(task.price_per_slot_ton))
    
    # Вычисляем сумму возврата в TON
    refund_amount_ton = Decimal(remaining_slots) * price_per_slot_ton
    
    balance_ton = nano_to_ton(Decimal(balance.ton_active_balance))
    
    print(f"[CANCEL TASK] Task {task_id}: {remaining_slots} remaining slots × {price_per_slot_ton} TON = {refund_amount_ton} TON refund")
    print(f"[CANCEL TASK] Balance before: {balance_ton} TON")
    
    # Возвращаем средства на баланс заказчика (конвертируем в нано-TON для БД)
    if refund_amount_ton > 0:
        balance.ton_active_balance += ton_to_nano(refund_amount_ton)
    
    # Также нужно вернуть средства из эскроу исполнителей, если они есть
    # Находим все активные UserTask для этого задания
    active_user_tasks = db.query(models.UserTask).filter(
        and_(
            models.UserTask.task_id == task_id,
            models.UserTask.status == models.UserTaskStatus.IN_PROGRESS
        )
    ).all()
    
    # Возвращаем средства из эскроу исполнителей обратно на активный баланс заказчика
    for user_task in active_user_tasks:
        # Списываем средства из эскроу исполнителя
        executor_balance = db.query(models.UserBalance).filter(
            models.UserBalance.user_id == user_task.user_id
        ).first()
        if executor_balance:
            executor_balance.ton_escrow_balance -= user_task.reward_ton
        
        # Возвращаем средства заказчику (из эскроу исполнителя на активный баланс заказчика)
        balance.ton_active_balance += user_task.reward_ton
        
        # Обновляем статус UserTask
        user_task.status = models.UserTaskStatus.REFUNDED
    
    # Останавливаем задание
    task.status = models.TaskStatus.CANCELLED
    
    # Коммитим все изменения
    db.commit()
    db.refresh(balance)
    
    new_balance_ton = nano_to_ton(Decimal(balance.ton_active_balance))
    print(f"[CANCEL TASK] Balance after: {new_balance_ton} TON")
    print(f"[CANCEL TASK] Task {task_id} cancelled, refunded {len(active_user_tasks)} active user tasks")
    
    return {
        "status": "cancelled",
        "message": "Задание остановлено",
        "refund_amount": f"{refund_amount_ton:.4f} TON",
        "refunded_user_tasks": len(active_user_tasks)
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
    # price_per_slot_ton в БД хранится в нано-TON, используем напрямую
    from decimal import Decimal
    def nano_to_ton(nano: Decimal) -> Decimal:
        return nano / Decimal(10**9)
    
    price_per_slot_nano = Decimal(task.price_per_slot_ton)  # Уже в нано-TON
    user_task = models.UserTask(
        user_id=user.id,
        task_id=task_id,
        reward_ton=price_per_slot_nano,  # reward_ton хранится в нано-TON
        status=models.UserTaskStatus.IN_PROGRESS,
        escrow_started_at=datetime.utcnow(),
        escrow_ends_at=datetime.utcnow() + timedelta(days=7)
    )
    db.add(user_task)
    
    # Резервируем средства в эскроу (безопасно, с блокировкой)
    from app.database_optimizations import update_balance_safely
    update_balance_safely(db, user.id, -price_per_slot_nano, "active")
    update_balance_safely(db, user.id, price_per_slot_nano, "escrow")
    
    # Обновляем счетчик подписок, если это подписка
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    if task.task_type == models.TaskType.SUBSCRIPTION and balance:
        balance.subscriptions_used_24h += 1
    
    db.commit()
    db.refresh(user_task)
    return user_task

@router.post("/{task_id}/validate-comment")
async def validate_comment(task_id: int, telegram_id: int, db: Session = Depends(get_db)):
    """Валидация комментария через бота @BlackMirrowAdminBot"""
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
    
    # Используем реальную проверку через бота
    from app.comment_validator import validate_comment_task
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    await validate_comment_task(user_task.id, db)
    
    # Обновляем статус после проверки
    db.refresh(user_task)
    
    if user_task.status == models.UserTaskStatus.COMPLETED:
        return {"status": "validated", "message": "Comment validated successfully"}
    else:
        return {"status": "not_found", "message": "Comment not found. Please make sure you commented on the post and @BlackMirrowAdminBot is admin of the channel."}

@router.post("/{task_id}/check-manually")
async def check_task_manually(task_id: int, telegram_id: int, db: Session = Depends(get_db)):
    """Ручная проверка задания через бота @BlackMirrowAdminBot (для принудительной проверки)"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    user_task = db.query(models.UserTask).filter(
        and_(
            models.UserTask.user_id == user.id,
            models.UserTask.task_id == task_id
        )
    ).first()
    
    if not user_task:
        raise HTTPException(status_code=404, detail="User task not found")
    
    # Используем реальную проверку через бота
    from app.comment_validator import validate_comment_task, validate_subscription_task
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if task.task_type == models.TaskType.COMMENT:
        await validate_comment_task(user_task.id, db)
    elif task.task_type == models.TaskType.SUBSCRIPTION:
        await validate_subscription_task(user_task.id, db)
    
    # Обновляем статус после проверки
    db.refresh(user_task)
    db.refresh(task)
    
    return {
        "status": user_task.status.value,
        "validation_result": user_task.validation_result,
        "validated_at": user_task.validated_at.isoformat() if user_task.validated_at else None,
        "task_completed_slots": task.completed_slots,
        "task_total_slots": task.total_slots,
        "message": "Task checked successfully" if user_task.status == models.UserTaskStatus.COMPLETED else "Task not validated - comment/subscription not found. Make sure @BlackMirrowAdminBot is admin of the channel."
    }

@router.post("/{task_id}/report")
async def report_task(task_id: int, telegram_id: int, db: Session = Depends(get_db)):
    """Жалоба на задание (без описания, просто кнопка) - канал нарушает законы"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Находим запись о выполнении задания (может быть в любом статусе)
    user_task = db.query(models.UserTask).filter(
        and_(
            models.UserTask.user_id == user.id,
            models.UserTask.task_id == task_id
        )
    ).first()
    
    if not user_task:
        raise HTTPException(status_code=404, detail="User task not found")
    
    # Проверяем, не была ли уже создана жалоба на это задание от этого пользователя
    existing_report = db.query(models.TaskReport).filter(
        and_(
            models.TaskReport.task_id == task_id,
            models.TaskReport.reporter_id == user.id,
            models.TaskReport.status == models.TaskReportStatus.PENDING
        )
    ).first()
    
    if existing_report:
        return {
            "status": "already_reported",
            "message": "Вы уже отправили жалобу на это задание. Она находится на рассмотрении."
        }
    
    # Создаем запись о жалобе в базе данных
    report = models.TaskReport(
        task_id=task_id,
        reporter_id=user.id,
        reason="Канал нарушает законы (экстремизм или другой запрещенный контент)",
        status=models.TaskReportStatus.PENDING
    )
    db.add(report)
    
    db.commit()
    return {
        "status": "reported",
        "message": "Жалоба отправлена модератору. Спасибо за обратную связь!"
    }
