#!/bin/bash
# Скрипт для загрузки кода на GitHub

echo "🚀 Загрузка BlackMirrowMarket на GitHub"
echo ""

# Проверка, что мы в правильной директории
if [ ! -d ".git" ]; then
    echo "❌ Ошибка: .git директория не найдена"
    echo "Убедитесь, что вы находитесь в /Users/user/BlackMirrowMarket"
    exit 1
fi

# Проверка статуса
echo "📊 Статус Git:"
git status --short
echo ""

# Запрос информации
read -p "Введите ваш GitHub username: " GITHUB_USERNAME

if [ -z "$GITHUB_USERNAME" ]; then
    echo "❌ Username не может быть пустым"
    exit 1
fi

echo ""
echo "📝 Инструкции:"
echo "1. Создайте репозиторий на GitHub:"
echo "   https://github.com/new"
echo "   Название: BlackMirrowMarket"
echo "   Видимость: Private (рекомендуется)"
echo "   НЕ добавляйте README, .gitignore или лицензию!"
echo ""
echo "2. После создания репозитория нажмите Enter..."
read

# Добавление remote
echo ""
echo "🔗 Добавление remote..."
git remote remove origin 2>/dev/null
git remote add origin "https://github.com/${GITHUB_USERNAME}/BlackMirrowMarket.git"

# Проверка remote
echo ""
echo "✅ Remote настроен:"
git remote -v
echo ""

# Push
echo "📤 Загрузка кода на GitHub..."
echo "Вам может потребоваться ввести логин и пароль (или Personal Access Token)"
echo ""

git branch -M main
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Успешно! Код загружен на GitHub"
    echo "🔗 Репозиторий: https://github.com/${GITHUB_USERNAME}/BlackMirrowMarket"
    echo ""
    echo "🎉 Теперь можно настроить Railway!"
else
    echo ""
    echo "❌ Ошибка при загрузке"
    echo "Проверьте:"
    echo "1. Репозиторий создан на GitHub"
    echo "2. Правильный username: ${GITHUB_USERNAME}"
    echo "3. У вас есть доступ к репозиторию"
    echo "4. Если нужна аутентификация - используйте Personal Access Token"
fi

