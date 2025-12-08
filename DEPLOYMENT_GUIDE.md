# 🚀 Руководство по развертыванию приложения в Telegram

## 📋 План действий

### Этап 1: Выбор хостинга и сервера

#### Варианты хостинга:

1. **DigitalOcean** (рекомендуется для начала)
   - Простота настройки
   - От $6/месяц
   - Готовая поддержка Docker
   - Ссылка: https://www.digitalocean.com/

2. **Hetzner Cloud**
   - Немецкий хостинг, хорошая цена
   - От €4/месяц
   - Быстрые серверы
   - Ссылка: https://www.hetzner.com/cloud

3. **AWS / Google Cloud / Azure**
   - Для масштабирования
   - Более сложная настройка
   - Дороже, но мощнее

4. **VPS от российских провайдеров**
   - Timeweb, REG.RU и т.д.
   - От 200-300₽/месяц
   - Поддержка на русском

#### Рекомендация: DigitalOcean Droplet
- Размер: Basic, 1GB RAM, 1 vCPU (достаточно для старта)
- ОС: Ubuntu 22.04 LTS
- Регион: ближайший к вашим пользователям

---

### Этап 2: Настройка сервера

#### 2.1 Подключение к серверу
```bash
ssh root@ваш_ip_адрес
```

#### 2.2 Установка необходимого ПО
```bash
# Обновление системы
apt update && apt upgrade -y

# Установка Python 3.11
apt install python3.11 python3.11-venv python3-pip -y

# Установка Node.js 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# Установка PostgreSQL
apt install postgresql postgresql-contrib -y

# Установка Nginx (для прокси и статики)
apt install nginx -y

# Установка Certbot (для SSL)
apt install certbot python3-certbot-nginx -y

# Установка Git
apt install git -y
```

#### 2.3 Настройка PostgreSQL
```bash
# Переключение на пользователя postgres
sudo -u postgres psql

# Создание базы данных и пользователя
CREATE DATABASE blackmirrowmarket;
CREATE USER bmm_user WITH PASSWORD 'ваш_надежный_пароль';
GRANT ALL PRIVILEGES ON DATABASE blackmirrowmarket TO bmm_user;
\q
```

---

### Этап 3: Развертывание кода

#### 3.1 Клонирование репозитория
```bash
# Создание директории для приложения
mkdir -p /var/www/blackmirrowmarket
cd /var/www/blackmirrowmarket

# Клонирование репозитория (если используете Git)
# git clone https://github.com/ваш_username/blackmirrowmarket.git .

# Или загрузка файлов через SCP/SFTP
```

#### 3.2 Настройка Backend
```bash
cd /var/www/blackmirrowmarket/backend

# Создание виртуального окружения
python3.11 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Создание .env файла
nano .env
```

**Содержимое .env:**
```env
# База данных
DATABASE_URL=postgresql://bmm_user:ваш_надежный_пароль@localhost:5432/blackmirrowmarket

# TON настройки
TON_WALLET_ADDRESS=UQCc5ORf-eL7vBXVREuwMNOWq7jOUE--06Jvz95vRQt9dXXF
TON_WALLET_SEED=ваша_seed_фраза_12_слов
TONAPI_KEY=AGBMV6ZNTWRBHIYAAAAIMTWM3FZWBGA2IA775HKX67VIBS5JU6PEDWITLPECOMA2IWXARNQ

# Безопасность
SECRET_KEY=сгенерируйте_случайную_строку_минимум_32_символа
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ваш_надежный_пароль_админа

# Настройки приложения
ENVIRONMENT=production
DEBUG=False
```

**Генерация SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### 3.3 Инициализация базы данных
```bash
cd /var/www/blackmirrowmarket/backend
source venv/bin/activate

# Создание таблиц
python3 -c "from app.database import engine, Base; from app import models; Base.metadata.create_all(bind=engine)"
```

#### 3.4 Настройка Frontend
```bash
cd /var/www/blackmirrowmarket/frontend

# Установка зависимостей
npm install

# Создание .env файла
nano .env
```

**Содержимое .env:**
```env
VITE_API_URL=https://api.ваш_домен.com
```

**Сборка production версии:**
```bash
npm run build
```

---

### Этап 4: Настройка домена и SSL

#### 4.1 Покупка домена
- Рекомендуемые регистраторы: Namecheap, GoDaddy, REG.RU
- Домены: `.com`, `.io`, `.app`

#### 4.2 Настройка DNS
Добавьте A-записи в DNS вашего домена:
```
api.ваш_домен.com  -> IP_адрес_сервера
app.ваш_домен.com  -> IP_адрес_сервера
```

#### 4.3 Настройка Nginx

**Создание конфига для API:**
```bash
nano /etc/nginx/sites-available/api.ваш_домен.com
```

**Содержимое:**
```nginx
server {
    listen 80;
    server_name api.ваш_домен.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Создание конфига для Frontend:**
```bash
nano /etc/nginx/sites-available/app.ваш_домен.com
```

**Содержимое:**
```nginx
server {
    listen 80;
    server_name app.ваш_домен.com;

    root /var/www/blackmirrowmarket/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

**Активация конфигов:**
```bash
ln -s /etc/nginx/sites-available/api.ваш_домен.com /etc/nginx/sites-enabled/
ln -s /etc/nginx/sites-available/app.ваш_домен.com /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

#### 4.4 Получение SSL сертификата
```bash
certbot --nginx -d api.ваш_домен.com -d app.ваш_домен.com
```

---

### Этап 5: Настройка systemd сервисов

#### 5.1 Создание сервиса для Backend
```bash
nano /etc/systemd/system/blackmirrowmarket-backend.service
```

**Содержимое:**
```ini
[Unit]
Description=BlackMirrowMarket Backend
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/blackmirrowmarket/backend
Environment="PATH=/var/www/blackmirrowmarket/backend/venv/bin"
ExecStart=/var/www/blackmirrowmarket/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Запуск сервиса:**
```bash
systemctl daemon-reload
systemctl enable blackmirrowmarket-backend
systemctl start blackmirrowmarket-backend
systemctl status blackmirrowmarket-backend
```

---

### Этап 6: Настройка Telegram Bot

#### 6.1 Создание бота через @BotFather
1. Напишите @BotFather в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Сохраните токен бота

#### 6.2 Настройка Webhook
```bash
# Замените YOUR_BOT_TOKEN и YOUR_DOMAIN
curl -X POST "https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook?url=https://api.ваш_домен.com/webhook"
```

#### 6.3 Создание Mini App
1. В @BotFather отправьте `/newapp`
2. Выберите вашего бота
3. Укажите:
   - Title: BlackMirrowMarket
   - Short name: blackmirrowmarket
   - Description: Маркетплейс микро-задач
   - Photo: загрузите иконку
   - Web App URL: `https://app.ваш_домен.com`

---

### Этап 7: Финальная проверка

#### 7.1 Проверка Backend
```bash
curl https://api.ваш_домен.com/health
# Должен вернуть: {"status":"healthy"}
```

#### 7.2 Проверка Frontend
- Откройте в браузере: `https://app.ваш_домен.com`
- Должен открыться интерфейс приложения

#### 7.3 Проверка в Telegram
- Откройте вашего бота в Telegram
- Нажмите на кнопку "Open App" или отправьте `/start`
- Должно открыться приложение

---

### Этап 8: Мониторинг и логи

#### 8.1 Просмотр логов Backend
```bash
journalctl -u blackmirrowmarket-backend -f
```

#### 8.2 Настройка резервного копирования
```bash
# Создание скрипта бэкапа
nano /usr/local/bin/backup-bmm.sh
```

**Содержимое:**
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -U bmm_user blackmirrowmarket > /var/backups/bmm_$DATE.sql
find /var/backups -name "bmm_*.sql" -mtime +7 -delete
```

**Добавление в cron:**
```bash
crontab -e
# Добавьте строку:
0 2 * * * /usr/local/bin/backup-bmm.sh
```

---

## 🔒 Безопасность

1. **Firewall:**
```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

2. **Обновление системы:**
```bash
apt update && apt upgrade -y
```

3. **Проверка прав доступа:**
```bash
chown -R www-data:www-data /var/www/blackmirrowmarket
chmod -R 755 /var/www/blackmirrowmarket
```

---

## 📝 Чеклист перед запуском

- [ ] Сервер настроен и обновлен
- [ ] PostgreSQL установлен и база создана
- [ ] Backend запущен и работает
- [ ] Frontend собран и развернут
- [ ] Домен настроен и SSL получен
- [ ] Nginx настроен и работает
- [ ] Telegram Bot создан и webhook настроен
- [ ] Mini App создан и привязан к боту
- [ ] Переменные окружения настроены
- [ ] Резервное копирование настроено
- [ ] Firewall настроен
- [ ] Тестирование всех функций

---

## 🆘 Полезные команды

```bash
# Перезапуск Backend
systemctl restart blackmirrowmarket-backend

# Просмотр логов
journalctl -u blackmirrowmarket-backend -n 50

# Проверка статуса
systemctl status blackmirrowmarket-backend

# Обновление кода
cd /var/www/blackmirrowmarket
git pull
cd backend && source venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm install && npm run build
systemctl restart blackmirrowmarket-backend
```

---

## 📞 Поддержка

При возникновении проблем проверьте:
1. Логи Backend: `journalctl -u blackmirrowmarket-backend -f`
2. Логи Nginx: `tail -f /var/log/nginx/error.log`
3. Статус сервисов: `systemctl status blackmirrowmarket-backend`
4. Подключение к БД: `sudo -u postgres psql -d blackmirrowmarket`

