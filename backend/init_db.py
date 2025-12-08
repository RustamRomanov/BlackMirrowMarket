"""
Скрипт для инициализации базы данных на Railway
Запускается один раз после создания PostgreSQL
"""
import os
import sys
from app.database import engine, Base
from app import models

def init_database():
    """Создание всех таблиц в базе данных"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")
    
    # Создание индексов (если нужно)
    # Можно выполнить через psql или добавить сюда

if __name__ == "__main__":
    try:
        init_database()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)

