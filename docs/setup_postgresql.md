# Установка PostgreSQL на Heroku

## Проблема
Приложение получает ошибку `ConnectionRefusedError: [Errno 111] Connection refused` при попытке подключиться к базе данных PostgreSQL.

## Решение

### Вариант 1: Через Heroku CLI

Если у вас установлен Heroku CLI, выполните:

```bash
# Установите PostgreSQL аддон (бесплатный план mini)
heroku addons:create heroku-postgresql:mini --app darnitsacashbot-b132719cee1f

# Проверьте, что аддон установлен
heroku addons --app darnitsacashbot-b132719cee1f

# Проверьте, что DATABASE_URL установлен
heroku config:get DATABASE_URL --app darnitsacashbot-b132719cee1f
```

### Вариант 2: Через веб-интерфейс Heroku

1. Откройте [Heroku Dashboard](https://dashboard.heroku.com/apps/darnitsacashbot-b132719cee1f)
2. Перейдите на вкладку **Resources**
3. В разделе **Add-ons** найдите **Heroku Postgres**
4. Нажмите **Find more add-ons** или введите "postgres" в поиске
5. Выберите **Heroku Postgres**
6. Выберите план **Mini** (бесплатный) или **Hobby Dev** (бесплатный)
7. Нажмите **Provision**

### После установки PostgreSQL

1. **Проверьте переменную DATABASE_URL:**
   ```bash
   heroku config:get DATABASE_URL --app darnitsacashbot-b132719cee1f
   ```
   Должна быть установлена автоматически.

2. **Выполните миграции базы данных:**
   ```bash
   heroku run alembic upgrade head --app darnitsacashbot-b132719cee1f
   ```

3. **Перезапустите приложение:**
   ```bash
   heroku restart --app darnitsacashbot-b132719cee1f
   ```

4. **Проверьте логи:**
   ```bash
   heroku logs --tail --app darnitsacashbot-b132719cee1f
   ```

## Дополнительные аддоны

Если вам также нужны другие сервисы:

### Redis
```bash
heroku addons:create heroku-redis:mini --app darnitsacashbot-b132719cee1f
```


## Проверка подключения

После установки PostgreSQL и выполнения миграций, проверьте работу приложения:

```bash
# Проверьте health endpoint
curl https://darnitsacashbot-b132719cee1f.herokuapp.com/healthz

# Проверьте логи на наличие ошибок подключения
heroku logs --tail --app darnitsacashbot-b132719cee1f | grep -i "database\|postgres\|connection"
```

## Примечания

- План **mini** предоставляет до 10,000 строк в базе данных (бесплатно)
- План **hobby-dev** предоставляет до 10,000 строк и автоматические резервные копии (бесплатно)
- Переменная `DATABASE_URL` устанавливается автоматически при добавлении аддона
- SSL подключение настроено автоматически в коде приложения

