from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal
from app.models import TaskType, TaskStatus, UserTaskStatus, UserRole
from pydantic import Field

# User Schemas
class UserBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserCreate(UserBase):
    age: Optional[int] = None
    gender: Optional[str] = None
    country: Optional[str] = None
    referrer_code: Optional[str] = None  # Код реферера при регистрации
    terms_accepted: Optional[bool] = False

class UserUpdate(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    country: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    terms_accepted: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    age: Optional[int]
    gender: Optional[str]
    country: Optional[str]
    referral_code: Optional[str]
    terms_accepted: bool
    role: UserRole
    is_banned: bool
    ban_until: Optional[datetime] = None
    ban_reason: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ReferralInfo(BaseModel):
    referral_code: str
    referral_link: str
    total_referrals: int
    total_earned_ton: Decimal
    total_earned_fiat: Decimal
    
    class Config:
        from_attributes = True

class ReferralDetail(BaseModel):
    referred_username: Optional[str]
    referred_first_name: Optional[str]
    total_earned_ton: Decimal
    commission_earned_ton: Decimal
    created_at: datetime
    
    class Config:
        from_attributes = True

# Balance Schemas
class BalanceResponse(BaseModel):
    ton_active_balance: Decimal
    ton_escrow_balance: Decimal
    fiat_balance: Decimal
    fiat_currency: str
    subscription_limit_24h: int
    subscriptions_used_24h: int
    
    class Config:
        from_attributes = True

class CurrencyUpdate(BaseModel):
    currency: str


class UserWithdrawRequest(BaseModel):
    """Запрос на вывод средств пользователя"""
    to_address: str
    amount_ton: Decimal = Field(..., description="Сумма в TON (не нано-TON)")


class UserWithdrawResponse(BaseModel):
    """Ответ на запрос вывода средств"""
    transaction_id: int
    status: str
    tx_hash: Optional[str] = None
    message: str
    amount_ton: float

# Task Schemas
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    task_type: TaskType
    target_country: Optional[str] = None
    target_gender: Optional[str] = None
    target_age_min: Optional[int] = None
    target_age_max: Optional[int] = None
    price_per_slot_ton: Decimal
    total_slots: int
    telegram_channel_id: Optional[str] = None
    telegram_post_id: Optional[int] = None
    comment_instruction: Optional[str] = None

class TaskCreate(TaskBase):
    pass

class TaskResponse(TaskBase):
    id: int
    creator_id: int
    completed_slots: int
    status: TaskStatus
    is_test: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class TaskListItem(BaseModel):
    id: int
    title: str
    description: Optional[str]
    task_type: TaskType
    price_per_slot_ton: Decimal
    price_per_slot_fiat: Decimal
    fiat_currency: str
    total_slots: int
    completed_slots: int
    remaining_slots: int
    telegram_channel_id: Optional[str] = None
    comment_instruction: Optional[str] = None
    is_test: bool = False
    
    class Config:
        from_attributes = True

# UserTask Schemas
class UserTaskCreate(BaseModel):
    task_id: int

class UserTaskResponse(BaseModel):
    id: int
    user_id: int
    task_id: int
    status: UserTaskStatus
    reward_ton: Decimal
    escrow_ends_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


# TON transactions
class TonTransactionResponse(BaseModel):
    id: int
    user_id: int
    to_address: str
    amount_nano: Decimal
    status: str
    tx_hash: Optional[str] = None
    idempotency_key: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TonWithdrawRequest(BaseModel):
    telegram_id: int
    to_address: str
    amount_nano: Decimal = Field(..., description="Сумма в нано-TON")
    idempotency_key: Optional[str] = None


class TonWithdrawResponse(BaseModel):
    transaction_id: int
    status: str
    tx_hash: Optional[str] = None
    message: str


class TonAdminWithdrawRequest(BaseModel):
    """Запрос на вывод с сервисного кошелька (для администратора)"""
    to_address: str
    amount_ton: Decimal = Field(..., description="Сумма в TON (не нано-TON)")
    notes: Optional[str] = None
    idempotency_key: Optional[str] = None
