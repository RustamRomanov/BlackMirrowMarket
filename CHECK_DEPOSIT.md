# Проверка депозита пользователя 8032604270

## Проблема
Пользователь пополнил баланс, но средства не отображаются.

## Возможные причины:
1. Транзакция не была обнаружена системой
2. Telegram ID не был указан в комментарии транзакции
3. Депозит найден, но не обработан (статус "pending")
4. Ошибка при обработке депозита (статус "failed")

## Как проверить:

### 1. Проверить логи Railway
Зайдите в Railway → Ваш сервис → Logs и найдите:
- Сообщения о депозитах: `✅ Автоматически зачислено`
- Ошибки: `⚠️ Ошибка обработки депозита`
- Ошибки API: `TON API error`

### 2. Проверить через админку
1. Откройте админку: `https://ваш-домен.railway.app/admin`
2. Перейдите в раздел "Deposits" (если есть)
3. Найдите депозиты с Telegram ID `8032604270` в комментарии

### 3. Проверить через базу данных
Если у вас есть доступ к PostgreSQL на Railway:
```sql
-- Найти пользователя
SELECT * FROM users WHERE telegram_id = 8032604270;

-- Найти депозиты пользователя
SELECT * FROM deposits 
WHERE user_id = (SELECT id FROM users WHERE telegram_id = 8032604270)
   OR telegram_id_from_comment = '8032604270'
ORDER BY created_at DESC;

-- Проверить баланс
SELECT * FROM user_balances 
WHERE user_id = (SELECT id FROM users WHERE telegram_id = 8032604270);
```

### 4. Ручная обработка депозита
Если депозит найден, но не обработан:

1. Найдите депозит в базе данных
2. Проверьте, что `telegram_id_from_comment = '8032604270'`
3. Если статус `pending` или `failed`, можно обработать вручную:

```python
# В админке или через скрипт
from app.database import SessionLocal
from app import models
from decimal import Decimal

db = SessionLocal()
try:
    # Найти депозит
    deposit = db.query(models.Deposit).filter(
        models.Deposit.telegram_id_from_comment == '8032604270',
        models.Deposit.status == 'pending'
    ).first()
    
    if deposit:
        # Найти пользователя
        user = db.query(models.User).filter(
            models.User.telegram_id == 8032604270
        ).first()
        
        if user:
            # Зачислить на баланс
            balance = db.query(models.UserBalance).filter(
                models.UserBalance.user_id == user.id
            ).first()
            
            if not balance:
                balance = models.UserBalance(
                    user_id=user.id,
                    ton_active_balance=deposit.amount_nano,
                    last_fiat_rate=Decimal("250"),
                    fiat_currency="RUB"
                )
                db.add(balance)
            else:
                balance.ton_active_balance += deposit.amount_nano
            
            deposit.user_id = user.id
            deposit.status = "processed"
            deposit.processed_at = datetime.utcnow()
            db.commit()
            print(f"✅ Зачислено {deposit.amount_nano / 10**9:.4f} TON")
finally:
    db.close()
```

## Что проверить у пользователя:
1. Указал ли он Telegram ID в комментарии к транзакции?
2. Правильный ли адрес кошелька использовался?
3. Подтверждена ли транзакция в блокчейне?
4. Прошло ли достаточно времени (1-2 минуты после подтверждения)?

## Если депозит не найден:
1. Проверьте, что TON API ключ настроен на Railway
2. Проверьте, что адрес сервисного кошелька правильный
3. Проверьте логи на ошибки API
4. Возможно, нужно подождать - система проверяет депозиты каждую минуту

