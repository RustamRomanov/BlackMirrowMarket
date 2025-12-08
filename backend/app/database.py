from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Получаем URL базы данных из переменных окружения
# Если переменной нет, используем локальную SQLite по умолчанию
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./blackmirrowmarket.db")

# Проверяем, какая база используется
if DATABASE_URL.startswith("sqlite"):
    # Настройки для SQLite
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # Настройки для PostgreSQL (нужны для production)
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
