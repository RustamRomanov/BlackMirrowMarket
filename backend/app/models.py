from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, ForeignKey, Numeric, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum

class TaskType(str, enum.Enum):
    SUBSCRIPTION = "subscription"
    COMMENT = "comment"
    VIEW = "view"

class UserRole(str, enum.Enum):
    USER = "user"
    MODERATOR = "moderator"
    OWNER = "owner"

class TaskStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class UserTaskStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    
    # Профиль (обязательные поля)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)  # male, female, other
    country = Column(String, nullable=True)
    
    # Реферальная система
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Кто пригласил
    referral_code = Column(String(20), unique=True, nullable=True, index=True)  # Уникальный код для реферальной ссылки
    terms_accepted = Column(Boolean, default=False)  # Принял ли правила и соглашение
    
    role = Column(SQLEnum(UserRole), default=UserRole.USER)
    is_banned = Column(Boolean, default=False)
    ban_until = Column(DateTime(timezone=True), nullable=True)  # До какой даты заблокирован
    ban_reason = Column(Text, nullable=True)  # Причина блокировки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    balance = relationship("UserBalance", back_populates="user", uselist=False)
    created_tasks = relationship("Task", back_populates="creator")
    user_tasks = relationship("UserTask", back_populates="user")
    referrer = relationship("User", remote_side=[id], backref="referrals")

class UserBalance(Base):
    __tablename__ = "user_balances"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Балансы в нано-TON
    ton_active_balance = Column(Numeric(20, 0), default=0)  # Может быть отрицательным
    ton_escrow_balance = Column(Numeric(20, 0), default=0)
    ton_referral_earnings = Column(Numeric(20, 0), default=0)  # Заработок с рефералов
    
    # Курс валют
    last_fiat_rate = Column(Numeric(10, 2), default=0)  # TON к фиату
    fiat_currency = Column(String(3), default="RUB")
    
    # Динамический лимит подписок
    subscription_limit_24h = Column(Integer, default=100)
    subscriptions_used_24h = Column(Integer, default=0)
    last_limit_reset = Column(DateTime(timezone=True), server_default=func.now())
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="balance")

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(SQLEnum(TaskType), nullable=False)
    
    # Таргетинг
    target_country = Column(String, nullable=True)
    target_gender = Column(String, nullable=True)
    target_age_min = Column(Integer, nullable=True)
    target_age_max = Column(Integer, nullable=True)
    
    # Финансы
    price_per_slot_ton = Column(Numeric(20, 0), nullable=False)  # В нано-TON
    total_slots = Column(Integer, nullable=False)
    completed_slots = Column(Integer, default=0)
    
    # Информация о задании
    telegram_channel_id = Column(String, nullable=True)  # Для подписки/комментария
    telegram_post_id = Column(Integer, nullable=True)  # Для комментария/просмотра
    comment_instruction = Column(Text, nullable=True)  # Инструкция для комментария
    
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.ACTIVE)
    is_test = Column(Boolean, default=False)  # Для условных заданий
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    creator = relationship("User", back_populates="created_tasks")
    user_tasks = relationship("UserTask", back_populates="task")

class UserTask(Base):
    __tablename__ = "user_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    
    status = Column(SQLEnum(UserTaskStatus), default=UserTaskStatus.PENDING)
    reward_ton = Column(Numeric(20, 0), nullable=False)
    
    # Эскроу
    escrow_started_at = Column(DateTime(timezone=True), nullable=True)
    escrow_ends_at = Column(DateTime(timezone=True), nullable=True)
    
    # Валидация
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validation_result = Column(Boolean, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="user_tasks")
    task = relationship("Task", back_populates="user_tasks")

class Referral(Base):
    __tablename__ = "referrals"
    
    id = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Кто пригласил
    referred_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)  # Кого пригласили
    
    total_earned_ton = Column(Numeric(20, 0), default=0)  # Сколько заработал реферал
    referral_commission_ton = Column(Numeric(20, 0), default=0)  # Сколько получил реферер (5%)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    referrer = relationship("User", foreign_keys=[referrer_id], backref="referral_records")
    referred = relationship("User", foreign_keys=[referred_id])

class TaskReportStatus(str, enum.Enum):
    PENDING = "pending"  # Ожидает рассмотрения
    REVIEWING = "reviewing"  # На рассмотрении
    RESOLVED = "resolved"  # Решено
    REJECTED = "rejected"  # Отклонено

class TaskReport(Base):
    __tablename__ = "task_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Кто пожаловался
    
    reason = Column(Text, nullable=True)  # Причина жалобы
    status = Column(SQLEnum(TaskReportStatus), default=TaskReportStatus.PENDING)
    
    moderator_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Кто рассмотрел
    moderator_notes = Column(Text, nullable=True)  # Заметки модератора
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    task = relationship("Task", backref="reports")
    reporter = relationship("User", foreign_keys=[reporter_id], backref="reports_made")
    moderator = relationship("User", foreign_keys=[moderator_id], backref="reports_moderated")

class ProfitWithdrawal(Base):
    __tablename__ = "profit_withdrawals"

    id = Column(Integer, primary_key=True, index=True)
    amount_ton = Column(Numeric(20, 9), nullable=False)  # Сумма вывода в TON
    wallet_address = Column(String(255), nullable=False)  # Адрес кошелька для вывода
    status = Column(String(50), default="pending")  # pending, completed, rejected
    admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Кто вывел
    notes = Column(Text, nullable=True)  # Заметки

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    admin_user = relationship("User", backref="profit_withdrawals")


class TonTransaction(Base):
    __tablename__ = "ton_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Опционально для админских выводов
    to_address = Column(String(255), nullable=False)
    amount_nano = Column(Numeric(20, 0), nullable=False)
    status = Column(String(50), default="pending")  # pending, completed, failed
    tx_hash = Column(String(255), nullable=True, index=True)
    idempotency_key = Column(String(255), unique=True, nullable=False)
    error_message = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)  # Заметки администратора
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref="ton_transactions")


class Deposit(Base):
    """Входящие депозиты на сервисный кошелек"""
    __tablename__ = "deposits"

    id = Column(Integer, primary_key=True, index=True)
    tx_hash = Column(String(255), unique=True, nullable=False, index=True)
    from_address = Column(String(255), nullable=False)
    amount_nano = Column(Numeric(20, 0), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Определяется по комментарию
    telegram_id_from_comment = Column(String(50), nullable=True)  # Telegram ID из комментария транзакции
    status = Column(String(50), default="pending")  # pending, processed, failed
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="deposits")
