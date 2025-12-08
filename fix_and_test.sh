#!/bin/bash

echo "🔧 Исправление и тестирование приложения"
echo ""

# Проверяем бэкенд
echo "1. Проверка бэкенда..."
curl -s http://localhost:8000/health
echo ""
echo ""

# Создаем пользователя
echo "2. Создание тестового пользователя..."
curl -X POST http://localhost:8000/api/users/ \
  -H "Content-Type: application/json" \
  -d '{"telegram_id": 123456789, "username": "test_user", "first_name": "Test"}' \
  2>&1 | head -5
echo ""
echo ""

# Проверяем баланс
echo "3. Проверка баланса..."
curl -s http://localhost:8000/api/balance/123456789 2>&1 | head -5
echo ""
echo ""

# Инициализируем задания
echo "4. Инициализация тестовых заданий..."
curl -X POST http://localhost:8000/api/admin/init-test-tasks 2>&1 | head -5
echo ""
echo ""

# Проверяем задания
echo "5. Проверка заданий..."
curl -s "http://localhost:8000/api/tasks/?telegram_id=123456789" 2>&1 | head -10
echo ""
echo ""

echo "✅ Готово! Обновите страницу в браузере."




