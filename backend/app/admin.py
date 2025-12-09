from sqladmin import ModelView, Admin, BaseView, expose
from app.models import User, Task, UserBalance, UserTask, UserRole, TaskStatus, UserTaskStatus, TaskReport, TaskReportStatus
from sqlalchemy import func, and_
from app.database import SessionLocal
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime, timedelta

class DashboardView(BaseView):
    name = "Главная"
    icon = "fa-solid fa-chart-line"
    identity = "dashboard"
    
    def get_url_path(self) -> str:
        """Переопределяем URL для правильной генерации ссылок в меню"""
        return "/admin/dashboard"

    @expose("/", methods=["GET"])
    async def index(self, request: Request):
        # Собираем статистику
        db = SessionLocal()
        try:
            # Основная статистика
            total_users = db.query(User).count()
            active_tasks = db.query(Task).filter(Task.status == TaskStatus.ACTIVE).count()
            completed_tasks = db.query(UserTask).filter(UserTask.status == UserTaskStatus.COMPLETED).count()
            pending_reports = db.query(TaskReport).filter(TaskReport.status == TaskReportStatus.PENDING).count()
            
            # Финансы
            total_balance_nano = db.query(func.sum(UserBalance.ton_active_balance)).scalar() or 0
            total_balance_ton = round(float(total_balance_nano) / 10**9, 2)
            
            # Общий оборот (все деньги, которые прошли через систему)
            total_turnover_nano = db.query(func.sum(Task.price_per_slot_ton * Task.total_slots)).scalar() or 0
            total_turnover_ton = round(float(total_turnover_nano) / 10**9, 2)
            
            # Прибыль приложения (комиссия 10% с каждого выполненного задания)
            app_profit_ton = round(total_turnover_ton * 0.10, 2)
            
            # Статистика за сегодня
            today = datetime.now().date()
            today_users = db.query(User).filter(func.date(User.created_at) == today).count()
            today_tasks = db.query(Task).filter(func.date(Task.created_at) == today).count()
            today_completed = db.query(UserTask).filter(
                and_(
                    UserTask.status == UserTaskStatus.COMPLETED,
                    func.date(UserTask.created_at) == today
                )
            ).count()
            
            # Статистика за неделю
            week_ago = datetime.now() - timedelta(days=7)
            week_users = db.query(User).filter(User.created_at >= week_ago).count()
            week_tasks = db.query(Task).filter(Task.created_at >= week_ago).count()
            
        finally:
            db.close()

        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Главная - Админка BlackMirrowMarket</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; background: #f5f7fa; color: #333; line-height: 1.6; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .header h1 {{ font-size: 32px; margin-bottom: 10px; }}
        .header p {{ font-size: 16px; opacity: 0.9; }}
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
        .action-card li:last-child {{ border-bottom: none; }}
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
                    <p style="color: #666; font-size: 14px;">Показывает общий оборот, прибыль приложения (10% комиссия), статистику по типам заданий и периодам.</p>
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
</body>
</html>"""
        
        return HTMLResponse(content=html)

class TaskAdminView(ModelView, model=Task):
    name = "Задания"
    name_plural = "Задания"
    icon = "fa-solid fa-list-check"
    
    column_list = [
        Task.id,
        Task.title,
        Task.task_type,
        Task.status,
        Task.completed_slots,
        Task.total_slots,
        Task.creator_id,
        Task.created_at
    ]
    
    column_searchable_list = [Task.title, Task.id]
    column_sortable_list = [Task.id, Task.created_at, Task.completed_slots]
    form_excluded_columns = [Task.price_per_slot_ton]
    
    column_labels = {
        Task.task_type: "Тип задания",
        Task.status: "Статус",
        Task.completed_slots: "Выполнено",
        Task.total_slots: "Всего слотов",
        Task.creator_id: "ID создателя"
    }

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.telegram_id, User.username, User.first_name, User.role, User.is_banned, User.created_at]
    column_searchable_list = [User.username, User.telegram_id, User.first_name]
    column_sortable_list = [User.id, User.created_at, User.is_banned]
    
    icon = "fa-solid fa-user"
    name = "Пользователь"
    name_plural = "Пользователи"
    
    form_columns = [
        User.telegram_id,
        User.username,
        User.first_name,
        User.last_name,
        User.age,
        User.gender,
        User.country,
        User.role,
        User.is_banned,
        User.ban_until,
        User.ban_reason,
    ]
    
    column_labels = {
        User.is_banned: "Заблокирован",
        User.ban_until: "Блокировка до (YYYY-MM-DD HH:MM или пусто для постоянной)",
        User.ban_reason: "Причина блокировки (будет показана пользователю)"
    }

class UserBalanceAdmin(ModelView, model=UserBalance):
    column_list = [UserBalance.user_id, UserBalance.ton_active_balance, UserBalance.ton_escrow_balance]
    column_sortable_list = [UserBalance.ton_active_balance]
    icon = "fa-solid fa-wallet"
    name = "Баланс"
    name_plural = "Балансы"
    
    column_labels = {
        UserBalance.user_id: "ID пользователя",
        UserBalance.ton_active_balance: "Активный баланс (нано-TON)",
        UserBalance.ton_escrow_balance: "В эскроу (нано-TON)"
    }

class UserTaskAdmin(ModelView, model=UserTask):
    column_list = [UserTask.id, UserTask.user_id, UserTask.task_id, UserTask.status, UserTask.reward_ton]
    column_sortable_list = [UserTask.created_at]
    icon = "fa-solid fa-clock-rotate-left"
    name = "Выполнение"
    name_plural = "Выполнения"
    
    column_labels = {
        UserTask.user_id: "ID пользователя",
        UserTask.task_id: "ID задания",
        UserTask.status: "Статус",
        UserTask.reward_ton: "Награда (нано-TON)"
    }

class ProfitView(BaseView):
    name = "Прибыль"
    icon = "fa-solid fa-dollar-sign"
    identity = "profit"
    
    def get_url_path(self) -> str:
        """Переопределяем URL для правильной генерации ссылок в меню"""
        return "/admin/profit"

    @expose("/", methods=["GET"])
    async def index(self, request: Request):
        db = SessionLocal()
        try:
            total_turnover_nano = db.query(func.sum(Task.price_per_slot_ton * Task.total_slots)).scalar() or 0
            total_turnover_ton = round(float(total_turnover_nano) / 10**9, 2)
            app_profit_ton = round(total_turnover_ton * 0.10, 2)
            
            subscription_turnover = db.query(func.sum(Task.price_per_slot_ton * Task.total_slots)).filter(
                Task.task_type == "subscription"
            ).scalar() or 0
            comment_turnover = db.query(func.sum(Task.price_per_slot_ton * Task.total_slots)).filter(
                Task.task_type == "comment"
            ).scalar() or 0
            view_turnover = db.query(func.sum(Task.price_per_slot_ton * Task.total_slots)).filter(
                Task.task_type == "view"
            ).scalar() or 0
            
            today = datetime.now().date()
            week_ago = datetime.now() - timedelta(days=7)
            month_ago = datetime.now() - timedelta(days=30)
            
            turnover_today = db.query(func.sum(Task.price_per_slot_ton * Task.total_slots)).filter(
                func.date(Task.created_at) == today
            ).scalar() or 0
            turnover_week = db.query(func.sum(Task.price_per_slot_ton * Task.total_slots)).filter(
                Task.created_at >= week_ago
            ).scalar() or 0
            turnover_month = db.query(func.sum(Task.price_per_slot_ton * Task.total_slots)).filter(
                Task.created_at >= month_ago
            ).scalar() or 0
            
        finally:
            db.close()

        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Прибыль - Админка</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #333; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }}
        .header h1 {{ font-size: 32px; margin-bottom: 10px; }}
        .info-box {{ background: #e3f2fd; border-left: 4px solid #2196f3; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        .info-box strong {{ color: #1976d2; display: block; margin-bottom: 10px; font-size: 18px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }}
        .stat-card {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-card.gradient {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
        .stat-card.gradient-green {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; }}
        .stat-card h3 {{ font-size: 14px; text-transform: uppercase; margin-bottom: 10px; opacity: 0.9; }}
        .stat-card .value {{ font-size: 36px; font-weight: bold; }}
        table {{ width: 100%; background: white; border-collapse: collapse; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; }}
        th, td {{ padding: 15px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #667eea; color: white; font-weight: 600; }}
        tr:hover {{ background: #f5f5f5; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💰 Финансовая статистика</h1>
        </div>
        
        <div class="info-box">
            <strong>💡 Как это работает:</strong>
            Приложение берет комиссию 10% с каждого выполненного задания. Комиссия вычитается с пользователя, который выполнил задание (исполнителя). Это означает, что если исполнитель выполнил задание на 100 TON, приложение получит 10 TON прибыли, а исполнитель получит 90 TON.
        </div>
        
        <div class="stats-grid">
            <div class="stat-card gradient">
                <h3>Общий оборот</h3>
                <div class="value">{total_turnover_ton:.2f} TON</div>
            </div>
            <div class="stat-card gradient-green">
                <h3>Прибыль приложения (10%)</h3>
                <div class="value">{app_profit_ton:.2f} TON</div>
            </div>
        </div>
        
        <h2 style="margin: 30px 0 15px 0;">📊 Оборот по типам заданий</h2>
        <table>
            <thead>
                <tr>
                    <th>Тип задания</th>
                    <th>Оборот (TON)</th>
                    <th>Прибыль (10%)</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Подписка</td>
                    <td>{round(float(subscription_turnover) / 10**9, 2):.2f}</td>
                    <td>{round(float(subscription_turnover) / 10**9 * 0.10, 2):.2f}</td>
                </tr>
                <tr>
                    <td>Комментарий</td>
                    <td>{round(float(comment_turnover) / 10**9, 2):.2f}</td>
                    <td>{round(float(comment_turnover) / 10**9 * 0.10, 2):.2f}</td>
                </tr>
                <tr>
                    <td>Просмотр</td>
                    <td>{round(float(view_turnover) / 10**9, 2):.2f}</td>
                    <td>{round(float(view_turnover) / 10**9 * 0.10, 2):.2f}</td>
                </tr>
            </tbody>
        </table>
        
        <h2 style="margin: 30px 0 15px 0;">📈 Оборот по периодам</h2>
        <table>
            <thead>
                <tr>
                    <th>Период</th>
                    <th>Оборот (TON)</th>
                    <th>Прибыль (10%)</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Сегодня</td>
                    <td>{round(float(turnover_today) / 10**9, 2):.2f}</td>
                    <td>{round(float(turnover_today) / 10**9 * 0.10, 2):.2f}</td>
                </tr>
                <tr>
                    <td>За неделю</td>
                    <td>{round(float(turnover_week) / 10**9, 2):.2f}</td>
                    <td>{round(float(turnover_week) / 10**9 * 0.10, 2):.2f}</td>
                </tr>
                <tr>
                    <td>За месяц</td>
                    <td>{round(float(turnover_month) / 10**9, 2):.2f}</td>
                    <td>{round(float(turnover_month) / 10**9 * 0.10, 2):.2f}</td>
                </tr>
            </tbody>
        </table>
    </div>
</body>
</html>"""
        
        return HTMLResponse(content=html)

class ComplaintsView(BaseView):
    name = "Жалобы"
    icon = "fa-solid fa-flag"
    identity = "complaints"
    
    def get_url_path(self) -> str:
        """Переопределяем URL для правильной генерации ссылок в меню"""
        return "/admin/complaints"

    @expose("/", methods=["GET"])
    async def index(self, request: Request):
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
                    "moderator_notes": report.moderator_notes,
                    "created_at": report.created_at.strftime("%Y-%m-%d %H:%M") if report.created_at else None,
                    "resolved_at": report.resolved_at.strftime("%Y-%m-%d %H:%M") if report.resolved_at else None,
                })
        finally:
            db.close()

        rows_html = ""
        if reports_data:
            for r in reports_data:
                status_colors = {
                    "pending": "#ff9800",
                    "reviewing": "#2196f3",
                    "resolved": "#4caf50",
                    "rejected": "#f44336"
                }
                status_color = status_colors.get(r["status"], "#666")
                
                rows_html += f"""
                <tr>
                    <td>{r['id']}</td>
                    <td><a href="/admin/task/detail/{r['task_id']}" style="color: #667eea;">#{r['task_id']}</a> - {r['task_title'][:50]}</td>
                    <td>@{r['reporter_username']} ({r['reporter_telegram_id']})</td>
                    <td>{r['reason'][:100]}</td>
                    <td><span style="color: {status_color}; font-weight: bold;">{r['status'].upper()}</span></td>
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
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #333; line-height: 1.6; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #f44336 0%, #e91e63 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }}
        .header h1 {{ font-size: 32px; margin-bottom: 10px; }}
        .info-box {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        .info-box strong {{ color: #856404; display: block; margin-bottom: 10px; font-size: 18px; }}
        .badge {{ display: inline-block; padding: 5px 10px; border-radius: 4px; font-size: 12px; font-weight: bold; background: #ff9800; color: white; }}
        table {{ width: 100%; background: white; border-collapse: collapse; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #667eea; color: white; font-weight: 600; }}
        tr:hover {{ background: #f5f5f5; }}
        a {{ color: #667eea; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚩 Жалобы пользователей</h1>
        </div>
        
        <div class="info-box">
            <strong>💡 Как работать с жалобами:</strong>
            Пользователи могут пожаловаться на задание, если оно нарушает правила. Просмотрите жалобу, проверьте задание и примите решение: решить (заблокировать задание) или отклонить (жалоба необоснованна).
        </div>
        
        <p style="margin: 20px 0;"><strong>Ожидают рассмотрения:</strong> <span class="badge">{len(pending_reports)}</span></p>
        
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
</body>
</html>"""
        
        return HTMLResponse(content=html)

class BanUserView(BaseView):
    name = "Блокировка пользователя"
    icon = "fa-solid fa-ban"
    identity = "ban-user"
    
    def get_url_path(self) -> str:
        """Переопределяем URL для правильной генерации ссылок в меню"""
        return "/admin/ban-user"

    @expose("/", methods=["GET", "POST"])
    async def ban_user(self, request: Request):
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

        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Блокировка пользователя - Админка</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #333; line-height: 1.6; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }}
        .header h1 {{ font-size: 32px; margin-bottom: 10px; }}
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
</body>
</html>"""
        
        return HTMLResponse(content=html)
