#!/usr/bin/env node
/**
 * Скрипт для удаления всех пользователей и чеков из базы данных Heroku
 */

const { Client } = require('pg');

// DATABASE_URL для подключения к Heroku PostgreSQL
const DATABASE_URL = 'postgres://udsoi5dli0ta96:p7733ead1284915f292e44768fde954be2befd8c5c76f3216479425e681bfaf3a@c1erdbv5s7bd6i.cluster-czz5s0kz4scl.eu-west-1.rds.amazonaws.com:5432/ddv1kml2m2u456';

/**
 * Удалить все данные из базы
 */
async function deleteAllData() {
  console.log('\n🔌 Подключение к базе данных...');
  
  const client = new Client({
    connectionString: DATABASE_URL,
    ssl: {
      rejectUnauthorized: false // Для AWS RDS
    },
    connectionTimeoutMillis: 30000, // 30 секунд таймаут подключения
    query_timeout: 60000 // 60 секунд таймаут запросов
  });

  let transactionStarted = false;
  
  try {
    console.log('   Попытка подключения к базе данных...');
    console.log('   Хост: c1erdbv5s7bd6i.cluster-czz5s0kz4scl.eu-west-1.rds.amazonaws.com');
    
    // Подключаемся с таймаутом
    const connectPromise = client.connect();
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Таймаут подключения (30 секунд)')), 30000)
    );
    
    await Promise.race([connectPromise, timeoutPromise]);
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
    // Откатываем транзакцию в случае ошибки (только если она была начата)
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

// Запуск скрипта
console.log('='.repeat(60));
console.log('🧹 Очистка базы данных Heroku');
console.log('='.repeat(60));
console.log('База данных: ddv1kml2m2u456');
console.log('='.repeat(60));

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

