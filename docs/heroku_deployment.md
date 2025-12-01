# Деплой на Heroku

Этот документ описывает процесс деплоя проекта DarnitsaCashBot на Heroku.

## Предварительные требования

1. Учетная запись Heroku
2. Heroku CLI установлен локально
3. Git репозиторий проекта

## Настройка Heroku приложения

### 1. Создание приложения

```bash
heroku create your-app-name
```

### 2. Настройка Buildpacks

Проект требует два buildpack'а:

1. **Python buildpack** (автоматически определяется Heroku)
2. **Apt buildpack** (для установки системных пакетов: Tesseract OCR и библиотеки)

Настройте buildpacks в правильном порядке:

```bash
# Добавьте Apt buildpack первым (он должен быть установлен до Python buildpack)
heroku buildpacks:add --index 1 heroku-community/apt

# Python buildpack будет автоматически добавлен вторым
# Если нужно добавить явно:
heroku buildpacks:add --index 2 heroku/python
```

**Проверка установленных buildpacks:**
```bash
heroku buildpacks
```

Должны быть установлены в следующем порядке:
1. `heroku-community/apt`
2. `heroku/python`

**Важно:** Файл `Aptfile` уже содержит необходимые системные пакеты:
- `tesseract-ocr` - движок OCR
- `tesseract-ocr-ukr` - языковой пакет для украинского языка
- `tesseract-ocr-rus` - языковой пакет для русского языка
- `tesseract-ocr-eng` - языковой пакет для английского языка
- `libglib2.0-0` - библиотеки для OpenCV
- `libgl1` - библиотеки для OpenCV

### 3. Добавление аддонов

#### База данных PostgreSQL
```bash
heroku addons:create heroku-postgresql:mini
```

#### Redis
```bash
heroku addons:create heroku-redis:mini
```

#### Хранилище (S3-совместимое)
Для хранения файлов чеков можно использовать:
- AWS S3 (рекомендуется)
- MinIO (для разработки)

### 4. Настройка переменных окружения

Установите необходимые переменные окружения:

```bash
# Обязательные переменные
heroku config:set TELEGRAM_BOT_TOKEN=your_bot_token
heroku config:set ENCRYPTION_SECRET=your_32_byte_secret

# Telegram настройки
heroku config:set TELEGRAM_ADMIN_IDS=123456789,987654321
heroku config:set TELEGRAM_WEBHOOK_URL=https://your-app-name.herokuapp.com/webhook
# URL API Gateway (используется ботом для подключения к API)
heroku config:set API_GATEWAY_URL=https://your-app-name.herokuapp.com

# Хранилище (S3)
heroku config:set STORAGE_ENDPOINT=https://s3.amazonaws.com
heroku config:set STORAGE_BUCKET=your-bucket-name
heroku config:set STORAGE_ACCESS_KEY=your-access-key
heroku config:set STORAGE_SECRET_KEY=your-secret-key

# Portmone настройки
heroku config:set PORTMONE_LOGIN=your_login
heroku config:set PORTMONE_PASSWORD=your_password
heroku config:set PORTMONE_PAYEE_ID=your_payee_id
heroku config:set PORTMONE_WEBHOOK_TOKEN=your_webhook_token

# Окружение
heroku config:set APP_ENV=prod
heroku config:set LOG_LEVEL=INFO
```

**Примечание:** `DATABASE_URL` и `REDIS_URL` автоматически устанавливаются Heroku при добавлении соответствующих аддонов.

### 5. Миграции базы данных

1. **Единоразовое обновление существующей базы.** Перед повторным деплоем выполните миграции вручную, чтобы привести продакшн-базу к актуальному состоянию:

   ```bash
   heroku run alembic upgrade head
   ```

   Если предпочитаете явный вызов интерпретатора:

   ```bash
   heroku run python -m alembic upgrade head
   ```

2. **Автоматический запуск при каждом деплое.** В `Procfile` добавлена release-команда:

   ```
   release: alembic upgrade head
   ```

   Heroku выполняет этот шаг перед запуском новых dyno, поэтому все последующие деплои будут автоматически применять накопленные миграции. Проверяйте логи release-процесса при ошибках (`heroku logs --tail --dyno release`).

## Деплой

### Первый деплой

```bash
git push heroku main
```

### Последующие деплои

```bash
git push heroku main
```

## Масштабирование процессов

### Запуск веб-сервера (API Gateway)

```bash
heroku ps:scale web=1
```

### Запуск Telegram бота (worker)

```bash
heroku ps:scale worker=1
```

### Мониторинг процессов

```bash
heroku ps
```

### Просмотр логов

**Все логи (web + worker):**
```bash
heroku logs --tail
```

**Только логи Telegram бота (worker):**
```bash
heroku logs --tail --ps worker
```

**Только логи API Gateway (web):**
```bash
heroku logs --tail --ps web
```

**Последние N строк:**
```bash
heroku logs --tail -n 100
```

**Поиск ошибок в логах:**
```bash
heroku logs --tail | grep -i error
```

## Структура процессов

Проект использует три процесса в `Procfile`:

- **web**: API Gateway (FastAPI) - обрабатывает HTTP запросы
- **worker**: Telegram Bot - обрабатывает сообщения от пользователей
- **release**: выполняет `alembic upgrade head` перед запуском dyno, чтобы гарантировать актуальную схему базы данных

## Дополнительные воркеры

Если необходимо запустить дополнительные воркеры (OCR, bonus service, rules engine), можно добавить их в Procfile:

```
web: python -m apps.api_gateway.main
worker: python -m apps.telegram_bot.main
ocr-worker: python -m services.ocr_worker.worker
bonus-worker: python -m services.bonus_service.main
rules-worker: python -m services.rules_engine.service
```

И затем масштабировать:

```bash
heroku ps:scale ocr-worker=1 bonus-worker=1 rules-worker=1
```

## Проверка работоспособности

После деплоя проверьте:

1. **Health check endpoint:**
   ```bash
   curl https://your-app-name.herokuapp.com/healthz
   ```

2. **Метрики:**
   ```bash
   curl https://your-app-name.herokuapp.com/metrics
   ```

## Troubleshooting

### Проблемы с подключением к базе данных

Убедитесь, что аддон PostgreSQL добавлен:
```bash
heroku addons
```

Проверьте DATABASE_URL:
```bash
heroku config:get DATABASE_URL
```

### Проблемы с Redis

Проверьте REDIS_URL:
```bash
heroku config:get REDIS_URL
```

### Просмотр детальных логов

```bash
heroku logs --tail --source app
```

### Проверка работы Telegram бота

**1. Убедитесь, что worker запущен:**
```bash
heroku ps
```
Должен быть активен процесс `worker.1`.

**2. Если worker не запущен:**
```bash
heroku ps:scale worker=1
```

**3. Проверьте логи бота при отправке команды /start:**
```bash
heroku logs --tail --ps worker
```
Отправьте команду `/start` боту и проверьте логи на наличие ошибок.

**4. Проверьте переменные окружения бота:**
```bash
heroku config:get TELEGRAM_BOT_TOKEN
heroku config:get API_GATEWAY_URL
```

**5. Перезапустите worker при необходимости:**
```bash
heroku ps:restart worker
```

### Запуск консоли

```bash
heroku run python
```

## Оптимизация

### Уменьшение размера slug

Файл `.slugignore` уже настроен для исключения ненужных файлов из деплоя.

### Настройка dyno типов

Для продакшена рекомендуется использовать:
- Standard-1X или Standard-2X для web процесса
- Standard-1X для worker процессов

```bash
heroku ps:resize web=standard-1x worker=standard-1x
```

## Безопасность

1. **Никогда не коммитьте секреты** в репозиторий
2. Используйте **Config Vars** в Heroku для всех секретов
3. Включите **Two-Factor Authentication** для Heroku аккаунта
4. Регулярно обновляйте зависимости

## Мониторинг

Heroku предоставляет встроенный мониторинг через:
- Heroku Metrics
- Logplex для логов
- Add-ons для расширенного мониторинга (New Relic, DataDog и т.д.)

Проект также экспортирует метрики Prometheus на `/metrics` endpoint.

