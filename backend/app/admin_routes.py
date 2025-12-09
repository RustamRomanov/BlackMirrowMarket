"""Прямые роутеры для админки, обходящие sqladmin BaseView"""
from fastapi import Request
from fastapi.responses import HTMLResponse
from app.models import (
    User,
    Task,
    UserBalance,
    UserTask,
    UserRole,
    TaskStatus,
    UserTaskStatus,
    TaskReport,
    TaskReportStatus,
    TonTransaction,
    Deposit,
)
from sqlalchemy import func, and_
from app.database import SessionLocal
from datetime import datetime, timedelta
from app.ton_service import get_ton_service
from decimal import Decimal
import os

def get_sidebar_html(active_page="dashboard"):
    """Генерирует боковое меню"""
    pages = {
        "dashboard": "/admin/dashboard",
        "profit": "/admin/profit",
        "deposits": "/admin/deposits",
        "ton": "/admin/ton",
        "complaints": "/admin/complaints",
        "ban-user": "/admin/ban-user",
        "user": "/admin/user/list",
        "task": "/admin/task/list",
        "user-balance": "/admin/user-balance/list",
        "user-task": "/admin/user-task/list"
    }
    
    return f"""
    <div class="sidebar">
        <div class="sidebar-header">
            <h2>📊 Админка</h2>
        </div>
        <nav class="sidebar-nav">
            <a href="/admin/dashboard" class="nav-item {'active' if active_page == 'dashboard' else ''}">
                <span class="nav-icon">📊</span>
                <span class="nav-text">Главная</span>
            </a>
            <a href="/admin/profit" class="nav-item {'active' if active_page == 'profit' else ''}">
                <span class="nav-icon">💰</span>
                <span class="nav-text">Прибыль</span>
            </a>
            <a href="/admin/deposits" class="nav-item {'active' if active_page == 'deposits' else ''}">
                <span class="nav-icon">💳</span>
                <span class="nav-text">Депозиты</span>
            </a>
            <a href="/admin/ton" class="nav-item {'active' if active_page == 'ton' else ''}">
                <span class="nav-icon">🪙</span>
                <span class="nav-text">TON Кошелек</span>
            </a>
            <a href="/admin/complaints" class="nav-item {'active' if active_page == 'complaints' else ''}">
                <span class="nav-icon">🚩</span>
                <span class="nav-text">Жалобы</span>
            </a>
            <a href="/admin/ban-user" class="nav-item {'active' if active_page == 'ban-user' else ''}">
                <span class="nav-icon">🚫</span>
                <span class="nav-text">Блокировка</span>
            </a>
            <a href="/admin/user/list" class="nav-item {'active' if active_page == 'user' else ''}">
                <span class="nav-icon">👥</span>
                <span class="nav-text">Пользователи</span>
            </a>
            <a href="/admin/task/list" class="nav-item {'active' if active_page == 'task' else ''}">
                <span class="nav-icon">📋</span>
                <span class="nav-text">Задания</span>
            </a>
            <a href="/admin/user-balance/list" class="nav-item {'active' if active_page == 'user-balance' else ''}">
                <span class="nav-icon">💳</span>
                <span class="nav-text">Балансы</span>
            </a>
            <a href="/admin/user-task/list" class="nav-item {'active' if active_page == 'user-task' else ''}">
                <span class="nav-icon">⏱️</span>
                <span class="nav-text">Выполнения</span>
            </a>
        </nav>
    </div>
    """

def get_base_styles():
    """Базовые стили для всех страниц"""
    return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #333; line-height: 1.6; display: flex; }
        .sidebar { width: 260px; background: #2c3e50; color: white; min-height: 100vh; position: fixed; left: 0; top: 0; overflow-y: auto; }
        .sidebar-header { padding: 20px; background: #1a252f; border-bottom: 1px solid #34495e; }
        .sidebar-header h2 { font-size: 20px; font-weight: 600; }
        .sidebar-nav { padding: 10px 0; }
        .nav-item { display: flex; align-items: center; padding: 12px 20px; color: #ecf0f1; text-decoration: none; transition: all 0.3s; border-left: 3px solid transparent; }
        .nav-item:hover { background: #34495e; border-left-color: #3498db; }
        .nav-item.active { background: #34495e; border-left-color: #3498db; font-weight: 600; }
        .nav-icon { font-size: 18px; margin-right: 12px; width: 24px; text-align: center; }
        .nav-text { font-size: 15px; }
        .main-content { margin-left: 260px; flex: 1; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .header h1 { font-size: 32px; margin-bottom: 10px; }
        .header p { font-size: 16px; opacity: 0.9; }
        table { width: 100%; background: white; border-collapse: collapse; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #667eea; color: white; font-weight: 600; }
        tr:hover { background: #f5f5f5; }
        .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
        .badge-success { background: #4caf50; color: white; }
        .badge-warning { background: #ff9800; color: white; }
        .badge-danger { background: #f44336; color: white; }
        .badge-info { background: #2196f3; color: white; }
        .badge-secondary { background: #9e9e9e; color: white; }
        .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; }
        .card h2 { margin-bottom: 15px; color: #333; }
        .card h3 { margin-bottom: 10px; }
        .muted { color: #777; font-size: 14px; }
        .content-header { margin-bottom: 20px; }
        .content-header h1 { font-size: 28px; color: #333; }
        .data-table { width: 100%; background: white; border-collapse: collapse; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .data-table th { background: #667eea; color: white; font-weight: 600; padding: 12px 15px; text-align: left; }
        .data-table td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }
        .data-table tr:hover { background: #f5f5f5; }
    """

async def get_dashboard_html(request: Request):
    """Главная страница админки"""
    db = SessionLocal()
    try:
        total_users = db.query(User).count()
        # Только реальные задания (без тестовых)
        active_tasks = db.query(Task).filter(
            Task.status == TaskStatus.ACTIVE,
            Task.is_test == False
        ).count()
        completed_tasks = db.query(UserTask).filter(UserTask.status == UserTaskStatus.COMPLETED).count()
        pending_reports = db.query(TaskReport).filter(TaskReport.status == TaskReportStatus.PENDING).count()
        
        # Суммируем только реальные балансы пользователей (с проверкой на None)
        total_balance_nano = db.query(func.sum(UserBalance.ton_active_balance)).scalar() or 0
        total_balance_ton = round(float(total_balance_nano) / 10**9, 4) if total_balance_nano else 0.0
        
        # Получаем реальный баланс сервисного кошелька
        from app.ton_service import get_ton_service
        try:
            service = get_ton_service()
            wallet_balance_nano = await service.get_wallet_balance()
            wallet_balance_ton = round(float(wallet_balance_nano) / 10**9, 4)
        except Exception as e:
            print(f"Error getting wallet balance: {e}")
            wallet_balance_ton = 0.0
        
        # Прибыль = реальный баланс кошелька минус выведенные средства
        from app.models import TonTransaction, ProfitWithdrawal
        withdrawn_nano = db.query(func.sum(TonTransaction.amount_nano)).filter(
            TonTransaction.status == "completed",
            TonTransaction.user_id.is_(None)  # Админские выводы
        ).scalar() or 0
        withdrawn_ton = round(float(withdrawn_nano) / 10**9, 4) if withdrawn_nano else 0.0
        
        # Реальная прибыль = текущий баланс кошелька (уже учитывает все транзакции)
        app_profit_ton = wallet_balance_ton
        
        # Оборот считаем из реальных транзакций (депозиты)
        from app.models import Deposit
        total_deposits_nano = db.query(func.sum(Deposit.amount_nano)).filter(
            Deposit.status == "processed"
        ).scalar() or 0
        total_turnover_ton = round(float(total_deposits_nano) / 10**9, 4) if total_deposits_nano else 0.0
        
        today = datetime.now().date()
        today_users = db.query(User).filter(func.date(User.created_at) == today).count()
        # Только реальные задания (без тестовых)
        today_tasks = db.query(Task).filter(
            func.date(Task.created_at) == today,
            Task.is_test == False
        ).count()
        today_completed = db.query(UserTask).filter(
            and_(
                UserTask.status == UserTaskStatus.COMPLETED,
                func.date(UserTask.created_at) == today
            )
        ).count()
        
        week_ago = datetime.now() - timedelta(days=7)
        week_users = db.query(User).filter(User.created_at >= week_ago).count()
        # Только реальные задания (без тестовых)
        week_tasks = db.query(Task).filter(
            Task.created_at >= week_ago,
            Task.is_test == False
        ).count()
    finally:
        db.close()

    sidebar_html = get_sidebar_html("dashboard")
    
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Главная - Админка BlackMirrowMarket</title>
    <style>
        {get_base_styles()}
        .info-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        .info-box strong {{ color: #1976d2; display: block; margin-bottom: 10px; font-size: 18px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }}
        .stat-card {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-top: 4px solid #667eea; }}
        .stat-card h3 {{ color: #666; font-size: 14px; text-transform: uppercase; margin-bottom: 10px; }}
        .stat-card .value {{ font-size: 36px; font-weight: bold; color: #333; }}
        .stat-card .sub {{ color: #999; font-size: 14px; margin-top: 5px; }}
        .actions-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 30px 0; }}
        .action-card {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .action-card h3 {{ color: #667eea; margin-bottom: 15px; font-size: 20px; }}
        .action-card ul {{ list-style: none; }}
        .action-card li {{ padding: 10px 0; border-bottom: 1px solid #eee; }}
        .action-card a {{ color: #667eea; text-decoration: none; font-weight: 500; }}
        .action-card a:hover {{ text-decoration: underline; }}
        .alert {{ padding: 15px; border-radius: 8px; margin: 15px 0; }}
        .alert-success {{ background: #e8f5e9; border-left: 4px solid #4caf50; color: #2e7d32; }}
        .alert-warning {{ background: #fff3cd; border-left: 4px solid #ffc107; color: #856404; }}
        .btn {{ display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin-top: 10px; }}
        .btn:hover {{ background: #5568d3; }}
    </style>
</head>
<body>
    {sidebar_html}
    <div class="main-content">
    <div class="container">
        <div class="header">
            <h1>📊 Центр управления BlackMirrowMarket</h1>
            <p>Добро пожаловать в админ-панель! Здесь вы можете управлять пользователями, заданиями, отслеживать прибыль и обрабатывать жалобы.</p>
        </div>

        <div class="info-box">
            <strong>📖 Начало работы:</strong>
            Используйте меню слева для навигации. Каждый раздел имеет описание и подсказки. Если что-то непонятно - читайте инструкции в каждом разделе.
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h3>Всего пользователей</h3>
                <div class="value">{total_users}</div>
                <div class="sub">+{today_users} сегодня</div>
            </div>
            <div class="stat-card">
                <h3>Активные задания</h3>
                <div class="value">{active_tasks}</div>
                <div class="sub">+{today_tasks} сегодня</div>
            </div>
            <div class="stat-card">
                <h3>Прибыль приложения</h3>
                <div class="value">{app_profit_ton} TON</div>
                <div class="sub">Оборот: {total_turnover_ton} TON</div>
            </div>
            <div class="stat-card">
                <h3>Выполнено заданий</h3>
                <div class="value">{completed_tasks}</div>
                <div class="sub">+{today_completed} сегодня</div>
            </div>
        </div>

        <div class="actions-grid">
            <div class="action-card">
                <h3>📌 Быстрые действия</h3>
                <ul>
                    <li><a href="/admin/profit">💰 Прибыль</a> - Детальная финансовая статистика и расчет прибыли</li>
                    <li><a href="/admin/complaints">🚩 Жалобы</a> - Обработка жалоб пользователей ({pending_reports} ожидают)</li>
                    <li><a href="/admin/ban-user">🚫 Блокировка пользователя</a> - Удобная форма для блокировки</li>
                    <li><a href="/admin/user/list">👥 Пользователи</a> - Управление пользователями и ролями</li>
                    <li><a href="/admin/task/list">📋 Задания</a> - Модерация заданий</li>
                    <li><a href="/admin/user-balance/list">💳 Балансы</a> - Управление балансами</li>
                    <li><a href="/admin/user-task/list">⏱️ Выполнения</a> - История выполнения заданий</li>
                </ul>
            </div>
            <div class="action-card">
                <h3>🆘 Требуют внимания</h3>
                {"<div class='alert alert-warning'><strong>⚠️ Есть жалобы!</strong> " + str(pending_reports) + " жалоб(ы) ожидают рассмотрения.<br><a href='/admin/complaints' class='btn'>Перейти к жалобам</a></div>" if pending_reports > 0 else "<div class='alert alert-success'><strong>✅ Все хорошо!</strong> Нет жалоб, требующих внимания.</div>"}
                <div style="margin-top: 20px;">
                    <h4>Статистика за неделю:</h4>
                    <ul>
                        <li>Новых пользователей: {week_users}</li>
                        <li>Создано заданий: {week_tasks}</li>
                    </ul>
                </div>
            </div>
        </div>

        <div class="action-card" style="margin-top: 20px;">
            <h3>ℹ️ О разделах админки</h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 15px;">
                <div>
                    <h4>💰 Прибыль</h4>
                    <p style="color: #666; font-size: 14px;">Показывает общий оборот, прибыль приложения (5% комиссия), статистику по типам заданий и периодам.</p>
                </div>
                <div>
                    <h4>🚩 Жалобы</h4>
                    <p style="color: #666; font-size: 14px;">Здесь отображаются все жалобы пользователей на задания. Вы можете решить жалобу (заблокировать задание) или отклонить её.</p>
                </div>
                <div>
                    <h4>👥 Пользователи</h4>
                    <p style="color: #666; font-size: 14px;">Управление пользователями: просмотр профилей, бан, назначение модераторов, изменение ролей.</p>
                </div>
                <div>
                    <h4>📋 Задания</h4>
                    <p style="color: #666; font-size: 14px;">Список всех заданий. Можно редактировать, удалять, менять статус (активно/приостановлено).</p>
                </div>
                <div>
                    <h4>💳 Балансы</h4>
                    <p style="color: #666; font-size: 14px;">Просмотр балансов всех пользователей. Можно вручную пополнять балансы для тестирования.</p>
                </div>
                <div>
                    <h4>⏱️ Выполнения</h4>
                    <p style="color: #666; font-size: 14px;">История выполнения заданий пользователями. Статусы: ожидает, в процессе, выполнено, провалено.</p>
                </div>
            </div>
        </div>
    </div>
    </div>
    </div>
    <script src="/admin/static/admin_menu.js"></script>
</body>
</html>"""
    
    return HTMLResponse(content=html)


# ---------------------------
# Депозиты: просмотр и ручная проверка
# ---------------------------


async def get_deposits_html(request: Request):
    """Страница депозитов - просмотр всех входящих депозитов"""
    db = SessionLocal()
    try:
        deposits = db.query(Deposit).order_by(Deposit.created_at.desc()).limit(100).all()

        # Статистика
        total_deposits = db.query(func.count(Deposit.id)).scalar() or 0
        pending_deposits = db.query(func.count(Deposit.id)).filter(Deposit.status == "pending").scalar() or 0
        processed_deposits = db.query(func.count(Deposit.id)).filter(Deposit.status == "processed").scalar() or 0
        total_amount_nano = db.query(func.sum(Deposit.amount_nano)).filter(Deposit.status == "processed").scalar() or 0
        total_amount_ton = round(float(total_amount_nano) / 10**9, 4) if total_amount_nano else 0.0

        deposits_html = ""
        for d in deposits:
            amount_ton = round(float(d.amount_nano) / 10**9, 4)
            status_emoji = "✅" if d.status == "processed" else ("⏳" if d.status == "pending" else "❌")
            status_color = "green" if d.status == "processed" else ("orange" if d.status == "pending" else "red")
            user_info = ""
            if d.user:
                user_info = f'<a href="/admin/user/detail/{d.user.id}">@{d.user.username or "N/A"} (ID: {d.user.id})</a>'
            elif d.telegram_id_from_comment:
                user_info = f'<span style="color: orange;">Telegram ID: {d.telegram_id_from_comment} (пользователь не найден)</span>'
            else:
                user_info = '<span style="color: red;">ID не указан</span>'

            processed_at = d.processed_at.strftime("%Y-%m-%d %H:%M:%S") if d.processed_at else "—"
            created_at = d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else "—"

            deposits_html += f"""
            <tr>
                <td>{d.id}</td>
                <td><code style="font-size: 11px;">{d.tx_hash[:20]}...</code></td>
                <td><code style="font-size: 11px;">{d.from_address[:20]}...</code></td>
                <td><strong>{amount_ton:.4f} TON</strong></td>
                <td>{user_info}</td>
                <td><span style="color: {status_color};">{status_emoji} {d.status}</span></td>
                <td>{created_at}</td>
                <td>{processed_at}</td>
                <td>
                    <a href="https://tonscan.org/tx/{d.tx_hash}" target="_blank" style="color: #667eea;">🔍 Проверить</a>
                </td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Депозиты - Админка</title>
    <style>
        {get_base_styles()}
        .content-header {{ margin-bottom: 20px; }}
        .content-header h1 {{ font-size: 28px; color: #333; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-label {{
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .card h2 {{ margin-bottom: 15px; color: #333; }}
        .data-table {{ width: 100%; background: white; border-collapse: collapse; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .data-table th {{ background: #667eea; color: white; font-weight: 600; padding: 12px 15px; text-align: left; }}
        .data-table td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }}
        .data-table tr:hover {{ background: #f5f5f5; }}
    </style>
</head>
<body>
    {get_sidebar_html("deposits")}
    <div class="main-content">
        <div class="content-header">
            <h1>💳 Депозиты</h1>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Всего депозитов</div>
                <div class="stat-value">{total_deposits}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Обработано</div>
                <div class="stat-value" style="color: green;">{processed_deposits}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Ожидают обработки</div>
                <div class="stat-value" style="color: orange;">{pending_deposits}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Общая сумма</div>
                <div class="stat-value">{total_amount_ton:.4f} TON</div>
            </div>
        </div>

        <div class="card">
            <h2>Последние депозиты</h2>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>TX Hash</th>
                        <th>Отправитель</th>
                        <th>Сумма</th>
                        <th>Пользователь</th>
                        <th>Статус</th>
                        <th>Создан</th>
                        <th>Обработан</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    {deposits_html if deposits_html else '<tr><td colspan="9" style="text-align: center;">Депозитов не найдено</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="card" style="margin-top: 20px;">
            <h2>🔍 Ручная проверка транзакции</h2>
            <form method="POST" action="/admin/deposits/check" style="display: flex; gap: 10px; align-items: center;">
                <input type="text" name="tx_hash" placeholder="Введите TX Hash транзакции" required style="flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 4px;">
                <button type="submit" style="padding: 10px 20px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer;">Проверить</button>
            </form>
            <p style="margin-top: 10px; color: #666; font-size: 14px;">
                Введите хеш транзакции для проверки через tonapi.io. Система автоматически создаст запись о депозите, если транзакция найдена.
            </p>
        </div>
    </div>
    <script src="/admin/static/admin_menu.js"></script>
</body>
</html>
        """

        return HTMLResponse(content=html)
    finally:
        db.close()


async def check_deposit_manually(request: Request):
    """Ручная проверка транзакции через tonapi.io с автоматической обработкой"""
    if request.method != "POST":
        return HTMLResponse(content="<h1>Метод не поддерживается</h1>", status_code=405)

    form = await request.form()
    tx_hash = form.get("tx_hash", "").strip()

    if not tx_hash:
        return HTMLResponse(content="<h1>Ошибка: TX Hash не указан</h1>", status_code=400)

    db = SessionLocal()
    try:
        existing = db.query(Deposit).filter(Deposit.tx_hash == tx_hash).first()
        if existing:
            user_info = ""
            if existing.user_id:
                user = db.query(User).filter(User.id == existing.user_id).first()
                if user:
                    user_info = f"Пользователь: @{user.username or 'user'} (Telegram ID: {user.telegram_id})"
            
            return HTMLResponse(content=f"""
                <h1>Транзакция уже существует в базе</h1>
                <p><strong>TX Hash:</strong> {tx_hash}</p>
                <p><strong>Статус:</strong> {existing.status}</p>
                <p><strong>Сумма:</strong> {float(existing.amount_nano) / 10**9:.4f} TON</p>
                {f'<p><strong>{user_info}</strong></p>' if user_info else ''}
                <p><strong>Telegram ID из комментария:</strong> {existing.telegram_id_from_comment or 'не найден'}</p>
                <p><a href="/admin/deposits">← Назад к депозитам</a></p>
            """)

        service = get_ton_service()
        if not service or not service.api_key:
            return HTMLResponse(content="<h1>Ошибка: TON сервис не настроен (нет API ключа)</h1>", status_code=500)

        import aiohttp
        import ssl
        import re
        from datetime import datetime

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            connector=connector
        ) as session:
            url = f"https://tonapi.io/v2/blockchain/transactions/{tx_hash}"
            headers = {"Authorization": f"Bearer {service.api_key}"}
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    # Парсим транзакцию
                    in_msg = data.get("in_msg")
                    if not in_msg:
                        return HTMLResponse(content=f"""
                            <h1>Транзакция найдена, но нет входящего сообщения</h1>
                            <p>TX Hash: {tx_hash}</p>
                            <p>Это может быть исходящая транзакция или транзакция без сообщения.</p>
                            <pre>{str(data)[:2000]}</pre>
                            <p><a href="/admin/deposits">← Назад к депозитам</a></p>
                        """)
                    
                    # Получаем сумму
                    value = int(in_msg.get("value", 0))
                    source = in_msg.get("source", {}).get("address", "") or in_msg.get("source", "")
                    
                    # Получаем комментарий
                    msg_body = in_msg.get("msg_data", {})
                    telegram_id = None
                    msg_text_str = ""
                    
                    if isinstance(msg_body, dict):
                        msg_text_str = msg_body.get("text", "") or msg_body.get("comment", "")
                    elif isinstance(msg_body, str):
                        msg_text_str = msg_body
                    
                    if not msg_text_str:
                        decoded = in_msg.get("decoded_body", {})
                        if isinstance(decoded, dict):
                            msg_text_str = decoded.get("text", "") or decoded.get("comment", "")
                    
                    if not msg_text_str:
                        body_b64 = in_msg.get("body", "")
                        if body_b64:
                            try:
                                import base64
                                decoded_bytes = base64.b64decode(body_b64)
                                if len(decoded_bytes) > 4:
                                    msg_text_str = decoded_bytes[4:].decode('utf-8', errors='ignore').strip()
                            except:
                                pass
                    
                    # Ищем Telegram ID
                    if msg_text_str:
                        match_id = re.search(r'(?:tg:)?(\d{8,12})', msg_text_str)
                        if match_id:
                            telegram_id = match_id.group(1)
                    
                    # Создаем депозит
                    deposit = Deposit(
                        tx_hash=tx_hash,
                        from_address=source,
                        amount_nano=value,
                        telegram_id_from_comment=telegram_id,
                        status="pending"
                    )
                    db.add(deposit)
                    db.commit()
                    
                    result_html = f"""
                        <h1>✅ Транзакция обработана!</h1>
                        <p><strong>TX Hash:</strong> {tx_hash}</p>
                        <p><strong>Сумма:</strong> {value / 10**9:.4f} TON</p>
                        <p><strong>Отправитель:</strong> {source[:30]}...</p>
                        <p><strong>Комментарий:</strong> {msg_text_str[:100] if msg_text_str else 'нет'}</p>
                        <p><strong>Telegram ID из комментария:</strong> {telegram_id or 'не найден'}</p>
                    """
                    
                    # Зачисляем на баланс если нашли ID
                    if telegram_id:
                        try:
                            user = db.query(User).filter(User.telegram_id == int(telegram_id)).first()
                            
                            if user:
                                balance = db.query(UserBalance).filter(UserBalance.user_id == user.id).first()
                                
                                if not balance:
                                    balance = UserBalance(
                                        user_id=user.id,
                                        ton_active_balance=value,
                                        last_fiat_rate=Decimal("250"),
                                        fiat_currency="RUB"
                                    )
                                    db.add(balance)
                                else:
                                    balance.ton_active_balance += value
                                
                                deposit.user_id = user.id
                                deposit.status = "processed"
                                deposit.processed_at = datetime.utcnow()
                                db.commit()
                                
                                result_html += f"""
                                    <div style="background: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; margin: 15px 0; border-radius: 4px;">
                                        <h2>✅ Средства зачислены!</h2>
                                        <p><strong>Пользователь:</strong> @{user.username or 'user'} (Telegram ID: {user.telegram_id})</p>
                                        <p><strong>Зачислено:</strong> {value / 10**9:.4f} TON</p>
                                        <p><strong>Новый баланс:</strong> {float(balance.ton_active_balance) / 10**9:.4f} TON</p>
                                    </div>
                                """
                            else:
                                result_html += f"""
                                    <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 15px 0; border-radius: 4px;">
                                        <p>⚠️ Пользователь с Telegram ID {telegram_id} не найден в базе данных.</p>
                                        <p>Депозит создан со статусом "pending". Средства будут зачислены автоматически, когда пользователь зарегистрируется.</p>
                                    </div>
                                """
                        except Exception as e:
                            result_html += f"""
                                <div style="background: #ffebee; border-left: 4px solid #f44336; padding: 15px; margin: 15px 0; border-radius: 4px;">
                                    <p>❌ Ошибка при зачислении средств: {str(e)}</p>
                                </div>
                            """
                    else:
                        result_html += """
                            <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 15px 0; border-radius: 4px;">
                                <p>⚠️ Telegram ID не найден в комментарии транзакции.</p>
                                <p>Депозит создан со статусом "pending". Средства не будут зачислены автоматически.</p>
                            </div>
                        """
                    
                    result_html += '<p><a href="/admin/deposits">← Назад к депозитам</a></p>'
                    return HTMLResponse(content=result_html)
                    
                elif resp.status == 404:
                    return HTMLResponse(content=f"""
                        <h1>Транзакция не найдена</h1>
                        <p>TX Hash: {tx_hash}</p>
                        <p>Транзакция не найдена в блокчейне TON. Возможно, хеш неверный или транзакция еще не подтверждена.</p>
                        <p><a href="/admin/deposits">← Назад к депозитам</a></p>
                    """)
                else:
                    text = await resp.text()
                    return HTMLResponse(content=f"""
                        <h1>Ошибка при проверке транзакции</h1>
                        <p>Статус: {resp.status}</p>
                        <p>Ответ: {text[:500]}</p>
                        <p><a href="/admin/deposits">← Назад к депозитам</a></p>
                    """)
    finally:
        db.close()


async def get_ton_wallet_html(request: Request):
    """Страница TON-кошелька: баланс и журнал транзакций"""
    db = SessionLocal()
    ton_balance_ton = None
    balance_error = None
    transactions = []
    users_map = {}
    try:
        # Получаем транзакции (последние 50)
        transactions = (
            db.query(TonTransaction)
            .order_by(TonTransaction.created_at.desc())
            .limit(50)
            .all()
        )

        # Получаем всех пользователей, связанных с транзакциями
        user_ids = [tx.user_id for tx in transactions if tx.user_id is not None]
        if user_ids:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
            users_map = {user.id: user for user in users}

        # Баланс сервисного кошелька
        try:
            ton_service = get_ton_service()
            balance_nano = await ton_service.get_wallet_balance()
            ton_balance_ton = round(float(balance_nano) / 10**9, 4)
        except Exception as exc:  # noqa: BLE001
            import traceback
            balance_error = f"Не удалось получить баланс кошелька: {str(exc)}"
            print(f"TON balance error: {traceback.format_exc()}")
    finally:
        db.close()

    sidebar_html = get_sidebar_html("ton")

    def status_badge(status: str) -> str:
        colors = {
            "pending": "badge-warning",
            "completed": "badge-success",
            "failed": "badge-danger",
        }
        return colors.get(status, "badge-secondary")

    rows_html = ""
    for tx in transactions:
        # Определяем отправителя
        if tx.user_id is None:
            sender = '<span style="color: #667eea; font-weight: 600;">👤 Админ</span>'
        else:
            user = users_map.get(tx.user_id)
            if user:
                sender = f"@{user.username or 'user'} ({user.telegram_id})"
            else:
                sender = f"User #{tx.user_id}"
        
        # Форматируем адрес (сокращаем для удобства)
        addr_display = tx.to_address[:20] + '...' if len(tx.to_address) > 20 else tx.to_address
        
        # TX Hash с ссылкой на explorer
        tx_hash_display = '-'
        if tx.tx_hash and tx.tx_hash != 'unknown':
            tx_hash_display = f'<a href="https://tonapi.io/transaction/{tx.tx_hash}" target="_blank" style="color: #667eea; text-decoration: none;">{tx.tx_hash[:16]}...</a>'
        
        # Заметки
        notes_display = f'<span class="muted" title="{tx.notes}">📝</span>' if tx.notes else ''
        
        rows_html += f"""
        <tr>
            <td>#{tx.id}</td>
            <td>{sender}</td>
            <td><code style="background:#f5f5f5; padding:2px 6px; border-radius:3px; font-size:11px;">{addr_display}</code></td>
            <td><strong>{round(float(tx.amount_nano) / 10**9, 4)} TON</strong></td>
            <td><span class="badge {status_badge(tx.status)}">{tx.status}</span></td>
            <td>{tx_hash_display}</td>
            <td>{notes_display}</td>
            <td class="muted">{tx.created_at.strftime('%Y-%m-%d %H:%M') if tx.created_at else ''}</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TON Кошелек - Админка</title>
    <style>
        {get_base_styles()}
        .header {{ background: linear-gradient(135deg, #1f4037 0%, #99f2c8 100%); }}
    </style>
</head>
<body>
    {sidebar_html}
    <div class="main-content">
    <div class="container">
        <div class="header">
            <h1>🪙 TON Кошелек</h1>
            <p>Баланс сервисного кошелька и журнал автоматических выплат.</p>
        </div>

        <div class="card">
            <h3>Баланс кошелька</h3>
            <p class="muted">Адрес: {os.getenv("TON_WALLET_ADDRESS", "не настроен")}</p>
            {"<p><strong>Баланс:</strong> " + str(ton_balance_ton) + " TON</p>" if ton_balance_ton is not None else ""}
            {f"<div class='alert alert-warning'>{balance_error}</div>" if balance_error else ""}
        </div>

        <div class="card">
            <h3>💸 Вывод с сервисного кошелька</h3>
            <p class="muted">Прямой вывод TON с сервисного кошелька на любой адрес. Средства списываются с баланса кошелька приложения.</p>
            <form id="withdraw-form">
                <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px;">
                    <div>
                        <label><strong>Адрес получателя</strong></label>
                        <input type="text" id="w-address" required placeholder="EQ..." style="width:100%; padding:8px; border:1px solid #ddd; border-radius:6px; font-family: monospace;">
                    </div>
                    <div>
                        <label><strong>Сумма (TON)</strong></label>
                        <input type="number" step="0.000000001" min="0" id="w-amount" required placeholder="0.1" style="width:100%; padding:8px; border:1px solid #ddd; border-radius:6px;">
                    </div>
                    <div>
                        <label><strong>Заметки (опционально)</strong></label>
                        <input type="text" id="w-notes" placeholder="Куда/зачем" style="width:100%; padding:8px; border:1px solid #ddd; border-radius:6px;">
                    </div>
                </div>
                <button type="submit" class="btn" style="margin-top:12px; background: #667eea; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: 600;">🚀 Отправить TON</button>
                <div id="w-result" style="margin-top:12px; padding: 12px; border-radius: 6px; display: none;"></div>
            </form>
        </div>

        <div class="card">
            <h3>Журнал транзакций (последние 50)</h3>
            <p class="muted">Статусы: pending — отправляется, completed — подтверждено, failed — ошибка отправки.</p>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Отправитель</th>
                        <th>Адрес получателя</th>
                        <th>Сумма</th>
                        <th>Статус</th>
                        <th>TX Hash</th>
                        <th>Заметки</th>
                        <th>Создано</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html if rows_html else "<tr><td colspan='8' style='text-align:center; padding:40px; color:#999;'>Нет транзакций</td></tr>"}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h3>ℹ️ Как это работает</h3>
            <ul style="line-height: 1.8;">
                <li><strong>Сервисный кошелек:</strong> Это основной кошелек приложения. На него поступают средства от заказчиков для создания заданий, и с него идут выплаты исполнителям.</li>
                <li><strong>Прямой вывод:</strong> Вы можете вывести средства с сервисного кошелька на любой адрес. Средства списываются напрямую с баланса кошелька.</li>
                <li><strong>Автоматическое обновление:</strong> Статусы транзакций обновляются автоматически каждые 30 секунд (pending → completed/failed).</li>
                <li><strong>Безопасность:</strong> Идемпотентность защищает от двойных списаний. Каждая транзакция имеет уникальный ключ.</li>
                <li><strong>Мониторинг:</strong> Все транзакции сохраняются в журнале. Вы можете отслеживать их статус и переходить к просмотру в TON Explorer по TX Hash.</li>
            </ul>
        </div>
    </div>
    </div>
    <script src="/admin/static/admin_menu.js"></script>
    <script>
      // Обработка формы вывода с сервисного кошелька
      const form = document.getElementById('withdraw-form');
      if (form) {{
        form.addEventListener('submit', async (e) => {{
          e.preventDefault();
          const toAddress = document.getElementById('w-address').value.trim();
          const amountTon = document.getElementById('w-amount').value;
          const notes = document.getElementById('w-notes').value.trim();
          const resultEl = document.getElementById('w-result');
          
          // Валидация адреса
          if (!toAddress.startsWith('EQ') && !toAddress.startsWith('UQ')) {{
            resultEl.style.display = 'block';
            resultEl.style.background = '#fee';
            resultEl.style.color = '#c33';
            resultEl.textContent = '❌ Неверный формат адреса. Должен начинаться с EQ или UQ';
            return;
          }}
          
          resultEl.style.display = 'block';
          resultEl.style.background = '#e3f2fd';
          resultEl.style.color = '#1976d2';
          resultEl.textContent = '⏳ Отправляем транзакцию...';
          
          try {{
            const payload = {{
              to_address: toAddress,
              amount_ton: Number(amountTon),
              notes: notes || null,
              idempotency_key: 'admin-' + Date.now()
            }};
            
            const resp = await fetch('/api/ton/admin/withdraw', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify(payload)
            }});
            
            const data = await resp.json();
            
            if (!resp.ok) {{
              throw new Error(data.detail || 'Ошибка вывода');
            }}
            
            // Успех
            resultEl.style.background = '#e8f5e9';
            resultEl.style.color = '#2e7d32';
            resultEl.innerHTML = '✅ <strong>Транзакция создана!</strong><br>' +
              'Статус: ' + data.status + '<br>' +
              (data.tx_hash ? 'TX Hash: <code style="background:#f5f5f5; padding:2px 6px; border-radius:3px;">' + data.tx_hash + '</code>' : 'TX Hash: ожидается...');
            
            // Очищаем форму
            form.reset();
            
            // Обновляем страницу через 2 секунды для обновления баланса
            setTimeout(() => {{
              window.location.reload();
            }}, 2000);
            
          }} catch (err) {{
            resultEl.style.background = '#fee';
            resultEl.style.color = '#c33';
            resultEl.textContent = '❌ Ошибка: ' + err.message;
          }}
        }});
      }}
    </script>
</body>
</html>"""

    return HTMLResponse(content=html)

async def get_profit_html(request: Request):
    """Страница прибыли"""
    from app.models import ProfitWithdrawal
    from decimal import Decimal
    
    db = SessionLocal()
    success_msg = None
    error_msg = None
    
    try:
        # Обработка формы вывода прибыли
        if request.method == "POST":
            form = await request.form()
            action = form.get("action")
            
            if action == "withdraw":
                amount = form.get("amount")
                wallet = form.get("wallet_address")
                
                if not amount or not wallet:
                    error_msg = "Заполните все поля"
                else:
                    try:
                        amount_ton = Decimal(amount)
                        if amount_ton <= 0:
                            error_msg = "Сумма должна быть больше 0"
                        else:
                            # Вычисляем доступную прибыль из реального баланса кошелька
                            try:
                                service = get_ton_service()
                                wallet_balance_nano = await service.get_wallet_balance()
                                available_profit = round(float(wallet_balance_nano) / 10**9, 4)
                            except Exception as e:
                                available_profit = 0.0
                            
                            if amount_ton > available_profit:
                                error_msg = f"Недостаточно средств. Доступно: {available_profit:.2f} TON"
                            else:
                                # Создаем запись о выводе
                                withdrawal = ProfitWithdrawal(
                                    amount_ton=amount_ton,
                                    wallet_address=wallet,
                                    status="pending"
                                )
                                db.add(withdrawal)
                                db.commit()
                                success_msg = f"Запрос на вывод {amount_ton:.2f} TON на адрес {wallet} создан"
                    except ValueError:
                        error_msg = "Неверный формат суммы"
            
            elif action == "delete_withdrawal":
                withdrawal_id = form.get("withdrawal_id")
                if withdrawal_id:
                    try:
                        withdrawal_id = int(withdrawal_id)
                        from app.models import ProfitWithdrawal
                        withdrawal = db.query(ProfitWithdrawal).filter(ProfitWithdrawal.id == withdrawal_id).first()
                        if withdrawal:
                            db.delete(withdrawal)
                            db.commit()
                            success_msg = f"Запись о выводе #{withdrawal_id} удалена"
                        else:
                            error_msg = "Запись не найдена"
                    except (ValueError, Exception) as e:
                        error_msg = f"Ошибка при удалении: {str(e)}"
        
        # Получаем реальный баланс сервисного кошелька
        try:
            service = get_ton_service()
            wallet_balance_nano = await service.get_wallet_balance()
            wallet_balance_ton = round(float(wallet_balance_nano) / 10**9, 4)
        except Exception as e:
            print(f"Error getting wallet balance: {e}")
            wallet_balance_ton = 0.0
        
        # Оборот = сумма всех реальных депозитов
        from app.models import Deposit
        total_deposits_nano = db.query(func.sum(Deposit.amount_nano)).filter(
            Deposit.status == "processed"
        ).scalar() or 0
        total_turnover_ton = round(float(total_deposits_nano) / 10**9, 4) if total_deposits_nano else 0.0
        
        # Прибыль = реальный баланс кошелька (это и есть реальные средства приложения)
        app_profit_ton = wallet_balance_ton
        
        # Вычисляем уже выведенную прибыль (из админских выводов)
        withdrawn_nano = db.query(func.sum(TonTransaction.amount_nano)).filter(
            TonTransaction.status == "completed",
            TonTransaction.user_id.is_(None)  # Админские выводы
        ).scalar() or 0
        withdrawn_ton = round(float(withdrawn_nano) / 10**9, 4) if withdrawn_nano else 0.0
        
        # Доступная прибыль = текущий баланс кошелька (уже учитывает все транзакции)
        available_profit = wallet_balance_ton
        
        # История выводов
        from app.models import ProfitWithdrawal
        withdrawals = db.query(ProfitWithdrawal).order_by(ProfitWithdrawal.created_at.desc()).limit(20).all()
        
        # Оборот по типам заданий - считаем из реальных депозитов (не из заданий)
        # Пока оставляем 0, так как у нас нет связи депозитов с типами заданий
        subscription_turnover = 0
        comment_turnover = 0
        view_turnover = 0
        
        today = datetime.now().date()
        week_ago = datetime.now() - timedelta(days=7)
        month_ago = datetime.now() - timedelta(days=30)
        
        # Оборот за периоды из реальных депозитов
        turnover_today = db.query(func.sum(Deposit.amount_nano)).filter(
            func.date(Deposit.processed_at) == today,
            Deposit.status == "processed"
        ).scalar() or 0
        turnover_today = round(float(turnover_today) / 10**9, 4) if turnover_today else 0.0
        
        turnover_week = db.query(func.sum(Deposit.amount_nano)).filter(
            Deposit.processed_at >= week_ago,
            Deposit.status == "processed"
        ).scalar() or 0
        turnover_week = round(float(turnover_week) / 10**9, 4) if turnover_week else 0.0
        
        turnover_month = db.query(func.sum(Deposit.amount_nano)).filter(
            Deposit.processed_at >= month_ago,
            Deposit.status == "processed"
        ).scalar() or 0
        turnover_month = round(float(turnover_month) / 10**9, 4) if turnover_month else 0.0
    finally:
        db.close()

    sidebar_html = get_sidebar_html("profit")
    
    # Генерируем HTML для истории выводов отдельно, чтобы избежать проблем с вложенными f-строками
    withdrawals_html = ""
    if withdrawals:
        for w in withdrawals:
            amount_ton = round(float(w.amount_ton or 0) / 10**9, 2)
            created_at = w.created_at.strftime('%Y-%m-%d %H:%M') if w.created_at else '-'
            wallet_addr = w.wallet_address[:20] if w.wallet_address else '-'
            status_badge = 'badge-success' if w.status == 'completed' else 'badge-warning' if w.status == 'pending' else 'badge-danger'
            # Кнопка удаления только для pending статуса
            delete_button = ""
            if w.status == 'pending':
                delete_button = f"""
                    <form method="POST" style="display: inline;" onsubmit="return confirm('Вы уверены, что хотите удалить эту запись?');">
                        <input type="hidden" name="action" value="delete_withdrawal">
                        <input type="hidden" name="withdrawal_id" value="{w.id}">
                        <button type="submit" style="padding: 4px 12px; background: #f44336; color: white; border: none; border-radius: 4px; font-size: 12px; cursor: pointer;" title="Удалить запись">🗑️ Удалить</button>
                    </form>
                """
            withdrawals_html += f"""
                <tr>
                    <td>{created_at}</td>
                    <td>{amount_ton:.2f}</td>
                    <td style="font-family: monospace; font-size: 12px;">{wallet_addr}...</td>
                    <td><span class="badge {status_badge}">{w.status.upper()}</span></td>
                    <td>{delete_button}</td>
                </tr>
                """
    else:
        withdrawals_html = '<tr><td colspan="5" style="text-align: center; padding: 40px; color: #999;">Нет истории выводов</td></tr>'
    
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Прибыль - Админка</title>
    <style>
        {get_base_styles()}
        .header {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }}
        .info-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        .info-box strong {{ color: #1976d2; display: block; margin-bottom: 10px; font-size: 18px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }}
        .stat-card {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-card.gradient {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
        .stat-card.gradient-green {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; }}
        .stat-card h3 {{ font-size: 14px; text-transform: uppercase; margin-bottom: 10px; opacity: 0.9; }}
        .stat-card .value {{ font-size: 36px; font-weight: bold; }}
        h2 {{ margin: 30px 0 15px 0; color: #333; }}
    </style>
</head>
<body>
    {sidebar_html}
    <div class="main-content">
    <div class="container">
        <div class="header">
            <h1>💰 Финансовая статистика</h1>
        </div>
        
        <div class="info-box">
            <strong>💡 Как это работает:</strong>
            Приложение берет комиссию 5% с каждого созданного задания. Это означает, что если заказчик создал задание на 100 TON, приложение получит 5 TON прибыли.
        </div>
        
        <div class="stats-grid">
            <div class="stat-card gradient">
                <h3>Общий оборот</h3>
                <div class="value">{total_turnover_ton:.2f} TON</div>
            </div>
            <div class="stat-card gradient-green">
                <h3>Прибыль приложения (5%)</h3>
                <div class="value">{app_profit_ton:.2f} TON</div>
            </div>
            <div class="stat-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white;">
                <h3>Доступно для вывода</h3>
                <div class="value">{available_profit:.2f} TON</div>
                <div style="font-size: 14px; margin-top: 5px; opacity: 0.9;">Выведено: {withdrawn_ton:.2f} TON</div>
            </div>
        </div>
        
        <!-- Форма вывода прибыли -->
        <div style="background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 30px 0;">
            <h2 style="margin-bottom: 20px; color: #333;">💸 Вывод прибыли</h2>
            {"<div style='background: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; margin: 15px 0; border-radius: 4px; color: #2e7d32;'><strong>✅ Успешно!</strong> " + success_msg + "</div>" if success_msg else ""}
            {"<div style='background: #ffebee; border-left: 4px solid #f44336; padding: 15px; margin: 15px 0; border-radius: 4px; color: #c62828;'><strong>❌ Ошибка:</strong> " + error_msg + "</div>" if error_msg else ""}
            <form method="POST" style="display: grid; gap: 20px;">
                <input type="hidden" name="action" value="withdraw">
                <div>
                    <label style="display: block; margin-bottom: 8px; font-weight: bold; color: #333;">Сумма (TON):</label>
                    <input type="number" name="amount" step="0.01" min="0.01" max="{available_profit:.2f}" placeholder="Макс: {available_profit:.2f}" required style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px;">
                </div>
                <div>
                    <label style="display: block; margin-bottom: 8px; font-weight: bold; color: #333;">Адрес кошелька TON:</label>
                    <input type="text" name="wallet_address" placeholder="EQD..." required style="width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px;">
                </div>
                <button type="submit" style="padding: 12px 24px; background: #11998e; color: white; border: none; border-radius: 5px; font-size: 16px; font-weight: bold; cursor: pointer; transition: opacity 0.3s;" onmouseover="this.style.opacity='0.9'" onmouseout="this.style.opacity='1'">Вывести прибыль</button>
            </form>
        </div>
        
        <!-- История выводов -->
        <h2>📋 История выводов</h2>
        <table>
            <thead>
                <tr>
                    <th>Дата</th>
                    <th>Сумма (TON)</th>
                    <th>Адрес кошелька</th>
                    <th>Статус</th>
                    <th>Действия</th>
                </tr>
            </thead>
            <tbody>
                {withdrawals_html}
            </tbody>
        </table>
        
        <h2>📊 Оборот по типам заданий</h2>
        <table>
            <thead>
                <tr>
                    <th>Тип задания</th>
                    <th>Оборот (TON)</th>
                    <th>Прибыль (5%)</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Подписка</td>
                    <td>{f"{round(float(subscription_turnover) / 10**9, 2):.2f}"}</td>
                    <td>{f"{round(float(subscription_turnover) / 10**9 * 0.05, 2):.2f}"}</td>
                </tr>
                <tr>
                    <td>Комментарий</td>
                    <td>{f"{round(float(comment_turnover) / 10**9, 2):.2f}"}</td>
                    <td>{f"{round(float(comment_turnover) / 10**9 * 0.05, 2):.2f}"}</td>
                </tr>
                <tr>
                    <td>Просмотр</td>
                    <td>{f"{round(float(view_turnover) / 10**9, 2):.2f}"}</td>
                    <td>{f"{round(float(view_turnover) / 10**9 * 0.05, 2):.2f}"}</td>
                </tr>
            </tbody>
        </table>
        
        <h2>📈 Оборот по периодам</h2>
        <table>
            <thead>
                <tr>
                    <th>Период</th>
                    <th>Оборот (TON)</th>
                    <th>Прибыль (5%)</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Сегодня</td>
                    <td>{f"{round(float(turnover_today) / 10**9, 2):.2f}"}</td>
                    <td>{f"{round(float(turnover_today) / 10**9 * 0.05, 2):.2f}"}</td>
                </tr>
                <tr>
                    <td>За неделю</td>
                    <td>{f"{round(float(turnover_week) / 10**9, 2):.2f}"}</td>
                    <td>{f"{round(float(turnover_week) / 10**9 * 0.05, 2):.2f}"}</td>
                </tr>
                <tr>
                    <td>За месяц</td>
                    <td>{f"{round(float(turnover_month) / 10**9, 2):.2f}"}</td>
                    <td>{f"{round(float(turnover_month) / 10**9 * 0.05, 2):.2f}"}</td>
                </tr>
            </tbody>
        </table>
    </div>
    </div>
    </div>
    <script src="/admin/static/admin_menu.js"></script>
</body>
</html>"""
    
    return HTMLResponse(content=html)

async def get_complaints_html(request: Request):
    """Страница жалоб"""
    db = SessionLocal()
    try:
        all_reports = db.query(TaskReport).order_by(TaskReport.created_at.desc()).all()
        pending_reports = [r for r in all_reports if r.status == TaskReportStatus.PENDING]
        
        reports_data = []
        for report in all_reports:
            task = db.query(Task).filter(Task.id == report.task_id).first()
            reporter = db.query(User).filter(User.id == report.reporter_id).first()
            moderator = db.query(User).filter(User.id == report.moderator_id).first() if report.moderator_id else None
            
            reports_data.append({
                "id": report.id,
                "task_id": report.task_id,
                "task_title": task.title if task else "Задание удалено",
                "reporter_username": reporter.username if reporter else "Неизвестно",
                "reporter_telegram_id": reporter.telegram_id if reporter else None,
                "reason": report.reason or "Не указана",
                "status": report.status.value if report.status else "pending",
                "moderator_username": moderator.username if moderator else None,
                "created_at": report.created_at.strftime("%Y-%m-%d %H:%M") if report.created_at else None,
            })
    finally:
        db.close()

    sidebar_html = get_sidebar_html("complaints")
    
    rows_html = ""
    if reports_data:
        for r in reports_data:
            status_colors = {"pending": "#ff9800", "reviewing": "#2196f3", "resolved": "#4caf50", "rejected": "#f44336"}
            status_color = status_colors.get(r["status"], "#666")
            
            rows_html += f"""
            <tr>
                <td>{r['id']}</td>
                <td><a href="/admin/task/list" style="color: #667eea;">#{r['task_id']}</a> - {r['task_title'][:50]}</td>
                <td>@{r['reporter_username']} ({r['reporter_telegram_id']})</td>
                <td>{r['reason'][:100]}</td>
                <td><span class="badge {'badge-warning' if r['status'] == 'pending' else 'badge-info' if r['status'] == 'reviewing' else 'badge-success' if r['status'] == 'resolved' else 'badge-danger'}">{r['status'].upper()}</span></td>
                <td>{r['moderator_username'] or '-'}</td>
                <td>{r['created_at']}</td>
            </tr>
            """
    else:
        rows_html = '<tr><td colspan="7" style="text-align: center; padding: 40px; color: #999;">Нет жалоб в базе данных</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Жалобы - Админка</title>
    <style>
        {get_base_styles()}
        .header {{ background: linear-gradient(135deg, #f44336 0%, #e91e63 100%); }}
        .info-box {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        .info-box strong {{ color: #856404; display: block; margin-bottom: 10px; font-size: 18px; }}
        a {{ color: #667eea; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    {sidebar_html}
    <div class="main-content">
    <div class="container">
        <div class="header">
            <h1>🚩 Жалобы пользователей</h1>
        </div>
        
        <div class="info-box">
            <strong>💡 Как работать с жалобами:</strong>
            Пользователи могут пожаловаться на задание, если оно нарушает правила. Просмотрите жалобу, проверьте задание и примите решение: решить (заблокировать задание) или отклонить (жалоба необоснованна).
        </div>
        
        <p style="margin: 20px 0;"><strong>Ожидают рассмотрения:</strong> <span class="badge badge-warning">{len(pending_reports)}</span></p>
        
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Задание</th>
                    <th>Жалобщик</th>
                    <th>Причина</th>
                    <th>Статус</th>
                    <th>Модератор</th>
                    <th>Дата</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    </div>
    </div>
    <script src="/admin/static/admin_menu.js"></script>
</body>
</html>"""
    
    return HTMLResponse(content=html)

async def get_ban_user_html(request: Request):
    """Страница блокировки пользователя"""
    db = SessionLocal()
    success_msg = None
    error_msg = None
    
    try:
        if request.method == "POST":
            form = await request.form()
            user_id = form.get("user_id")
            ban_days = form.get("ban_days")
            ban_reason = form.get("ban_reason", "")
            action = form.get("action")
            
            if not user_id:
                error_msg = "Не указан ID пользователя"
            else:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if not user:
                    error_msg = "Пользователь не найден"
                else:
                    if action == "ban":
                        user.is_banned = True
                        user.ban_reason = ban_reason
                        
                        if ban_days and int(ban_days) > 0:
                            user.ban_until = datetime.now() + timedelta(days=int(ban_days))
                        else:
                            user.ban_until = None
                        
                        db.commit()
                        success_msg = f"Пользователь {user.username or user.telegram_id} заблокирован"
                        if ban_days:
                            success_msg += f" на {ban_days} дней"
                        else:
                            success_msg += " навсегда"
                    else:
                        user.is_banned = False
                        user.ban_until = None
                        user.ban_reason = None
                        db.commit()
                        success_msg = f"Блокировка с пользователя {user.username or user.telegram_id} снята"
        
        users = db.query(User).order_by(User.created_at.desc()).limit(100).all()
        users_list = [{"id": u.id, "username": u.username or f"ID: {u.telegram_id}", "telegram_id": u.telegram_id, "is_banned": u.is_banned, "ban_until": u.ban_until.strftime("%Y-%m-%d %H:%M") if u.ban_until else None} for u in users]
    finally:
        db.close()

    sidebar_html = get_sidebar_html("ban-user")
    
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Блокировка пользователя - Админка</title>
    <style>
        {get_base_styles()}
        .header {{ background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%); }}
        .card {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .info-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        .info-box strong {{ color: #1976d2; display: block; margin-bottom: 10px; font-size: 18px; }}
        .info-box ul {{ margin: 10px 0 0 20px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; font-weight: bold; color: #333; }}
        select, input[type="number"], textarea {{ width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; }}
        textarea {{ min-height: 100px; resize: vertical; }}
        .btn {{ padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; font-weight: bold; margin-right: 10px; }}
        .btn-ban {{ background: #f44336; color: white; }}
        .btn-unban {{ background: #4caf50; color: white; }}
        .btn:hover {{ opacity: 0.9; }}
        .success {{ background: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; margin: 15px 0; border-radius: 4px; color: #2e7d32; }}
        .error {{ background: #ffebee; border-left: 4px solid #f44336; padding: 15px; margin: 15px 0; border-radius: 4px; color: #c62828; }}
    </style>
</head>
<body>
    {sidebar_html}
    <div class="main-content">
    <div class="container">
        <div class="header">
            <h1>🚫 Блокировка пользователя</h1>
        </div>
        
        <div class="card">
            <div class="info-box">
                <strong>💡 Как использовать:</strong>
                <ul>
                    <li>Выберите пользователя из списка</li>
                    <li>Укажите количество дней блокировки (или оставьте 0 для постоянной блокировки)</li>
                    <li>Напишите причину блокировки - она будет показана пользователю в его профиле</li>
                    <li>Нажмите "Заблокировать" для применения или "Снять блокировку" для разблокировки</li>
                </ul>
            </div>
            
            {"<div class='success'><strong>✅ Успешно!</strong> " + success_msg + "</div>" if success_msg else ""}
            {"<div class='error'><strong>❌ Ошибка:</strong> " + error_msg + "</div>" if error_msg else ""}
            
            <form method="POST">
                <div class="form-group">
                    <label for="user_id">Выберите пользователя:</label>
                    <select name="user_id" id="user_id" required>
                        <option value="">-- Выберите пользователя --</option>
                        {"".join([f"<option value='{u['id']}' {'selected' if u['is_banned'] else ''}>{u['username']} {'(ЗАБЛОКИРОВАН' + (' до ' + u['ban_until'] if u['ban_until'] else ' навсегда') + ')' if u['is_banned'] else ''}</option>" for u in users_list])}
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="ban_days">Количество дней блокировки:</label>
                    <input type="number" name="ban_days" id="ban_days" min="0" value="0" required>
                    <small style="color: #666;">Укажите 0 для постоянной блокировки</small>
                </div>
                
                <div class="form-group">
                    <label for="ban_reason">Причина блокировки (будет показана пользователю):</label>
                    <textarea name="ban_reason" id="ban_reason" placeholder="Например: Нарушение правил сообщества, спам, мошенничество и т.д." required></textarea>
                </div>
                
                <div>
                    <button type="submit" name="action" value="ban" class="btn btn-ban">🚫 Заблокировать</button>
                    <button type="submit" name="action" value="unban" class="btn btn-unban">✅ Снять блокировку</button>
                </div>
            </form>
        </div>
    </div>
    </div>
    </div>
    <script src="/admin/static/admin_menu.js"></script>
</body>
</html>"""
    
    return HTMLResponse(content=html)

async def get_users_html(request: Request):
    """Страница пользователей"""
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).limit(100).all()
        
        users_data = []
        for user in users:
            balance = db.query(UserBalance).filter(UserBalance.user_id == user.id).first()
            users_data.append({
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username or "-",
                "first_name": user.first_name or "-",
                "age": user.age or "-",
                "gender": user.gender or "-",
                "country": user.country or "-",
                "role": user.role.value if user.role else "user",
                "is_banned": user.is_banned,
                "ban_until": user.ban_until.strftime("%Y-%m-%d %H:%M") if user.ban_until else None,
                "balance_ton": round(float(balance.ton_active_balance) / 10**9, 2) if balance else 0,
                "created_at": user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else "-",
            })
    finally:
        db.close()

    sidebar_html = get_sidebar_html("user")
    
    rows_html = ""
    if users_data:
        for u in users_data:
            role_badge = f'<span class="badge {"badge-danger" if u["role"] == "owner" else "badge-info" if u["role"] == "moderator" else "badge-secondary"}">{u["role"].upper()}</span>'
            ban_badge = f'<span class="badge badge-danger">ЗАБЛОКИРОВАН</span>' if u["is_banned"] else ""
            
            rows_html += f"""
            <tr>
                <td>{u['id']}</td>
                <td>@{u['username']}</td>
                <td>{u['first_name']}</td>
                <td>{u['telegram_id']}</td>
                <td>{u['age']}</td>
                <td>{u['gender']}</td>
                <td>{u['country']}</td>
                <td>{u['balance_ton']:.2f} TON</td>
                <td>{role_badge}</td>
                <td>{ban_badge}</td>
                <td>{u['created_at']}</td>
            </tr>
            """
    else:
        rows_html = '<tr><td colspan="11" style="text-align: center; padding: 40px; color: #999;">Нет пользователей</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Пользователи - Админка</title>
    <style>
        {get_base_styles()}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
        .info-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        .info-box strong {{ color: #1976d2; display: block; margin-bottom: 10px; font-size: 18px; }}
    </style>
</head>
<body>
    {sidebar_html}
    <div class="main-content">
    <div class="container">
        <div class="header">
            <h1>👥 Пользователи</h1>
            <p>Управление пользователями системы. Просмотр профилей, изменение ролей, блокировка.</p>
        </div>
        
        <div class="info-box">
            <strong>💡 Управление пользователями:</strong>
            Здесь отображается список всех пользователей. Вы можете просматривать их профили, изменять роли (пользователь/модератор/владелец) и блокировать пользователей. Для блокировки используйте раздел "Блокировка пользователя".
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Username</th>
                    <th>Имя</th>
                    <th>Telegram ID</th>
                    <th>Возраст</th>
                    <th>Пол</th>
                    <th>Страна</th>
                    <th>Баланс</th>
                    <th>Роль</th>
                    <th>Статус</th>
                    <th>Дата регистрации</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    </div>
    </div>
    <script src="/admin/static/admin_menu.js"></script>
</body>
</html>"""
    
    return HTMLResponse(content=html)

async def get_tasks_html(request: Request):
    """Страница заданий"""
    db = SessionLocal()
    try:
        tasks = db.query(Task).order_by(Task.created_at.desc()).limit(100).all()
        
        tasks_data = []
        for task in tasks:
            creator = db.query(User).filter(User.id == task.creator_id).first()
            tasks_data.append({
                "id": task.id,
                "title": task.title,
                "task_type": task.task_type.value if task.task_type else "unknown",
                "price_per_slot_ton": round(float(task.price_per_slot_ton) / 10**9, 2),
                "total_slots": task.total_slots,
                "completed_slots": task.completed_slots,
                "remaining_slots": task.total_slots - task.completed_slots,
                "status": task.status.value if task.status else "unknown",
                "creator_username": creator.username if creator else "Неизвестно",
                "created_at": task.created_at.strftime("%Y-%m-%d %H:%M") if task.created_at else "-",
            })
    finally:
        db.close()

    sidebar_html = get_sidebar_html("task")
    
    rows_html = ""
    if tasks_data:
        for t in tasks_data:
            type_badge = f'<span class="badge {"badge-success" if t["task_type"] == "subscription" else "badge-info" if t["task_type"] == "comment" else "badge-warning"}">{t["task_type"].upper()}</span>'
            status_badge = f'<span class="badge {"badge-success" if t["status"] == "active" else "badge-warning" if t["status"] == "paused" else "badge-secondary"}">{t["status"].upper()}</span>'
            
            rows_html += f"""
            <tr>
                <td>{t['id']}</td>
                <td>{t['title'][:50]}{'...' if len(t['title']) > 50 else ''}</td>
                <td>{type_badge}</td>
                <td>{t['price_per_slot_ton']:.2f} TON</td>
                <td>{t['completed_slots']} / {t['total_slots']}</td>
                <td>{t['remaining_slots']}</td>
                <td>{status_badge}</td>
                <td>@{t['creator_username']}</td>
                <td>{t['created_at']}</td>
            </tr>
            """
    else:
        rows_html = '<tr><td colspan="9" style="text-align: center; padding: 40px; color: #999;">Нет заданий</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Задания - Админка</title>
    <style>
        {get_base_styles()}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
        .info-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        .info-box strong {{ color: #1976d2; display: block; margin-bottom: 10px; font-size: 18px; }}
    </style>
</head>
<body>
    {sidebar_html}
    <div class="main-content">
    <div class="container">
        <div class="header">
            <h1>📋 Задания</h1>
            <p>Модерация заданий. Просмотр, редактирование, изменение статуса заданий.</p>
        </div>
        
        <div class="info-box">
            <strong>💡 Модерация заданий:</strong>
            Здесь отображается список всех заданий в системе. Вы можете просматривать детали заданий, изменять их статус (активно/приостановлено/завершено) и удалять задания, нарушающие правила.
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Название</th>
                    <th>Тип</th>
                    <th>Цена за слот</th>
                    <th>Выполнено / Всего</th>
                    <th>Осталось</th>
                    <th>Статус</th>
                    <th>Создатель</th>
                    <th>Дата создания</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    </div>
    </div>
    <script src="/admin/static/admin_menu.js"></script>
</body>
</html>"""
    
    return HTMLResponse(content=html)

async def get_user_balance_html(request: Request):
    """Страница балансов с возможностью пополнения"""
    db = SessionLocal()
    success_msg = None
    error_msg = None
    
    try:
        # Обработка пополнения баланса
        if request.method == "POST":
            form = await request.form()
            action = form.get("action")
            
            if action == "deposit":
                telegram_id = form.get("telegram_id")
                amount_ton = form.get("amount_ton")
                
                if not telegram_id or not amount_ton:
                    error_msg = "Заполните все поля"
                else:
                    try:
                        telegram_id_int = int(telegram_id)
                        amount_decimal = Decimal(amount_ton)
                        amount_nano = int(amount_decimal * Decimal(10**9))
                        
                        if amount_nano <= 0:
                            error_msg = "Сумма должна быть больше 0"
                        else:
                            user = db.query(User).filter(User.telegram_id == telegram_id_int).first()
                            if not user:
                                error_msg = f"Пользователь с Telegram ID {telegram_id} не найден"
                            else:
                                balance = db.query(UserBalance).filter(UserBalance.user_id == user.id).first()
                                if not balance:
                                    balance = UserBalance(
                                        user_id=user.id,
                                        ton_active_balance=amount_nano,
                                        last_fiat_rate=Decimal("250"),
                                        fiat_currency="RUB"
                                    )
                                    db.add(balance)
                                else:
                                    balance.ton_active_balance += amount_nano
                                
                                db.commit()
                                success_msg = f"Баланс пользователя @{user.username or 'user'} ({telegram_id}) пополнен на {amount_ton} TON"
                    except ValueError:
                        error_msg = "Неверный формат данных"
                    except Exception as e:
                        error_msg = f"Ошибка: {str(e)}"
        
        balances = db.query(UserBalance).join(User).order_by(UserBalance.created_at.desc()).limit(100).all()
        
        balances_data = []
        for balance in balances:
            user = db.query(User).filter(User.id == balance.user_id).first()
            balances_data.append({
                "id": balance.id,
                "user_id": balance.user_id,
                "username": user.username if user else "Неизвестно",
                "telegram_id": user.telegram_id if user else "-",
                "ton_active_balance": round(float(balance.ton_active_balance or 0) / 10**9, 4),
                "ton_escrow_balance": round(float(balance.ton_escrow_balance or 0) / 10**9, 4),
                "ton_referral_earnings": round(float(balance.ton_referral_earnings or 0) / 10**9, 4),
                "total_balance": round((float(balance.ton_active_balance or 0) + float(balance.ton_escrow_balance or 0) + float(balance.ton_referral_earnings or 0)) / 10**9, 4),
                "subscriptions_used": balance.subscriptions_used_24h,
                "subscription_limit": balance.subscription_limit_24h,
            })
    finally:
        db.close()

    sidebar_html = get_sidebar_html("user-balance")
    
    rows_html = ""
    if balances_data:
        for b in balances_data:
            rows_html += f"""
            <tr>
                <td>{b['id']}</td>
                <td>@{b['username']}</td>
                <td>{b['telegram_id']}</td>
                <td>{b['ton_active_balance']:.4f} TON</td>
                <td>{b['ton_escrow_balance']:.4f} TON</td>
                <td>{b['ton_referral_earnings']:.4f} TON</td>
                <td><strong>{b['total_balance']:.4f} TON</strong></td>
                <td>{b['subscriptions_used']} / {b['subscription_limit']}</td>
            </tr>
            """
    else:
        rows_html = '<tr><td colspan="8" style="text-align: center; padding: 40px; color: #999;">Нет балансов</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Балансы - Админка</title>
    <style>
        {get_base_styles()}
        .header {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }}
        .info-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        .info-box strong {{ color: #1976d2; display: block; margin-bottom: 10px; font-size: 18px; }}
    </style>
</head>
<body>
    {sidebar_html}
    <div class="main-content">
    <div class="container">
        <div class="header">
            <h1>💳 Балансы пользователей</h1>
            <p>Просмотр и управление балансами всех пользователей системы.</p>
        </div>
        
        <div class="info-box">
            <strong>💡 Управление балансами:</strong>
            Здесь отображаются балансы всех пользователей. Вы можете просматривать активный баланс, баланс в эскроу, заработок с рефералов и общий баланс каждого пользователя.
        </div>
        
        {"<div class='alert alert-success' style='background:#e8f5e9; border-left:4px solid #4caf50; padding:15px; margin:15px 0; border-radius:8px; color:#2e7d32;'>✅ " + success_msg + "</div>" if success_msg else ""}
        {"<div class='alert alert-danger' style='background:#fee; border-left:4px solid #f44336; padding:15px; margin:15px 0; border-radius:8px; color:#c33;'>❌ " + error_msg + "</div>" if error_msg else ""}
        
        <div class="card" style="background:white; padding:25px; border-radius:10px; box-shadow:0 2px 4px rgba(0,0,0,0.1); margin:20px 0;">
            <h3>💰 Пополнить баланс пользователя (ручное)</h3>
            <p class="muted">Обычно пополнение происходит автоматически при переводе TON на сервисный кошелек с комментарием (Telegram ID). Используйте эту форму только для ручного пополнения без транзакции.</p>
            <form method="POST" style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:12px; margin-top:15px;">
                <input type="hidden" name="action" value="deposit">
                <div>
                    <label><strong>Telegram ID</strong></label>
                    <input type="number" name="telegram_id" required placeholder="123456789" style="width:100%; padding:8px; border:1px solid #ddd; border-radius:6px;">
                </div>
                <div>
                    <label><strong>Сумма (TON)</strong></label>
                    <input type="number" step="0.000000001" min="0" name="amount_ton" required placeholder="10.5" style="width:100%; padding:8px; border:1px solid #ddd; border-radius:6px;">
                </div>
                <div style="display:flex; align-items:flex-end;">
                    <button type="submit" class="btn" style="background:#667eea; color:white; border:none; padding:12px 24px; border-radius:6px; cursor:pointer; font-weight:600; width:100%;">➕ Пополнить</button>
                </div>
            </form>
            <p class="muted" style="margin-top:15px; font-size:12px;">
                <strong>Автоматическое пополнение:</strong> Сервисный кошелек: <code style="background:#f5f5f5; padding:2px 6px; border-radius:3px;">{os.getenv("TON_WALLET_ADDRESS", "не настроен")}</code><br>
                Пользователи переводят TON на этот адрес с комментарием (Telegram ID), и баланс зачисляется автоматически в течение 1-2 минут.
            </p>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Username</th>
                    <th>Telegram ID</th>
                    <th>Активный баланс</th>
                    <th>В эскроу</th>
                    <th>Реферальный доход</th>
                    <th>Общий баланс</th>
                    <th>Подписки (24ч)</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    </div>
    </div>
    <script src="/admin/static/admin_menu.js"></script>
</body>
</html>"""
    
    return HTMLResponse(content=html)

async def get_user_task_html(request: Request):
    """Страница выполнений заданий"""
    db = SessionLocal()
    try:
        user_tasks = db.query(UserTask).order_by(UserTask.created_at.desc()).limit(100).all()
        
        user_tasks_data = []
        for user_task in user_tasks:
            user = db.query(User).filter(User.id == user_task.user_id).first()
            task = db.query(Task).filter(Task.id == user_task.task_id).first()
            
            user_tasks_data.append({
                "id": user_task.id,
                "user_username": user.username if user else "Неизвестно",
                "user_telegram_id": user.telegram_id if user else "-",
                "task_id": user_task.task_id,
                "task_title": task.title if task else "Задание удалено",
                "task_type": task.task_type.value if task else "unknown",
                "reward_ton": round(float(user_task.reward_ton) / 10**9, 2),
                "status": user_task.status.value if user_task.status else "unknown",
                "created_at": user_task.created_at.strftime("%Y-%m-%d %H:%M") if user_task.created_at else "-",
                "validated_at": user_task.validated_at.strftime("%Y-%m-%d %H:%M") if user_task.validated_at else "-",
            })
    finally:
        db.close()

    sidebar_html = get_sidebar_html("user-task")
    
    rows_html = ""
    if user_tasks_data:
        for ut in user_tasks_data:
            type_badge = f'<span class="badge {"badge-success" if ut["task_type"] == "subscription" else "badge-info" if ut["task_type"] == "comment" else "badge-warning"}">{ut["task_type"].upper()}</span>'
            status_badge = f'<span class="badge {"badge-success" if ut["status"] == "completed" else "badge-warning" if ut["status"] == "in_progress" else "badge-danger" if ut["status"] == "failed" else "badge-secondary"}">{ut["status"].upper()}</span>'
            
            rows_html += f"""
            <tr>
                <td>{ut['id']}</td>
                <td>@{ut['user_username']}</td>
                <td>{ut['user_telegram_id']}</td>
                <td><a href="/admin/task/list" style="color: #667eea;">#{ut['task_id']}</a> - {ut['task_title'][:40]}{'...' if len(ut['task_title']) > 40 else ''}</td>
                <td>{type_badge}</td>
                <td>{ut['reward_ton']:.2f} TON</td>
                <td>{status_badge}</td>
                <td>{ut['created_at']}</td>
                <td>{ut['validated_at']}</td>
            </tr>
            """
    else:
        rows_html = '<tr><td colspan="9" style="text-align: center; padding: 40px; color: #999;">Нет выполнений</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Выполнения - Админка</title>
    <style>
        {get_base_styles()}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
        .info-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        .info-box strong {{ color: #1976d2; display: block; margin-bottom: 10px; font-size: 18px; }}
        a {{ color: #667eea; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    {sidebar_html}
    <div class="main-content">
    <div class="container">
        <div class="header">
            <h1>⏱️ Выполнения заданий</h1>
            <p>История выполнения заданий пользователями. Отслеживание статусов и наград.</p>
        </div>
        
        <div class="info-box">
            <strong>💡 История выполнений:</strong>
            Здесь отображается история выполнения заданий пользователями. Вы можете видеть, кто выполнил какое задание, какой статус выполнения (ожидает, в процессе, выполнено, провалено) и какая награда была начислена.
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Пользователь</th>
                    <th>Telegram ID</th>
                    <th>Задание</th>
                    <th>Тип</th>
                    <th>Награда</th>
                    <th>Статус</th>
                    <th>Начато</th>
                    <th>Завершено</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    </div>
    </div>
    <script src="/admin/static/admin_menu.js"></script>
</body>
</html>"""
    
    return HTMLResponse(content=html)
