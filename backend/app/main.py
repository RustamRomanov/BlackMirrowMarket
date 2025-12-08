from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.database import engine, Base
from app.routers import users, tasks, balance, admin, ton
from sqladmin import Admin
from app.admin import UserAdmin, UserBalanceAdmin, UserTaskAdmin, TaskAdminView, DashboardView, ProfitView, ComplaintsView, BanUserView
from app.auth_admin import authentication_backend
import os

# Создаем таблицы при запуске (с обработкой ошибок)
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Warning: Could not create tables: {e}")
    # Продолжаем работу, таблицы могут быть созданы вручную

app = FastAPI(title="BlackMirrowMarket API", version="1.0.0")

# Добавляем SessionMiddleware для работы админки (должен быть ПЕРЕД созданием admin_panel)
secret_key = os.getenv("SECRET_KEY", "super_secret_key_change_this_in_production")
app.add_middleware(SessionMiddleware, secret_key=secret_key)

# Добавляем прямые маршруты для кастомных views ДО создания admin_panel
# Это нужно, чтобы они имели приоритет над маршрутами sqladmin
from app.admin_routes import (
    get_dashboard_html,
    get_profit_html,
    get_complaints_html,
    get_ban_user_html,
    get_users_html,
    get_tasks_html,
    get_user_balance_html,
    get_user_task_html,
    get_ton_wallet_html,
)
from fastapi import Request

# Переопределяем главную страницу админки
@app.get("/admin/")
async def admin_root(request: Request):
    """Главная страница админки - перенаправляет на Dashboard"""
    return await get_dashboard_html(request)

@app.get("/admin/dashboard")
async def dashboard_route(request: Request):
    return await get_dashboard_html(request)

@app.get("/admin/profit")
@app.post("/admin/profit")
async def profit_route(request: Request):
    return await get_profit_html(request)

@app.get("/admin/complaints")
async def complaints_route(request: Request):
    return await get_complaints_html(request)

@app.get("/admin/ban-user")
@app.post("/admin/ban-user")
async def ban_user_route(request: Request):
    return await get_ban_user_html(request)

@app.get("/admin/ton")
async def ton_wallet_route(request: Request):
    return await get_ton_wallet_html(request)

@app.get("/admin/user/list")
async def users_route(request: Request):
    return await get_users_html(request)

@app.get("/admin/task/list")
async def tasks_route(request: Request):
    return await get_tasks_html(request)

@app.get("/admin/user-balance/list")
@app.post("/admin/user-balance/list")
async def user_balance_route(request: Request):
    return await get_user_balance_html(request)

@app.get("/admin/user-task/list")
async def user_task_route(request: Request):
    return await get_user_task_html(request)

# Подключаем статические файлы для админки
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import os

# Создаем директорию для статики, если её нет
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)

# Подключаем статические файлы
app.mount("/admin/static", StaticFiles(directory=static_dir), name="admin_static")

# Middleware временно отключен, чтобы не блокировать страницы sqladmin
# Скрипт меню будет добавляться через JavaScript автоматически
# app.add_middleware(AdminMenuMiddleware)

# Подключаем админку с аутентификацией
# Указываем кастомный шаблон для добавления меню
templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
admin_panel = Admin(app, engine, authentication_backend=authentication_backend, templates_dir=templates_dir)

# Регистрируем кастомные views с явными identity
admin_panel.add_view(DashboardView)
admin_panel.add_view(ProfitView)
admin_panel.add_view(ComplaintsView)
admin_panel.add_view(BanUserView)

# Регистрируем ModelView
admin_panel.add_view(UserAdmin)
admin_panel.add_view(UserBalanceAdmin)
admin_panel.add_view(TaskAdminView)
admin_panel.add_view(UserTaskAdmin)


# CORS для Telegram Mini App
# Railway домены и Telegram
cors_origins = os.getenv("CORS_ORIGINS", "https://t.me,https://web.telegram.org").split(",")
if os.getenv("ENVIRONMENT") != "production":
    cors_origins.append("http://localhost:3000")  # Для локальной разработки

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(balance.router, prefix="/api/balance", tags=["balance"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(ton.router, prefix="/api/ton", tags=["ton"])

@app.get("/")
async def root():
    return {"message": "BlackMirrowMarket API", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}


# Фоновая задача для обновления статусов TON транзакций
import asyncio
from app.ton_service import get_ton_service
from app.database import SessionLocal

async def update_ton_transactions_periodically():
    """Периодически обновляет статусы pending транзакций."""
    while True:
        try:
            await asyncio.sleep(30)  # Проверяем каждые 30 секунд
            service = get_ton_service()
            db = SessionLocal()
            try:
                await service.update_pending_transactions(db)
            finally:
                db.close()
        except Exception as e:
            print(f"Error in update_ton_transactions_periodically: {e}")
            await asyncio.sleep(60)  # При ошибке ждем дольше

async def check_deposits_periodically():
    """Периодически проверяет входящие депозиты и автоматически зачисляет на балансы."""
    while True:
        try:
            await asyncio.sleep(60)  # Проверяем каждую минуту
            service = get_ton_service()
            db = SessionLocal()
            try:
                await service.check_incoming_deposits(db)
            finally:
                db.close()
        except Exception as e:
            print(f"Error in check_deposits_periodically: {e}")
            await asyncio.sleep(120)  # При ошибке ждем дольше

@app.on_event("startup")
async def startup_event():
    """Запускаем фоновые задачи при старте приложения."""
    asyncio.create_task(update_ton_transactions_periodically())
    asyncio.create_task(check_deposits_periodically())


