#!/bin/bash
# Скрипт для запуска бэкенда

cd "$(dirname "$0")"

# Проверяем, есть ли виртуальное окружение
if [ -d "../.venv" ]; then
    echo "Активируем виртуальное окружение из корня проекта..."
    source ../.venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Активируем виртуальное окружение из backend..."
    source .venv/bin/activate
else
    echo "Виртуальное окружение не найдено, используем глобальный Python"
fi

# Устанавливаем зависимости если нужно
echo "Проверяем зависимости..."
python3 -m pip install -q -r requirements.txt

# Запускаем бэкенд
echo "Запускаем бэкенд..."
python3 run.py



