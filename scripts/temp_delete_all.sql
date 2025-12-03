
BEGIN;

-- 1. Удаляем line_items (зависит от receipts)
DELETE FROM line_items;

-- 2. Удаляем bonus_transactions (зависит от receipts и users)
DELETE FROM bonus_transactions;

-- 3. Удаляем receipts (чеки) (зависит от users)
DELETE FROM receipts;

-- 4. Удаляем users
DELETE FROM users;

COMMIT;

-- Показываем статистику
SELECT 
    (SELECT COUNT(*) FROM users) as users_count,
    (SELECT COUNT(*) FROM receipts) as receipts_count,
    (SELECT COUNT(*) FROM bonus_transactions) as bonus_transactions_count,
    (SELECT COUNT(*) FROM line_items) as line_items_count;
