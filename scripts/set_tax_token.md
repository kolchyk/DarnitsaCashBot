# Установка токена TAX_GOV_UA_API_TOKEN в Heroku

## Способ 1: Через Heroku CLI (рекомендуется)

Если у вас установлен Heroku CLI и вы авторизованы:

```bash
heroku config:set TAX_GOV_UA_API_TOKEN=f38dae70-5fe6-4e0a-a9c6-170713b7d79d --app <your-app-name>
```

Или если приложение уже связано с git репозиторием:

```bash
heroku config:set TAX_GOV_UA_API_TOKEN=f38dae70-5fe6-4e0a-a9c6-170713b7d79d
```

## Способ 2: Через веб-интерфейс Heroku

1. Откройте https://dashboard.heroku.com/apps
2. Выберите ваше приложение
3. Перейдите в раздел **Settings**
4. Нажмите **Reveal Config Vars**
5. Добавьте новую переменную:
   - **KEY**: `TAX_GOV_UA_API_TOKEN`
   - **VALUE**: `f38dae70-5fe6-4e0a-a9c6-170713b7d79d`
6. Нажмите **Add**

## Способ 3: Через скрипт (если настроен Heroku API токен)

```bash
# Установите Heroku API токен (если еще не установлен)
set HEROKU_API_TOKEN=your_heroku_api_token  # Windows
export HEROKU_API_TOKEN=your_heroku_api_token  # Linux/Mac

# Установите имя приложения (если отличается)
set HEROKU_APP_NAME=your-app-name  # Windows
export HEROKU_APP_NAME=your-app-name  # Linux/Mac

# Запустите скрипт
python scripts/set_heroku_config.py TAX_GOV_UA_API_TOKEN f38dae70-5fe6-4e0a-a9c6-170713b7d79d
```

## Проверка установки

После установки проверьте, что переменная установлена:

```bash
heroku config:get TAX_GOV_UA_API_TOKEN --app <your-app-name>
```

Или через веб-интерфейс в разделе Settings → Config Vars.

## Важно

После установки переменной окружения необходимо перезапустить приложение:

```bash
heroku restart --app <your-app-name>
```

Или перезапустите через веб-интерфейс: Settings → Restart all dynos.

