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
    get_deposits_html,
    check_deposit_manually,
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
# CORS: разрешаем все источники, чтобы не ломались preflight-запросы в WebApp
cors_origins = os.getenv("CORS_ORIGINS", "https://t.me,https://web.telegram.org").split(",")
if os.getenv("ENVIRONMENT") != "production":
    cors_origins.append("http://localhost:3000")  # Для локальной разработки

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # разрешаем все Origin
    allow_origin_regex=".*",      # дублируем регуляркой
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,
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
    """Периодически обновляет статусы pending транзакций и обрабатывает pending withdrawals."""
    while True:
        try:
            await asyncio.sleep(30)  # Проверяем каждые 30 секунд
            service = get_ton_service()
            if service is None:
                # TON сервис не настроен, пропускаем
                await asyncio.sleep(300)  # Проверяем реже, если не настроено
                continue
            db = SessionLocal()
            try:
                # Сначала обрабатываем pending withdrawals (попытки отправить)
                await service.process_pending_withdrawals(db)
                # Затем обновляем статусы уже отправленных транзакций
                await service.update_pending_transactions(db)
            finally:
                db.close()
        except Exception as e:
            import traceback
            print(f"Error in update_ton_transactions_periodically: {e}", file=sys.stderr, flush=True)
            traceback.print_exc()
            await asyncio.sleep(60)  # При ошибке ждем дольше

async def check_deposits_periodically():
    """Периодически проверяет входящие депозиты и автоматически зачисляет на балансы."""
    import sys
    print("🔄 Фоновая задача проверки депозитов запущена", file=sys.stderr, flush=True)
    while True:
        try:
            await asyncio.sleep(60)  # Проверяем каждую минуту
            import sys
            print("⏰ Время проверки депозитов (каждую минуту)", file=sys.stderr, flush=True)
            service = get_ton_service()
            if service is None:
                # TON сервис не настроен, пропускаем
                print("⚠️ TON сервис не настроен (get_ton_service вернул None), пропускаем проверку депозитов", file=sys.stderr, flush=True)
                await asyncio.sleep(300)  # Проверяем реже, если не настроено
                continue
            
            # Проверяем, что api_key и wallet_address установлены
            if not service.api_key or not service.wallet_address:
                print(f"⚠️ TON сервис создан, но api_key={bool(service.api_key)}, wallet_address={bool(service.wallet_address)}. Пропускаем проверку.", file=sys.stderr, flush=True)
                await asyncio.sleep(300)  # Проверяем реже, если не настроено
                continue
            
            print("🔍 Проверка входящих депозитов...", file=sys.stderr, flush=True)
            db = SessionLocal()
            try:
                await service.check_incoming_deposits(db)
                print("✅ Проверка депозитов завершена", file=sys.stderr, flush=True)
            except Exception as deposit_error:
                import traceback
                print(f"❌ Ошибка при проверке депозитов: {deposit_error}", file=sys.stderr, flush=True)
                traceback.print_exc()
            finally:
                db.close()
        except Exception as e:
            # Не спамим логи обычными ошибками
            import sys, traceback
            error_msg = str(e)
            if "404" not in error_msg and "not set" not in error_msg:
                print(f"❌ Error in check_deposits_periodically: {e}", file=sys.stderr, flush=True)
                traceback.print_exc()
            await asyncio.sleep(120)  # При ошибке ждем дольше


@app.on_event("startup")
async def startup_event():
    """Запускаем фоновые задачи при старте приложения."""
    import sys
    print("🚀 Запуск приложения...")
    
    # Удаляем тестовые задания и примеры при старте
    from app.database import SessionLocal
    from app.models import Task, User, UserTask, TonTransaction, UserBalance
    from datetime import datetime, timedelta
    from decimal import Decimal
    db = SessionLocal()
    try:
        # Помечаем старые pending транзакции без tx_hash как failed
        # Средства НЕ списывались, так что возвращать нечего
        print("🔄 Checking for old pending transactions without tx_hash...", file=sys.stderr, flush=True)
        old_pending_txs = db.query(TonTransaction).filter(
            TonTransaction.status == "pending",
            TonTransaction.tx_hash.is_(None)
        ).all()
        
        failed_count = 0
        for tx in old_pending_txs:
            # Проверяем, сколько времени прошло
            time_since_creation = datetime.utcnow() - (tx.created_at.replace(tzinfo=None) if tx.created_at and tx.created_at.tzinfo else tx.created_at) if tx.created_at else timedelta(0)
            
            # Если транзакция старше 1 минуты - помечаем как failed
            # Средства НЕ списывались, так что возвращать нечего
            if time_since_creation > timedelta(minutes=1):
                tx.status = "failed"
                tx.error_message = f"Transaction failed on startup: could not send after {time_since_creation}. Funds were never deducted."
                failed_count += 1
                if tx.user_id:
                    user = db.query(User).filter(User.id == tx.user_id).first()
                    if user:
                        print(f"⚠️ Startup: Marked transaction {tx.id} as failed for user {user.telegram_id} (funds were never deducted)", file=sys.stderr, flush=True)
        
        if failed_count > 0:
            db.commit()
            print(f"✅ Startup: Marked {failed_count} old pending transactions as failed (funds were never deducted)", file=sys.stderr, flush=True)
        
        # Удаляем тестовые задания (is_test=True)
        test_tasks = db.query(Task).filter(Task.is_test == True).all()
        test_count = len(test_tasks)
        for task in test_tasks:
            # Удаляем связанные UserTask записи
            db.query(UserTask).filter(UserTask.task_id == task.id).delete()
            db.delete(task)
        
        # Удаляем примеры заданий (созданные тестовыми пользователями - telegram_id <= 0)
        test_users = db.query(User).filter(User.telegram_id <= 0).all()
        example_count = 0
        if test_users:
            test_user_ids = [u.id for u in test_users]
            example_tasks = db.query(Task).filter(
                Task.creator_id.in_(test_user_ids)
            ).all()
            example_count = len(example_tasks)
            for task in example_tasks:
                # Удаляем связанные UserTask записи
                db.query(UserTask).filter(UserTask.task_id == task.id).delete()
                db.delete(task)
            if example_count > 0:
                print(f"🗑️ Удалено {example_count} примеров заданий")
        
        db.commit()
        if test_count > 0:
            print(f"🗑️ Удалено {test_count} тестовых заданий")
        # Убрано сообщение о том, что тестовые задания не найдены - это нормально
    except Exception as e:
        print(f"⚠️ Ошибка при удалении тестовых заданий: {e}")
        db.rollback()
    finally:
        db.close()
    
    print("🔄 Запуск фоновых задач...")
    asyncio.create_task(update_ton_transactions_periodically())
    asyncio.create_task(check_deposits_periodically())
    print("✅ Фоновые задачи запущены")


