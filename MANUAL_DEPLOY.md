# 📦 Ручной деплой (для начала)

## Простой способ развертывания без автоматизации

### Шаг 1: Подготовка сервера

```bash
# Подключение к серверу
ssh root@ваш_ip_адрес

# Установка необходимого ПО (см. DEPLOYMENT_GUIDE.md)
```

### Шаг 2: Загрузка кода на сервер

**Вариант A: Через Git (рекомендуется)**
```bash
# На сервере
cd /var/www
git clone https://github.com/ваш_username/blackmirrowmarket.git
cd blackmirrowmarket
```

**Вариант B: Через SCP/SFTP**
```bash
# На вашем компьютере
scp -r /Users/user/my-new-project/* root@ваш_ip:/var/www/blackmirrowmarket/
```

### Шаг 3: Настройка Backend

```bash
cd /var/www/blackmirrowmarket/backend

# Создание виртуального окружения
python3.11 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Создание .env файла
nano .env
# (вставить настройки из DEPLOYMENT_GUIDE.md)

# Создание таблиц
python3 -c "from app.database import engine, Base; from app import models; Base.metadata.create_all(bind=engine)"

# Создание индексов
psql -U bmm_user -d blackmirrowmarket -f database_indexes.sql
```

### Шаг 4: Настройка Frontend

```bash
cd /var/www/blackmirrowmarket/frontend

# Установка зависимостей
npm install

# Создание .env файла
echo "VITE_API_URL=https://api.ваш_домен.com" > .env

# Сборка
npm run build
```

### Шаг 5: Настройка systemd сервиса

```bash
sudo nano /etc/systemd/system/blackmirrowmarket-backend.service
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

**Запуск:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable blackmirrowmarket-backend
sudo systemctl start blackmirrowmarket-backend
```

### Шаг 6: Настройка Nginx

```bash
sudo nano /etc/nginx/sites-available/api.ваш_домен.com
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

```bash
sudo nano /etc/nginx/sites-available/app.ваш_домен.com
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

**Активация:**
```bash
sudo ln -s /etc/nginx/sites-available/api.ваш_домен.com /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/app.ваш_домен.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Шаг 7: SSL сертификат

```bash
sudo certbot --nginx -d api.ваш_домен.com -d app.ваш_домен.com
```

---

## 🔄 Обновление приложения (ручной деплой)

Когда нужно обновить код:

```bash
# Подключение к серверу
ssh root@ваш_ip_адрес

# Обновление кода
cd /var/www/blackmirrowmarket
git pull  # или загрузить файлы через SCP

# Backend
cd backend
source venv/bin/activate
pip install -r requirements.txt  # если добавились зависимости

# Frontend
cd ../frontend
npm install  # если добавились зависимости
npm run build

# Перезапуск
sudo systemctl restart blackmirrowmarket-backend
sudo systemctl reload nginx

# Проверка
sudo systemctl status blackmirrowmarket-backend
curl https://api.ваш_домен.com/health
```

---

## ✅ Проверка работы

```bash
# Проверка Backend
curl https://api.ваш_домен.com/health
# Должно вернуть: {"status":"healthy"}

# Проверка Frontend
# Открыть в браузере: https://app.ваш_домен.com

# Проверка логов
sudo journalctl -u blackmirrowmarket-backend -f
```

---

## 🆘 Решение проблем

### Backend не запускается
```bash
# Проверить логи
sudo journalctl -u blackmirrowmarket-backend -n 50

# Проверить права
sudo chown -R www-data:www-data /var/www/blackmirrowmarket

# Проверить .env файл
cat /var/www/blackmirrowmarket/backend/.env
```

### Frontend не открывается
```bash
# Проверить сборку
ls -la /var/www/blackmirrowmarket/frontend/dist

# Проверить Nginx
sudo nginx -t
sudo systemctl status nginx
```

### База данных не подключается
```bash
# Проверить подключение
psql -U bmm_user -d blackmirrowmarket -c "SELECT 1;"

# Проверить настройки
cat /var/www/blackmirrowmarket/backend/.env | grep DATABASE_URL
```

