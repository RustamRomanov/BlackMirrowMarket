# Инструкция по настройке и запуску

## Требования

- Python 3.9+
- Node.js 18+
- PostgreSQL 12+

## Шаг 1: Настройка базы данных

1. Создайте базу данных PostgreSQL:
```sql
CREATE DATABASE blackmirrowmarket;
```

2. Создайте пользователя (опционально):
```sql
CREATE USER blackmirrow_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE blackmirrowmarket TO blackmirrow_user;
```

## Шаг 2: Настройка Backend

1. Перейдите в директорию backend:
```bash
cd backend
```

2. Создайте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env`:
```bash
cp .env.example .env
```

5. Отредактируйте `.env` и укажите:
```
DATABASE_URL=postgresql://user:password@localhost:5432/blackmirrowmarket
TELEGRAM_BOT_TOKEN=8244581866:AAEayTkPVApVrITpEupY1mk7clo4q3Ncpms
TELEGRAM_ADMIN_BOT_TOKEN=8454417837:AAG8QQEqVGuHJJavlY4G84L9JM9JEWcZ8kg
```

6. Запустите сервер:
```bash
python run.py
# или
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

7. В другом терминале инициализируйте тестовые задания:
```bash
curl -X POST http://localhost:8000/api/admin/init-test-tasks
```

## Шаг 3: Настройка Frontend

1. Перейдите в директорию frontend:
```bash
cd frontend
```

2. Установите зависимости:
```bash
npm install
```

3. Создайте файл `.env`:
```bash
echo "VITE_API_URL=http://localhost:8000" > .env
```

4. Запустите dev сервер:
```bash
npm run dev
```

## Шаг 4: Настройка Telegram Mini App

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Найдите вашего бота: `@BlackMirrowMarketBot`
3. Отправьте команду `/newapp`
4. Выберите вашего бота
5. Укажите название приложения: `BlackMirrowMarket`
6. Укажите описание: `Маркетплейс микро-задач`
7. Загрузите фото (опционально)
8. Укажите URL Mini App: `https://your-domain.com` (или используйте ngrok для разработки)

### Использование ngrok для разработки

1. Установите ngrok: https://ngrok.com/
2. Запустите ngrok:
```bash
ngrok http 3000
```
3. Используйте полученный HTTPS URL в настройках Mini App

## Проверка работы

1. Откройте бота в Telegram: `@BlackMirrowMarketBot`
2. Нажмите на кнопку "Open App" или используйте команду `/start` и перейдите по ссылке
3. Заполните профиль (возраст, пол, страна)
4. Перейдите в раздел "Заработок" - вы должны увидеть список тестовых заданий
5. Попробуйте выполнить задание

## Структура API

API доступен по адресу: `http://localhost:8000`

Документация API (Swagger): `http://localhost:8000/docs`
Альтернативная документация (ReDoc): `http://localhost:8000/redoc`

## Устранение проблем

### Ошибка подключения к базе данных
- Проверьте, что PostgreSQL запущен
- Проверьте правильность DATABASE_URL в `.env`
- Убедитесь, что база данных создана

### Ошибка импорта модулей Python
- Убедитесь, что виртуальное окружение активировано
- Переустановите зависимости: `pip install -r requirements.txt`

### Frontend не подключается к API
- Проверьте, что backend запущен на порту 8000
- Проверьте VITE_API_URL в `.env` файле frontend
- Проверьте CORS настройки в backend

### Telegram Mini App не открывается
- Убедитесь, что используете HTTPS URL (ngrok для разработки)
- Проверьте, что frontend доступен по указанному URL
- Проверьте настройки бота в BotFather




