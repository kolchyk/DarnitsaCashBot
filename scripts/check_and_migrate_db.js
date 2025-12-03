#!/usr/bin/env node
/**
 * Скрипт для проверки и применения миграций базы данных Heroku
 * Проверяет текущий статус миграций и применяет их при необходимости
 */

const { execSync } = require('child_process');

const HEROKU_APP_NAME = 'darnitsacashbot';

console.log('='.repeat(60));
console.log('🔍 Проверка статуса миграций базы данных');
console.log('='.repeat(60));
console.log(`Приложение: ${HEROKU_APP_NAME}`);
console.log('='.repeat(60));

try {
  console.log('\n📊 Проверка текущего статуса миграций...');
  console.log('   Выполняется: heroku run alembic current --app ' + HEROKU_APP_NAME);
  
  const currentCommand = `npx --yes heroku run alembic current --app ${HEROKU_APP_NAME}`;
  const currentOutput = execSync(currentCommand, { 
    encoding: 'utf-8', 
    stdio: ['pipe', 'pipe', 'pipe'] 
  });
  
  console.log('\n📋 Текущий статус миграций:');
  console.log(currentOutput);
  
  console.log('\n🚀 Применение миграций до последней версии...');
  console.log('   Выполняется: heroku run alembic upgrade head --app ' + HEROKU_APP_NAME);
  
  const upgradeCommand = `npx --yes heroku run alembic upgrade head --app ${HEROKU_APP_NAME}`;
  const upgradeOutput = execSync(upgradeCommand, { 
    encoding: 'utf-8', 
    stdio: ['pipe', 'pipe', 'pipe'] 
  });
  
  console.log('\n✅ Результат применения миграций:');
  console.log(upgradeOutput);
  
  console.log('\n' + '='.repeat(60));
  console.log('✅ Миграции успешно применены!');
  console.log('='.repeat(60));
  
} catch (error) {
  console.error('\n❌ Ошибка при работе с миграциями:');
  console.error('   Тип ошибки:', error.constructor.name);
  console.error('   Сообщение:', error.message);
  if (error.stdout) {
    console.error('\n   Вывод команды:');
    console.error(error.stdout);
  }
  if (error.stderr) {
    console.error('\n   Ошибки:');
    console.error(error.stderr);
  }
  process.exit(1);
}

