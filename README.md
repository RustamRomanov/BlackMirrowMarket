# BlackMirrowMarket - Telegram Mini App

Маркетплейс микро-задач для Telegram с интеграцией TON блокчейна.

## 🚀 Быстрый старт

### Локальная разработка

**Backend:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Деплой на Railway

См. [RAILWAY_QUICK_START.md](./RAILWAY_QUICK_START.md) для быстрого деплоя.

## 📁 Структура проекта

```
BlackMirrowMarket/
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── models.py      # SQLAlchemy модели
│   │   ├── schemas.py     # Pydantic схемы
│   │   ├── database.py    # Настройка БД
│   │   ├── main.py        # Точка входа FastAPI
│   │   └── routers/       # API роутеры
│   └── requirements.txt
├── frontend/         # React + TypeScript Mini App
│   ├── src/
│   │   ├── pages/         # Страницы приложения
│   │   ├── components/    # React компоненты
│   │   └── context/       # React контекст
│   └── package.json
└── README.md
```

## 🗄️ База данных

- **PostgreSQL** - основная БД (production)
- **SQLite** - для локальной разработки
- **Redis** - кэширование (опционально)

См. [DATABASE_ARCHITECTURE.md](./DATABASE_ARCHITECTURE.md) для подробностей.

## 🚂 Деплой

- **Railway** - рекомендуемый способ для быстрого старта
- **VPS** - для долгосрочного использования

См. [RAILWAY_SETUP.md](./RAILWAY_SETUP.md) или [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)

## 🔧 Технологии

- **Backend:** FastAPI, SQLAlchemy, PostgreSQL
- **Frontend:** React, TypeScript, Vite
- **Blockchain:** TON (pytoniq, tonapi.io)
- **Admin:** SQLAdmin

## 📝 Документация

- [RAILWAY_QUICK_START.md](./RAILWAY_QUICK_START.md) - Быстрый деплой на Railway
- [RAILWAY_SETUP.md](./RAILWAY_SETUP.md) - Подробная инструкция по Railway
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - Деплой на VPS
- [DATABASE_ARCHITECTURE.md](./DATABASE_ARCHITECTURE.md) - Архитектура БД
- [DATABASE_SETUP.md](./DATABASE_SETUP.md) - Настройка PostgreSQL

## 🔒 Безопасность

- Все секреты хранятся в переменных окружения
- Не коммитьте `.env` файлы
- Используйте сильные пароли
- Регулярно обновляйте зависимости

## 📄 Лицензия

Private project
