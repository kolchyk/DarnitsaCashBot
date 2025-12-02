# Применение миграции базы данных

## Быстрый способ (через Heroku Dashboard)

1. Откройте https://dashboard.heroku.com/apps/darnitsacashbot-b132719cee1f
2. Нажмите **"More"** (справа вверху) → **"Run console"**
3. Введите команду: `alembic upgrade head`
4. Нажмите **"Run"**

## Альтернативный способ (через Heroku CLI)

### Установка Heroku CLI

1. Скачайте установщик: https://devcenter.heroku.com/articles/heroku-cli
2. Установите Heroku CLI
3. Перезапустите терминал

### Применение миграции

```bash
# Войдите в Heroku
heroku login

# Примените миграцию
heroku run alembic upgrade head --app darnitsacashbot-b132719cee1f

# Проверьте текущую версию миграции
heroku run alembic current --app darnitsacashbot-b132719cee1f
```

Должна отображаться версия: `20251202_00`

## Автоматическое применение

Если у вас настроен автоматический деплой из GitHub, миграция применится автоматически при следующем деплое через `release: alembic upgrade head` в Procfile.

## Проверка после применения

После применения миграции проверьте логи приложения:

```bash
heroku logs --tail --app darnitsacashbot-b132719cee1f
```

Убедитесь, что нет ошибок типа "value out of int32 range".

