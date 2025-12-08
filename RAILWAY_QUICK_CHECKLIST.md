# ✅ Быстрый чеклист Railway

## 🚀 Шаг за шагом

### 1. Регистрация
- [ ] Зарегистрировался на https://railway.app через GitHub

### 2. Проект
- [ ] Создал проект "Deploy from GitHub repo"
- [ ] Выбрал репозиторий `BlackMirrowMarket`

### 3. PostgreSQL
- [ ] Добавил PostgreSQL базу данных
- [ ] Railway создал `DATABASE_URL` автоматически

### 4. Backend
- [ ] Создал Backend сервис (Root Directory: `backend`)
- [ ] Build Command: `pip install -r requirements.txt`
- [ ] Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- [ ] Добавил переменные окружения (см. ниже)
- [ ] Создал домен Backend
- [ ] Сохранил домен Backend: `___________________________`

### 5. База данных
- [ ] Выполнил `python3 init_db.py` через Railway Shell
- [ ] Таблицы созданы успешно

### 6. Frontend
- [ ] Создал Frontend сервис (Root Directory: `frontend`)
- [ ] Build Command: `npm install && npm run build`
- [ ] Start Command: `npx serve -s dist -l $PORT`
- [ ] Добавил `VITE_API_URL=https://ваш-backend-домен.railway.app`
- [ ] Создал домен Frontend
- [ ] Сохранил домен Frontend: `___________________________`
- [ ] Обновил `CORS_ORIGINS` в Backend с доменом Frontend

### 7. Telegram
- [ ] Настроил Mini App через @BotFather
- [ ] Указал Web App URL (домен Frontend)

### 8. Проверка
- [ ] Backend health: `https://ваш-backend-домен.railway.app/health` ✅
- [ ] Frontend открывается: `https://ваш-frontend-домен.railway.app` ✅
- [ ] Telegram Mini App работает ✅

---

## 📝 Переменные окружения Backend

```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
TON_WALLET_ADDRESS=UQCc5ORf-eL7vBXVREuwMNOWq7jOUE--06Jvz95vRQt9dXXF
TON_WALLET_SEED="ваша_seed_фраза_12_слов"
TONAPI_KEY=AGBMV6ZNTWRBHIYAAAAIMTWM3FZWBGA2IA775HKX67VIBS5JU6PEDWITLPECOMA2IWXARNQ
SECRET_KEY=ВАШ_СГЕНЕРИРОВАННЫЙ_КЛЮЧ
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ваш_пароль
ENVIRONMENT=production
DEBUG=False
CORS_ORIGINS=https://t.me,https://web.telegram.org,https://ваш-frontend-домен.railway.app
```

**Сгенерировать SECRET_KEY:**
```bash
./generate_secret_key.sh
```

---

## 📝 Переменные окружения Frontend

```env
VITE_API_URL=https://ваш-backend-домен.railway.app
```

---

## 🔗 Полезные ссылки

- Railway Dashboard: https://railway.app
- Документация: [RAILWAY_SETUP_GUIDE.md](./RAILWAY_SETUP_GUIDE.md)
- Быстрый старт: [RAILWAY_QUICK_START.md](./RAILWAY_QUICK_START.md)

