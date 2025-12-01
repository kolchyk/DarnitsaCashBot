# Проверка содержимого базы данных на Heroku

Этот документ описывает различные способы проверки содержимого базы данных PostgreSQL на Heroku.

## Быстрая проверка структуры базы данных

### 1. Использование существующего скрипта

Проект содержит скрипт `check_database.py`, который проверяет подключение, структуру таблиц и их содержимое:

```bash
heroku run python scripts/check_database.py
```

Этот скрипт покажет:
- ✅ Статус подключения к базе данных
- 📊 Список всех таблиц и количество записей в каждой
- 🔍 Проверку наличия ожидаемых таблиц
- 🔄 Текущую версию миграций Alembic
- 📈 Статистику базы данных (размер, активные подключения)

### 2. Прямое подключение через psql

Для интерактивной работы с базой данных используйте `heroku pg:psql`:

```bash
# Подключение к базе данных
heroku pg:psql

# Или для конкретного приложения
heroku pg:psql -a your-app-name
```

После подключения вы можете выполнять SQL-запросы:

```sql
-- Просмотр всех таблиц
\dt

-- Просмотр структуры таблицы
\d users
\d receipts
\d bonus_transactions

-- Подсчет записей в таблицах
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM receipts;
SELECT COUNT(*) FROM bonus_transactions;
SELECT COUNT(*) FROM line_items;

-- Просмотр последних пользователей
SELECT id, telegram_id, phone_number, locale, created_at 
FROM users 
ORDER BY created_at DESC 
LIMIT 10;

-- Просмотр последних чеков
SELECT id, user_id, status, merchant, purchase_ts, created_at 
FROM receipts 
ORDER BY created_at DESC 
LIMIT 10;

-- Просмотр бонусных транзакций
SELECT id, user_id, receipt_id, msisdn, amount, payout_status, created_at 
FROM bonus_transactions 
ORDER BY created_at DESC 
LIMIT 10;

-- Выход из psql
\q
```

### 3. Выполнение SQL-запросов без интерактивного режима

Вы можете выполнять SQL-запросы напрямую из командной строки:

```bash
# Подсчет записей в таблицах
heroku pg:psql -c "SELECT COUNT(*) FROM users;"
heroku pg:psql -c "SELECT COUNT(*) FROM receipts;"
heroku pg:psql -c "SELECT COUNT(*) FROM bonus_transactions;"

# Просмотр структуры таблицы
heroku pg:psql -c "\d users"

# Просмотр последних 5 пользователей
heroku pg:psql -c "SELECT telegram_id, locale, created_at FROM users ORDER BY created_at DESC LIMIT 5;"
```

## Детальная проверка данных

### Просмотр пользователей

```bash
heroku pg:psql -c "
SELECT 
    id,
    telegram_id,
    phone_number,
    locale,
    consent_timestamp,
    created_at,
    updated_at
FROM users
ORDER BY created_at DESC
LIMIT 20;
"
```

### Просмотр чеков с деталями

```bash
heroku pg:psql -c "
SELECT 
    r.id,
    r.user_id,
    u.telegram_id,
    r.status,
    r.merchant,
    r.purchase_ts,
    r.created_at,
    COUNT(li.id) as items_count
FROM receipts r
LEFT JOIN users u ON r.user_id = u.id
LEFT JOIN line_items li ON li.receipt_id = r.id
GROUP BY r.id, u.telegram_id
ORDER BY r.created_at DESC
LIMIT 20;
"
```

### Просмотр бонусных транзакций

```bash
heroku pg:psql -c "
SELECT 
    bt.id,
    bt.user_id,
    u.telegram_id,
    bt.receipt_id,
    bt.msisdn,
    bt.amount,
    bt.payout_status,
    bt.provider,
    bt.portmone_status,
    bt.portmone_error_code,
    bt.created_at
FROM bonus_transactions bt
LEFT JOIN users u ON bt.user_id = u.id
ORDER BY bt.created_at DESC
LIMIT 20;
"
```

### Статистика по статусам чеков

```bash
heroku pg:psql -c "
SELECT 
    status,
    COUNT(*) as count
FROM receipts
GROUP BY status
ORDER BY count DESC;
"
```

### Статистика по статусам бонусных транзакций

```bash
heroku pg:psql -c "
SELECT 
    payout_status,
    COUNT(*) as count,
    SUM(amount) as total_amount_kopecks
FROM bonus_transactions
GROUP BY payout_status
ORDER BY count DESC;
"
```

## Информация о базе данных

### Базовая информация

```bash
# Информация о базе данных (размер, статус, план)
heroku pg:info

# Список всех аддонов PostgreSQL
heroku addons | grep postgres

# URL подключения к базе данных (без пароля)
heroku config:get DATABASE_URL
```

### Размер базы данных и таблиц

```bash
heroku pg:psql -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

## Использование Python скриптов для проверки

### Создание скрипта для детального просмотра данных

Вы можете создать скрипт для более удобного просмотра данных. Пример:

```bash
# Запуск Python интерактивно на Heroku
heroku run python

# Затем в Python:
from libs.data.database import get_async_session
from libs.data.models.user import User
from libs.data.models.receipt import Receipt
from libs.data.models.bonus import BonusTransaction
import asyncio

async def check():
    async for session in get_async_session():
        users = await session.execute(select(User).limit(10))
        print("Users:", users.scalars().all())
        break

asyncio.run(check())
```

## Экспорт данных

### Экспорт таблицы в CSV

```bash
# Экспорт пользователей
heroku pg:psql -c "COPY (SELECT * FROM users) TO STDOUT WITH CSV HEADER;" > users.csv

# Экспорт чеков
heroku pg:psql -c "COPY (SELECT * FROM receipts) TO STDOUT WITH CSV HEADER;" > receipts.csv
```

### Создание резервной копии

```bash
# Создание дампа базы данных
heroku pg:backups:capture

# Скачивание последнего дампа
heroku pg:backups:download

# Просмотр списка резервных копий
heroku pg:backups
```

## Полезные команды для отладки

### Проверка подключений к базе данных

```bash
heroku pg:psql -c "
SELECT 
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query_start,
    state_change
FROM pg_stat_activity
WHERE datname = current_database();
"
```

### Проверка индексов

```bash
heroku pg:psql -c "
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
"
```

### Проверка версии миграций

```bash
heroku pg:psql -c "SELECT * FROM alembic_version;"
```

## Troubleshooting

### Проблемы с подключением

Если возникают проблемы с подключением:

1. **Проверьте наличие аддона PostgreSQL:**
   ```bash
   heroku addons | grep postgres
   ```

2. **Проверьте переменную DATABASE_URL:**
   ```bash
   heroku config:get DATABASE_URL
   ```

3. **Проверьте статус базы данных:**
   ```bash
   heroku pg:info
   ```

### Проблемы с миграциями

Если таблицы отсутствуют или структура устарела:

```bash
# Проверка текущей версии миграций
heroku run alembic current

# Применение всех миграций
heroku run alembic upgrade head

# Просмотр истории миграций
heroku run alembic history
```

## Безопасность

⚠️ **Важно:**
- Никогда не коммитьте данные из продакшн базы данных
- Будьте осторожны при выполнении операций DELETE или UPDATE
- Всегда создавайте резервные копии перед важными изменениями
- Используйте транзакции для тестирования изменений

