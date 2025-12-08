#!/bin/bash
# Генерация SECRET_KEY для Railway

echo "🔐 Генерация SECRET_KEY для Railway"
echo ""
echo "Скопируйте этот ключ в переменные окружения Railway:"
echo ""
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
echo ""
echo "✅ Добавьте его в Railway → Backend → Variables → SECRET_KEY"

