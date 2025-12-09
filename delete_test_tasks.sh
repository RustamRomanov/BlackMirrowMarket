#!/bin/bash

# Скрипт для удаления тестовых заданий и примеров
# Замените YOUR_DOMAIN на ваш домен Railway

DOMAIN="blackmirrowmarket-production.up.railway.app"

echo "🧹 Комплексная очистка тестовых заданий и примеров..."
RESPONSE=$(curl -s -X POST "https://${DOMAIN}/api/admin/cleanup-test-tasks")
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

echo ""
echo "✅ Готово!"

