-- Критичные индексы для производительности
-- Выполнить после создания всех таблиц

-- Пользователи
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code) WHERE referral_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_referrer_id ON users(referrer_id) WHERE referrer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- Балансы (самая частая операция!)
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_balances_user_id ON user_balances(user_id);
CREATE INDEX IF NOT EXISTS idx_user_balances_updated_at ON user_balances(updated_at);

-- Задания
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_tasks_creator_id ON tasks(creator_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_is_test ON tasks(is_test) WHERE is_test = false;
CREATE INDEX IF NOT EXISTS idx_tasks_task_type ON tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_tasks_status_type ON tasks(status, task_type) WHERE status = 'active';

-- Транзакции TON
CREATE INDEX IF NOT EXISTS idx_ton_transactions_user_id ON ton_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_ton_transactions_status ON ton_transactions(status) WHERE status = 'pending';
CREATE UNIQUE INDEX IF NOT EXISTS idx_ton_transactions_tx_hash ON ton_transactions(tx_hash) WHERE tx_hash IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_ton_transactions_idempotency_key ON ton_transactions(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_ton_transactions_created_at ON ton_transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_ton_transactions_user_status ON ton_transactions(user_id, status);

-- Депозиты
CREATE UNIQUE INDEX IF NOT EXISTS idx_deposits_tx_hash ON deposits(tx_hash);
CREATE INDEX IF NOT EXISTS idx_deposits_user_id ON deposits(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_deposits_status ON deposits(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_deposits_created_at ON deposits(created_at);
CREATE INDEX IF NOT EXISTS idx_deposits_processed_at ON deposits(processed_at) WHERE processed_at IS NOT NULL;

-- Выполнения заданий
CREATE INDEX IF NOT EXISTS idx_user_tasks_user_id ON user_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_user_tasks_task_id ON user_tasks(task_id);
CREATE INDEX IF NOT EXISTS idx_user_tasks_status ON user_tasks(status);
CREATE INDEX IF NOT EXISTS idx_user_tasks_escrow_ends_at ON user_tasks(escrow_ends_at) WHERE status = 'in_progress';
CREATE INDEX IF NOT EXISTS idx_user_tasks_user_status ON user_tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_user_tasks_created_at ON user_tasks(created_at);

-- Рефералы
CREATE INDEX IF NOT EXISTS idx_referrals_referrer_id ON referrals(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referrals_referred_id ON referrals(referred_id);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer_referred ON referrals(referrer_id, referred_id);

-- Жалобы
CREATE INDEX IF NOT EXISTS idx_task_reports_status ON task_reports(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_task_reports_task_id ON task_reports(task_id);
CREATE INDEX IF NOT EXISTS idx_task_reports_user_id ON task_reports(user_id);
CREATE INDEX IF NOT EXISTS idx_task_reports_created_at ON task_reports(created_at);

-- Прибыль
CREATE INDEX IF NOT EXISTS idx_profit_withdrawals_status ON profit_withdrawals(status);
CREATE INDEX IF NOT EXISTS idx_profit_withdrawals_created_at ON profit_withdrawals(created_at);

-- Анализ производительности
-- Включить расширение для мониторинга запросов
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Обновить статистику для оптимизатора
ANALYZE;

