# 🗄️ Настройка базы данных для production

## 📋 Рекомендация: PostgreSQL 15+ + Redis 7+

### Почему эта комбинация:

1. **PostgreSQL** - для надежного хранения данных
   - ACID гарантии (критично для финансов)
   - Транзакции (защита от race conditions)
   - Масштабируется до миллионов записей
   - Проверено для финансовых систем

2. **Redis** - для скорости
   - Кэширование балансов (микросекунды)
   - Очереди для асинхронной обработки
   - Rate limiting
   - Счетчики и статистика

---

## 🚀 Быстрая установка

### 1. Установка PostgreSQL

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib -y

# Проверка версии
psql --version
```

### 2. Создание базы данных

```bash
sudo -u postgres psql

# В psql:
CREATE DATABASE blackmirrowmarket;
CREATE USER bmm_user WITH PASSWORD 'ваш_надежный_пароль';
GRANT ALL PRIVILEGES ON DATABASE blackmirrowmarket TO bmm_user;
\q
```

### 3. Установка Redis (опционально, но рекомендуется)

```bash
# Ubuntu/Debian
sudo apt install redis-server -y

# Запуск
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Проверка
redis-cli ping
# Должно вернуть: PONG
```

### 4. Настройка переменных окружения

В `backend/.env`:
```env
# PostgreSQL
DATABASE_URL=postgresql://bmm_user:ваш_надежный_пароль@localhost:5432/blackmirrowmarket

# Redis (опционально)
REDIS_URL=redis://localhost:6379/0
```

### 5. Создание таблиц и индексов

```bash
cd backend
source venv/bin/activate

# Создание таблиц
python3 -c "from app.database import engine, Base; from app import models; Base.metadata.create_all(bind=engine)"

# Создание индексов (для производительности)
psql -U bmm_user -d blackmirrowmarket -f database_indexes.sql
```

---

## ⚙️ Оптимизация PostgreSQL

### Настройка postgresql.conf

```bash
sudo nano /etc/postgresql/15/main/postgresql.conf
```

**Рекомендуемые настройки для 8GB RAM:**
```ini
shared_buffers = 2GB                    # 25% от RAM
effective_cache_size = 6GB              # 75% от RAM
maintenance_work_mem = 512MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1                  # Для SSD
effective_io_concurrency = 200          # Для SSD
work_mem = 20MB
min_wal_size = 1GB
max_wal_size = 4GB
max_connections = 200
```

**Перезапуск PostgreSQL:**
```bash
sudo systemctl restart postgresql
```

---

## 📊 Мониторинг производительности

### Просмотр медленных запросов

```sql
-- Включить расширение (один раз)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Просмотр топ-10 медленных запросов
SELECT 
    query,
    calls,
    total_exec_time,
    mean_exec_time,
    max_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### Просмотр использования индексов

```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;
```

---

## 🔄 Резервное копирование

### Автоматический бэкап

```bash
# Создать скрипт
sudo nano /usr/local/bin/backup-bmm.sh
```

**Содержимое:**
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/blackmirrowmarket"
mkdir -p $BACKUP_DIR

# Бэкап базы данных
pg_dump -U bmm_user blackmirrowmarket > $BACKUP_DIR/bmm_$DATE.sql

# Сжатие
gzip $BACKUP_DIR/bmm_$DATE.sql

# Удаление старых бэкапов (старше 7 дней)
find $BACKUP_DIR -name "bmm_*.sql.gz" -mtime +7 -delete

echo "Backup completed: bmm_$DATE.sql.gz"
```

**Сделать исполняемым:**
```bash
sudo chmod +x /usr/local/bin/backup-bmm.sh
```

**Добавить в cron (ежедневно в 2:00):**
```bash
sudo crontab -e
# Добавить:
0 2 * * * /usr/local/bin/backup-bmm.sh
```

---

## 🔒 Безопасность

### Ограничение доступа

```bash
sudo nano /etc/postgresql/15/main/pg_hba.conf
```

**Добавить (только локальные подключения):**
```
host    blackmirrowmarket    bmm_user    127.0.0.1/32    md5
```

**Перезапуск:**
```bash
sudo systemctl restart postgresql
```

---

## 📈 План масштабирования

### До 10,000 пользователей
- PostgreSQL на одном сервере
- Redis на том же сервере
- Базовые индексы
- Connection pooling

### 10,000 - 50,000 пользователей
- Оптимизация запросов
- Кэширование в Redis
- Мониторинг производительности

### 50,000 - 100,000 пользователей
- Read replicas
- Отдельный сервер для Redis
- Партиционирование больших таблиц

---

## ✅ Чеклист

- [ ] PostgreSQL установлен и запущен
- [ ] База данных создана
- [ ] Пользователь создан с правами
- [ ] Таблицы созданы
- [ ] Индексы созданы
- [ ] Redis установлен (опционально)
- [ ] Переменные окружения настроены
- [ ] Резервное копирование настроено
- [ ] Мониторинг настроен
- [ ] Безопасность настроена

