#!/bin/bash
# Скрипт для переключения Cursor на основной репозиторий

MAIN_REPO="/Users/user/BlackMirrowMarket"

echo "🔄 Переключение Cursor на основной репозиторий..."
echo "📁 Путь: $MAIN_REPO"

# Открываем папку в Finder
open "$MAIN_REPO"

# Пытаемся открыть в Cursor
open -a Cursor "$MAIN_REPO" 2>/dev/null || open -a "Cursor" "$MAIN_REPO" 2>/dev/null

# Открываем workspace файл
if [ -f "$MAIN_REPO/BlackMirrowMarket.code-workspace" ]; then
    open "$MAIN_REPO/BlackMirrowMarket.code-workspace"
fi

echo "✅ Команды выполнены!"
echo ""
echo "Если Cursor не переключился автоматически:"
echo "1. Перетащите папку $MAIN_REPO в окно Cursor"
echo "2. Или используйте Cmd+Shift+P → 'File: Open Folder...' → $MAIN_REPO"
