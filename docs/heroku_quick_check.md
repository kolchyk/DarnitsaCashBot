# Быстрая проверка Heroku после включения процессов

## ✅ Что вы сделали:
- Включили `web` процесс (API Gateway)
- Включили `worker` процесс (Telegram Bot)

## 🔍 Проверка работоспособности:

### 1. Проверьте статус процессов:

```bash
heroku ps
```

Должны быть активны оба процесса:
- `web.1` - должен быть `up` (запущен)
- `worker.1` - должен быть `up` (запущен)

### 2. Проверьте API Gateway:

```bash
curl https://darnitsacashbot-b132719cee1f.herokuapp.com/healthz
```

Должно вернуть: `{"status":"ok"}`

Если не работает, проверьте логи:
```bash
heroku logs --tail --ps web
```

### 3. Проверьте логи Telegram бота:

```bash
heroku logs --tail --ps worker
```

Ищите:
- `Starting bot with token: ...` - бот запустился
- `API Gateway URL: https://darnitsacashbot-b132719cee1f.herokuapp.com` - правильный URL
- `Bot is starting polling...` - бот начал слушать сообщения
- Нет ошибок подключения

### 4. Проверьте переменные окружения:

```bash
# Проверка обязательных переменных
heroku config:get API_GATEWAY_URL
heroku config:get ENCRYPTION_SECRET
heroku config:get TELEGRAM_BOT_TOKEN
```

**Обязательные переменные:**
- `API_GATEWAY_URL` - должно быть: `https://darnitsacashbot-b132719cee1f.herokuapp.com`
- `ENCRYPTION_SECRET` - должен быть установлен (любая строка, рекомендуется использовать безопасный случайный ключ)
- `TELEGRAM_BOT_TOKEN` - токен вашего Telegram бота

**Если не установлены:**
```bash
heroku config:set API_GATEWAY_URL=https://darnitsacashbot-b132719cee1f.herokuapp.com
heroku config:set ENCRYPTION_SECRET=your-secret-key-here
heroku config:set TELEGRAM_BOT_TOKEN=your-bot-token
```

### 5. Протестируйте бота:

Отправьте команду `/start` вашему боту в Telegram. Бот должен ответить.

Если не отвечает, проверьте логи worker:
```bash
heroku logs --tail --ps worker
```

## 🐛 Типичные проблемы:

### Проблема: Web процесс падает с ошибкой "ENCRYPTION_SECRET Field required"

**Симптомы:**
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for AppSettings
ENCRYPTION_SECRET
  Field required
```

**Решение:**
1. Установите переменную окружения `ENCRYPTION_SECRET`:
   ```bash
   heroku config:set ENCRYPTION_SECRET=your-secret-key-here
   ```
   Или через Dashboard: Settings → Config Vars → Add `ENCRYPTION_SECRET`

2. Сгенерируйте безопасный секрет (опционально):
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. После установки переменной процессы автоматически перезапустятся

### Проблема: Web процесс падает

**Решение:**
1. Проверьте логи: `heroku logs --tail --ps web`
2. Убедитесь, что база данных создана: `heroku addons`
3. Выполните миграции: `heroku run alembic upgrade head`
4. Убедитесь, что `ENCRYPTION_SECRET` установлен: `heroku config:get ENCRYPTION_SECRET`

### Проблема: Worker процесс падает

**Решение:**
1. Проверьте логи: `heroku logs --tail --ps worker`
2. Убедитесь, что `TELEGRAM_BOT_TOKEN` установлен: `heroku config:get TELEGRAM_BOT_TOKEN`
3. Убедитесь, что `API_GATEWAY_URL` установлен правильно
4. Убедитесь, что `ENCRYPTION_SECRET` установлен: `heroku config:get ENCRYPTION_SECRET`

### Проблема: Бот не отвечает

**Решение:**
1. Проверьте, что web процесс доступен: `curl https://darnitsacashbot-b132719cee1f.herokuapp.com/healthz`
2. Проверьте логи worker на ошибки подключения к API Gateway
3. Убедитесь, что `API_GATEWAY_URL` установлен правильно

## 📊 Мониторинг:

### Просмотр всех логов в реальном времени:

```bash
heroku logs --tail
```

### Просмотр логов конкретного процесса:

```bash
# Логи API Gateway
heroku logs --tail --ps web

# Логи Telegram бота
heroku logs --tail --ps worker
```

### Поиск ошибок:

```bash
heroku logs --tail | grep -i error
```

## 🔄 Перезапуск процессов:

Если что-то не работает, перезапустите:

```bash
# Перезапустить все процессы
heroku restart

# Или только конкретный процесс
heroku restart web
heroku restart worker
```

