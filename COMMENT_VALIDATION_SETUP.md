# Инструкция по настройке проверки комментариев через MTProto

## Что такое MTProto и зачем он нужен?

Telegram Bot API не позволяет получать комментарии к постам в каналах. Для этого нужен **Telegram Client API (MTProto)**, который работает как обычное приложение Telegram.

## Шаг 1: Получение API credentials от Telegram

1. Перейдите на https://my.telegram.org/apps
2. Войдите с вашим номером телефона (который используется для Telegram)
3. Создайте новое приложение:
   - **App title**: `BlackMirrowMarket Validator` (или любое название)
   - **Short name**: `bmm_validator` (или любое короткое имя)
   - **Platform**: `Other`
   - **Description**: `Comment validation bot for BlackMirrowMarket`
4. После создания вы получите:
   - **api_id** (число, например: 12345678)
   - **api_hash** (строка, например: abcdef1234567890abcdef1234567890)

**ВАЖНО**: Сохраните эти данные в безопасном месте!

## Шаг 2: Установка библиотеки Telethon

Добавьте в `backend/requirements.txt`:
```
telethon>=0.20.0
```

Затем установите:
```bash
cd backend
pip install telethon
```

## Шаг 3: Добавление переменных окружения

Добавьте в `.env` (локально) или в Railway Variables:

```env
TELEGRAM_API_ID=ваш_api_id
TELEGRAM_API_HASH=ваш_api_hash
TELEGRAM_PHONE=+79991234567
```

## Шаг 4: Первый запуск и авторизация

Запустите скрипт инициализации:
```bash
cd backend
python init_telegram_session.py
```

Введите код из Telegram, который придет на ваш телефон.

## Шаг 5: Обновление кода

Обновите функцию `check_comment_exists()` в `backend/app/comment_validator.py` согласно инструкции в файле.

Полная инструкция доступна в репозитории.
