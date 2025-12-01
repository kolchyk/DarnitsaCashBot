# Диагностика проблем на Heroku

## Бот не отвечает на команду /start

### Шаг 1: Проверьте, что оба процесса запущены

```bash
heroku ps
```

Должны быть активны оба процесса:
- `web.1` - API Gateway
- `worker.1` - Telegram Bot

Если какой-то процесс не запущен:

```bash
# Запустить web процесс
heroku ps:scale web=1

# Запустить worker процесс
heroku ps:scale worker=1
```

### Шаг 2: Проверьте переменные окружения

```bash
# Проверьте все переменные
heroku config

# Или конкретные переменные
heroku config:get TELEGRAM_BOT_TOKEN
heroku config:get API_GATEWAY_URL
heroku config:get ENCRYPTION_SECRET
```

**Критически важно:**
- `TELEGRAM_BOT_TOKEN` должен быть установлен
- `API_GATEWAY_URL` должен указывать на ваш Heroku app: `https://your-app-name.herokuapp.com`
- `ENCRYPTION_SECRET` должен быть установлен (32 байта)

### Шаг 3: Проверьте логи worker процесса

```bash
# Все логи worker
heroku logs --tail --ps worker

# Последние 100 строк
heroku logs -n 100 --ps worker

# Поиск ошибок
heroku logs --tail --ps worker | grep -i error
```

**Что искать в логах:**
- `Starting bot with token: ...` - бот запустился
- `API Gateway URL: ...` - правильный URL
- `Bot is starting polling...` - бот начал слушать сообщения
- Ошибки подключения к API Gateway
- Ошибки подключения к базе данных

### Шаг 4: Проверьте логи web процесса (API Gateway)

```bash
heroku logs --tail --ps web
```

**Что искать:**
- API Gateway должен отвечать на запросы
- Ошибки подключения к базе данных
- Ошибки при обработке запросов `/bot/users`

### Шаг 5: Проверьте доступность API Gateway

```bash
# Проверьте health endpoint
curl https://your-app-name.herokuapp.com/healthz

# Должен вернуть 200 OK
```

Если API Gateway недоступен, проверьте:
1. Запущен ли web процесс: `heroku ps:scale web=1`
2. Правильно ли настроен PORT (Heroku устанавливает его автоматически)
3. Нет ли ошибок в логах web процесса

### Шаг 6: Проверьте подключение к базе данных

```bash
# Проверьте наличие аддона PostgreSQL
heroku addons

# Должен быть heroku-postgresql
```

Если базы данных нет:
```bash
heroku addons:create heroku-postgresql:mini
heroku run alembic upgrade head
```

### Шаг 7: Проверьте токен бота

```bash
# Получите токен
heroku config:get TELEGRAM_BOT_TOKEN

# Проверьте бота через Telegram API (замените YOUR_TOKEN)
curl https://api.telegram.org/botYOUR_TOKEN/getMe
```

Должен вернуться JSON с информацией о боте.

### Шаг 8: Перезапустите процессы

Если ничего не помогает, перезапустите процессы:

```bash
# Перезапустить все процессы
heroku restart

# Или только worker
heroku restart worker
```

## Типичные проблемы и решения

### Проблема: Worker процесс падает сразу после запуска

**Причина:** Отсутствуют обязательные переменные окружения или ошибка в коде.

**Решение:**
1. Проверьте логи: `heroku logs --tail --ps worker`
2. Убедитесь, что все обязательные переменные установлены
3. Проверьте синтаксис кода

### Проблема: Бот запускается, но не отвечает

**Причина:** API Gateway недоступен или неправильно настроен `API_GATEWAY_URL`.

**Решение:**
1. Проверьте, что web процесс запущен: `heroku ps`
2. Проверьте `API_GATEWAY_URL`: должен быть `https://your-app-name.herokuapp.com`
3. Проверьте логи worker на ошибки подключения

### Проблема: Ошибка "API Gateway недоступен"

**Причина:** Web процесс не запущен или недоступен.

**Решение:**
1. Запустите web процесс: `heroku ps:scale web=1`
2. Подождите 1-2 минуты для полного запуска
3. Проверьте доступность: `curl https://your-app-name.herokuapp.com/healthz`

### Проблема: Ошибка подключения к базе данных

**Причина:** База данных не создана или неправильно настроена.

**Решение:**
1. Создайте базу данных: `heroku addons:create heroku-postgresql:mini`
2. Выполните миграции: `heroku run alembic upgrade head`
3. Проверьте `DATABASE_URL`: `heroku config:get DATABASE_URL`

## Чеклист для нового деплоя

- [ ] Создано Heroku приложение
- [ ] Добавлены аддоны (PostgreSQL, Redis, CloudAMQP)
- [ ] Установлены все переменные окружения
- [ ] `API_GATEWAY_URL` указывает на правильный URL приложения
- [ ] Выполнены миграции базы данных
- [ ] Запущены оба процесса (web и worker)
- [ ] Проверена доступность API Gateway через `/healthz`
- [ ] Проверены логи на наличие ошибок

## Полезные команды

```bash
# Просмотр всех переменных окружения
heroku config

# Установка переменной
heroku config:set KEY=value

# Просмотр логов в реальном времени
heroku logs --tail

# Просмотр логов конкретного процесса
heroku logs --tail --ps worker
heroku logs --tail --ps web

# Перезапуск всех процессов
heroku restart

# Перезапуск конкретного процесса
heroku restart worker
heroku restart web

# Масштабирование процессов
heroku ps:scale web=1 worker=1

# Проверка статуса процессов
heroku ps

# Выполнение команды в контексте приложения
heroku run python -c "from libs.common import get_settings; print(get_settings().api_gateway_url)"
```

