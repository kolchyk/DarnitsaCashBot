#!/bin/bash
# Быстрая настройка Cloudflare R2 для Heroku
# Использование: bash docs/r2_quick_setup.sh

echo "=========================================="
echo "Настройка Cloudflare R2 для DarnitsaCashBot"
echo "=========================================="
echo ""

# Запрос данных у пользователя
read -p "Введите Account ID (32 символа): " ACCOUNT_ID
read -p "Введите Bucket name: " BUCKET_NAME
read -p "Введите Access Key ID: " ACCESS_KEY
read -sp "Введите Secret Access Key: " SECRET_KEY
echo ""

# Формирование endpoint URL
ENDPOINT_URL="https://${ACCOUNT_ID}.r2.cloudflarestorage.com"

echo ""
echo "=========================================="
echo "Установка переменных окружения на Heroku"
echo "=========================================="
echo ""

# Установка переменных
heroku config:set STORAGE_ENDPOINT="${ENDPOINT_URL}"
heroku config:set STORAGE_BUCKET="${BUCKET_NAME}"
heroku config:set STORAGE_ACCESS_KEY="${ACCESS_KEY}"
heroku config:set STORAGE_SECRET_KEY="${SECRET_KEY}"
heroku config:set STORAGE_REGION="auto"

echo ""
echo "=========================================="
echo "Проверка конфигурации"
echo "=========================================="
echo ""

heroku config | grep STORAGE

echo ""
echo "=========================================="
echo "✅ Настройка завершена!"
echo "=========================================="
echo ""
echo "Для проверки подключения выполните:"
echo "  heroku run python scripts/test_r2_connection.py"
echo ""
echo "Или протестируйте через API:"
echo "  curl -X POST https://your-app.herokuapp.com/bot/receipts?telegram_id=YOUR_ID -F \"file=@test.jpg\""
echo ""

