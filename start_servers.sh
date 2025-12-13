#!/bin/bash

# Скрипт для запуска Backend и Frontend серверов

cd "$(dirname "$0")"

echo "🚀 Запуск BlackMirrowMarket..."
echo ""

# Очистка старых процессов
echo "🧹 Очистка старых процессов..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
sleep 1

# Запуск Backend
echo "📦 Запуск Backend на http://localhost:8000..."
cd backend
source venv/bin/activate
python3 run.py > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Ждем запуска backend
sleep 3

# Запуск Frontend
echo "🌐 Запуск Frontend на http://localhost:3000..."
cd frontend
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Серверы запущены!"
echo ""
echo "📊 Статус:"
echo "   Backend PID: $BACKEND_PID"
echo "   Frontend PID: $FRONTEND_PID"
echo ""
echo "🔗 Ссылки:"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Admin:    http://localhost:8000/admin"
echo ""
echo "📝 Логи:"
echo "   Backend:  tail -f backend.log"
echo "   Frontend: tail -f frontend.log"
echo ""
echo "⏹️  Для остановки выполните:"
echo "   kill $BACKEND_PID $FRONTEND_PID"
echo ""

# Ждем немного и проверяем
sleep 5
echo "🔍 Проверка серверов..."
if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo "   ✅ Backend работает"
else
    echo "   ⚠️  Backend может быть еще не готов (проверьте backend.log)"
fi

if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "   ✅ Frontend работает"
else
    echo "   ⏳ Frontend запускается (может занять до 30 секунд)"
fi

echo ""
echo "✨ Готово! Откройте http://localhost:3000 в браузере"



