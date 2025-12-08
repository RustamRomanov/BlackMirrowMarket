// Боковое меню для всех страниц админки
(function() {
    // Функция для добавления меню
    function addSidebar() {
        // Проверяем, не добавлено ли уже меню
        if (document.getElementById('custom-admin-sidebar')) {
            return;
        }

        // Создаем боковое меню
        const sidebar = document.createElement('div');
        sidebar.id = 'custom-admin-sidebar';
        sidebar.className = 'custom-sidebar';
        
        // Определяем активную страницу
        const currentPath = window.location.pathname;
        let activeClass = '';
        if (currentPath === '/admin/dashboard' || currentPath === '/admin/') {
            activeClass = 'active';
        }
        
        sidebar.innerHTML = `
            <div class="custom-sidebar-header">
                <h2>📊 Админка</h2>
            </div>
            <nav class="custom-sidebar-nav">
                <a href="/admin/dashboard" class="custom-nav-item ${currentPath === '/admin/dashboard' || currentPath === '/admin/' ? 'active' : ''}" data-page="dashboard">
                    <span class="custom-nav-icon">📊</span>
                    <span class="custom-nav-text">Главная</span>
                </a>
                <a href="/admin/profit" class="custom-nav-item ${currentPath === '/admin/profit' ? 'active' : ''}" data-page="profit">
                    <span class="custom-nav-icon">💰</span>
                    <span class="custom-nav-text">Прибыль</span>
                </a>
                <a href="/admin/ton" class="custom-nav-item ${currentPath === '/admin/ton' ? 'active' : ''}" data-page="ton">
                    <span class="custom-nav-icon">🪙</span>
                    <span class="custom-nav-text">TON Кошелек</span>
                </a>
                <a href="/admin/complaints" class="custom-nav-item ${currentPath === '/admin/complaints' ? 'active' : ''}" data-page="complaints">
                    <span class="custom-nav-icon">🚩</span>
                    <span class="custom-nav-text">Жалобы</span>
                </a>
                <a href="/admin/ban-user" class="custom-nav-item ${currentPath === '/admin/ban-user' ? 'active' : ''}" data-page="ban-user">
                    <span class="custom-nav-icon">🚫</span>
                    <span class="custom-nav-text">Блокировка</span>
                </a>
                <a href="/admin/user/list" class="custom-nav-item ${currentPath.startsWith('/admin/user/list') ? 'active' : ''}" data-page="user">
                    <span class="custom-nav-icon">👥</span>
                    <span class="custom-nav-text">Пользователи</span>
                </a>
                <a href="/admin/task/list" class="custom-nav-item ${currentPath.startsWith('/admin/task/list') ? 'active' : ''}" data-page="task">
                    <span class="custom-nav-icon">📋</span>
                    <span class="custom-nav-text">Задания</span>
                </a>
                <a href="/admin/user-balance/list" class="custom-nav-item ${currentPath.startsWith('/admin/user-balance/list') ? 'active' : ''}" data-page="user-balance">
                    <span class="custom-nav-icon">💳</span>
                    <span class="custom-nav-text">Балансы</span>
                </a>
                <a href="/admin/user-task/list" class="custom-nav-item ${currentPath.startsWith('/admin/user-task/list') ? 'active' : ''}" data-page="user-task">
                    <span class="custom-nav-icon">⏱️</span>
                    <span class="custom-nav-text">Выполнения</span>
                </a>
            </nav>
        `;

        // Добавляем стили
        if (!document.getElementById('custom-sidebar-styles')) {
            const style = document.createElement('style');
            style.id = 'custom-sidebar-styles';
            style.textContent = `
                .custom-sidebar {
                    width: 260px;
                    background: #2c3e50;
                    color: white;
                    min-height: 100vh;
                    position: fixed;
                    left: 0;
                    top: 0;
                    overflow-y: auto;
                    z-index: 1000;
                }
                .custom-sidebar-header {
                    padding: 20px;
                    background: #1a252f;
                    border-bottom: 1px solid #34495e;
                }
                .custom-sidebar-header h2 {
                    font-size: 20px;
                    font-weight: 600;
                    margin: 0;
                    color: white;
                }
                .custom-sidebar-nav {
                    padding: 10px 0;
                }
                .custom-nav-item {
                    display: flex;
                    align-items: center;
                    padding: 12px 20px;
                    color: #ecf0f1;
                    text-decoration: none;
                    transition: all 0.3s;
                    border-left: 3px solid transparent;
                }
                .custom-nav-item:hover {
                    background: #34495e;
                    border-left-color: #3498db;
                }
                .custom-nav-item.active {
                    background: #34495e;
                    border-left-color: #3498db;
                    font-weight: 600;
                }
                .custom-nav-icon {
                    font-size: 18px;
                    margin-right: 12px;
                    width: 24px;
                    text-align: center;
                }
                .custom-nav-text {
                    font-size: 15px;
                }
                body {
                    margin-left: 260px !important;
                    padding-left: 0 !important;
                }
                /* Для страниц sqladmin */
                .container-fluid, .container {
                    margin-left: 0 !important;
                }
                /* Убираем отступы у основного контента sqladmin */
                .page-wrapper, .page-content {
                    margin-left: 0 !important;
                    padding-left: 0 !important;
                }
            `;
            document.head.appendChild(style);
        }

        // Добавляем меню в документ
        document.body.insertBefore(sidebar, document.body.firstChild);

        // Добавляем отступ для body, если его еще нет
        if (!document.body.style.marginLeft || document.body.style.marginLeft === '0px') {
            document.body.style.marginLeft = '260px';
        }
    }
    
    // Запускаем сразу, если DOM готов
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', addSidebar);
    } else {
        addSidebar();
    }
    
    // Также пробуем через небольшую задержку (на случай, если страница загружается динамически)
    setTimeout(addSidebar, 100);
    setTimeout(addSidebar, 500);
    setTimeout(addSidebar, 1000);
    
    // Слушаем изменения DOM (для динамически загружаемых страниц)
    const observer = new MutationObserver(function(mutations) {
        addSidebar();
    });
    observer.observe(document.body, { childList: true, subtree: true });
})();
