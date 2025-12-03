#!/usr/bin/env node
/**
 * Скрипт для удаления всех пользователей и чеков из базы данных Heroku
 * Использует Heroku CLI для получения DATABASE_URL и выполняет SQL через pg
 */

const { execSync } = require('child_process');
const { Client } = require('pg');
const fs = require('fs');
const path = require('path');

const HEROKU_APP_NAME = 'darnitsacashbot';

// SQL команды для удаления всех данных
const SQL_COMMANDS = `
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
`;

/**
 * Получить DATABASE_URL из Heroku используя Heroku CLI
 */
function getDatabaseUrl() {
  console.log('📡 Получение DATABASE_URL из Heroku через CLI...');
  
  try {
    const command = `npx --yes heroku config:get DATABASE_URL --app ${HEROKU_APP_NAME}`;
    const dbUrl = execSync(command, { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
    
    if (!dbUrl) {
      throw new Error('DATABASE_URL пустой');
    }
    
    console.log('✅ DATABASE_URL получен через Heroku CLI');
    return dbUrl;
  } catch (error) {
    console.error('❌ Ошибка при получении DATABASE_URL из Heroku:');
    console.error('   Убедитесь, что Heroku CLI доступен через npx');
    throw error;
  }
}

async function deleteAllData() {
  console.log('='.repeat(60));
  console.log('🧹 Очистка базы данных Heroku');
  console.log('='.repeat(60));
  console.log(`Приложение: ${HEROKU_APP_NAME}`);
  console.log('='.repeat(60));
  
  // Получаем DATABASE_URL через Heroku CLI
  const dbUrl = getDatabaseUrl();
  
  console.log('\n🔌 Подключение к базе данных...');
  
  const client = new Client({
    connectionString: dbUrl,
    ssl: {
      rejectUnauthorized: false // Для AWS RDS/Heroku Postgres
    },
    connectionTimeoutMillis: 30000,
    query_timeout: 60000
  });

  let transactionStarted = false;
  
  try {
    console.log('   Попытка подключения...');
    await client.connect();
    console.log('✅ Подключено к базе данных\n');

    // Начинаем транзакцию
    await client.query('BEGIN');
    transactionStarted = true;

    console.log('🗑️  Удаление данных...\n');

    // 1. Удаляем line_items (зависит от receipts)
    console.log('1️⃣  Удаление line_items...');
    const lineItemsResult = await client.query('DELETE FROM line_items');
    console.log(`   ✅ Удалено ${lineItemsResult.rowCount} записей из line_items`);

    // 2. Удаляем bonus_transactions (зависит от receipts и users)
    console.log('2️⃣  Удаление bonus_transactions...');
    const bonusResult = await client.query('DELETE FROM bonus_transactions');
    console.log(`   ✅ Удалено ${bonusResult.rowCount} записей из bonus_transactions`);

    // 3. Удаляем receipts (чеки) (зависит от users)
    console.log('3️⃣  Удаление receipts (чеки)...');
    const receiptsResult = await client.query('DELETE FROM receipts');
    console.log(`   ✅ Удалено ${receiptsResult.rowCount} записей из receipts`);

    // 4. Удаляем users
    console.log('4️⃣  Удаление users...');
    const usersResult = await client.query('DELETE FROM users');
    console.log(`   ✅ Удалено ${usersResult.rowCount} записей из users`);

    // Коммитим транзакцию
    await client.query('COMMIT');
    
    console.log('\n✅ Все данные успешно удалены!');
    
    // Показываем статистику
    console.log('\n📊 Статистика удаления:');
    console.log(`   - Пользователей: ${usersResult.rowCount}`);
    console.log(`   - Чеков: ${receiptsResult.rowCount}`);
    console.log(`   - Транзакций бонусов: ${bonusResult.rowCount}`);
    console.log(`   - Позиций чеков: ${lineItemsResult.rowCount}`);

  } catch (error) {
    // Откатываем транзакцию в случае ошибки
    if (transactionStarted) {
      try {
        await client.query('ROLLBACK');
      } catch (rollbackError) {
        console.error('⚠️  Ошибка при откате транзакции:', rollbackError.message);
      }
    }
    console.error('\n❌ Ошибка при удалении данных:');
    console.error('   Тип ошибки:', error.constructor.name);
    console.error('   Сообщение:', error.message);
    if (error.stack) {
      console.error('   Stack:', error.stack);
    }
    throw error;
  } finally {
    try {
      await client.end();
      console.log('\n🔌 Соединение с базой данных закрыто');
    } catch (endError) {
      // Игнорируем ошибки при закрытии соединения
    }
  }
}

deleteAllData()
  .then(() => {
    console.log('\n✅ Скрипт завершен успешно');
    process.exit(0);
  })
  .catch((error) => {
    console.error('\n❌ Критическая ошибка:');
    console.error(error);
    process.exit(1);
  });

