from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.database import get_db
from app import models, schemas
from typing import Optional, List
from decimal import Decimal
import secrets
import string

router = APIRouter()

def generate_referral_code() -> str:
    """Генерация уникального реферального кода"""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))

@router.post("/", response_model=schemas.UserResponse)
async def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Создание или обновление пользователя"""
    db_user = db.query(models.User).filter(models.User.telegram_id == user.telegram_id).first()
    
    if db_user:
        # Обновляем существующего пользователя
        user_dict = user.dict(exclude_unset=True)
        # Обрабатываем реферальный код только если пользователь новый (нет referrer_id)
        if 'referrer_code' in user_dict and not db_user.referrer_id:
            referrer_code = user_dict.pop('referrer_code')
            if referrer_code:
                referrer = db.query(models.User).filter(models.User.referral_code == referrer_code).first()
                if referrer and referrer.id != db_user.id:
                    db_user.referrer_id = referrer.id
                    # Проверяем, нет ли уже записи о реферале
                    existing_referral = db.query(models.Referral).filter(
                        and_(
                            models.Referral.referrer_id == referrer.id,
                            models.Referral.referred_id == db_user.id
                        )
                    ).first()
                    if not existing_referral:
                        # Создаем запись о реферале
                        referral = models.Referral(referrer_id=referrer.id, referred_id=db_user.id)
                        db.add(referral)
        
        for key, value in user_dict.items():
            if key != 'referrer_code':  # Не обновляем referrer_code через обычное обновление
                setattr(db_user, key, value)
        db.commit()
        db.refresh(db_user)
        return db_user
    
    # Создаем нового пользователя
    user_dict = user.dict()
    referrer_code = user_dict.pop('referrer_code', None)
    
    # Генерируем уникальный реферальный код
    referral_code = generate_referral_code()
    while db.query(models.User).filter(models.User.referral_code == referral_code).first():
        referral_code = generate_referral_code()
    
    user_dict['referral_code'] = referral_code
    
    # Обрабатываем реферальный код
    referrer_id = None
    if referrer_code:
        referrer = db.query(models.User).filter(models.User.referral_code == referrer_code).first()
        if referrer:
            referrer_id = referrer.id
    
    if referrer_id:
        user_dict['referrer_id'] = referrer_id
    
    db_user = models.User(**user_dict)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Создаем запись о реферале, если есть реферер
    if referrer_id:
        referral = models.Referral(referrer_id=referrer_id, referred_id=db_user.id)
        db.add(referral)
    
    # Создаем баланс с нулевым балансом (реальные TON)
    db_balance = models.UserBalance(
        user_id=db_user.id,
        ton_active_balance=0,  # Начальный баланс 0 TON
        last_fiat_rate=Decimal("250"),  # Примерный курс TON/RUB
        fiat_currency="RUB"
    )
    db.add(db_balance)
    db.commit()
    
    return db_user

@router.get("/{telegram_id}", response_model=schemas.UserResponse)
async def get_user(telegram_id: int, db: Session = Depends(get_db)):
    """Получение пользователя по telegram_id"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверяем блокировку: если ban_until прошла, снимаем блокировку
    from datetime import datetime, timezone
    if user.is_banned and user.ban_until:
        if datetime.now(timezone.utc) > user.ban_until:
            user.is_banned = False
            user.ban_until = None
            user.ban_reason = None
            db.commit()
            db.refresh(user)
    
    return user

@router.put("/{telegram_id}", response_model=schemas.UserResponse)
async def update_user(telegram_id: int, user_update: schemas.UserUpdate, db: Session = Depends(get_db)):
    """Обновление профиля пользователя"""
    db_user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    for key, value in user_update.dict(exclude_unset=True).items():
        setattr(db_user, key, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

@router.get("/{telegram_id}/profile-complete")
async def check_profile_complete(telegram_id: int, db: Session = Depends(get_db)):
    """Проверка заполненности обязательных полей профиля"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    is_complete = user.age is not None and user.gender is not None and user.country is not None
    return {"is_complete": is_complete, "missing_fields": []}

@router.get("/{telegram_id}/referral-info", response_model=schemas.ReferralInfo)
async def get_referral_info(telegram_id: int, db: Session = Depends(get_db)):
    """Получение информации о реферальной программе"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.referral_code:
        # Генерируем код, если его нет
        referral_code = generate_referral_code()
        while db.query(models.User).filter(models.User.referral_code == referral_code).first():
            referral_code = generate_referral_code()
        user.referral_code = referral_code
        db.commit()
    
    # Подсчитываем рефералов
    total_referrals = db.query(models.Referral).filter(models.Referral.referrer_id == user.id).count()
    
    # Подсчитываем заработок с рефералов
    balance = db.query(models.UserBalance).filter(models.UserBalance.user_id == user.id).first()
    total_earned_ton = balance.ton_referral_earnings if balance else Decimal(0)
    
    # Конвертируем в фиат
    fiat_rate = float(balance.last_fiat_rate) if balance else 250.0
    total_earned_fiat = (float(total_earned_ton) / 10**9) * fiat_rate
    
    # Формируем реферальную ссылку
    referral_link = f"https://t.me/BlackMirrowMarketBot?start={user.referral_code}"
    
    return schemas.ReferralInfo(
        referral_code=user.referral_code,
        referral_link=referral_link,
        total_referrals=total_referrals,
        total_earned_ton=total_earned_ton,
        total_earned_fiat=Decimal(str(total_earned_fiat))
    )

@router.get("/{telegram_id}/referrals", response_model=List[schemas.ReferralDetail])
async def get_referrals(telegram_id: int, db: Session = Depends(get_db)):
    """Получение списка рефералов"""
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    referrals = db.query(models.Referral).filter(models.Referral.referrer_id == user.id).all()
    
    result = []
    for ref in referrals:
        referred_user = db.query(models.User).filter(models.User.id == ref.referred_id).first()
        result.append(schemas.ReferralDetail(
            referred_username=referred_user.username if referred_user else None,
            referred_first_name=referred_user.first_name if referred_user else None,
            total_earned_ton=ref.total_earned_ton,
            commission_earned_ton=ref.referral_commission_ton,
            created_at=ref.created_at
        ))
    
    return result
