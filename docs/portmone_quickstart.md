# Быстрый старт: Настройка Portmone API

## Шаг 1: Получение учетных данных

Получите от менеджера Portmone следующие данные:
- **LOGIN** - логин компании-реселера
- **PASSWORD** - пароль компании-реселера
- **PAYEE_ID** - ID получателя платежа (опционально)
- **TLS сертификат** - если требуется (опционально)

## Шаг 2: Настройка переменных окружения

Скопируйте `env.example` в `.env` и заполните необходимые переменные:

```bash
cp env.example .env
```

Откройте `.env` и установите:

```bash
PORTMONE_LOGIN=ваш_логин
PORTMONE_PASSWORD=ваш_пароль
PORTMONE_VERSION=2
PORTMONE_API_BASE=https://direct.portmone.com.ua/api/directcash/
```

Если требуется TLS сертификат:

```bash
PORTMONE_CERT_PATH=/путь/к/сертификату.pem
```

## Шаг 3: Проверка подключения

Запустите скрипт проверки:

```bash
python scripts/check_portmone_api.py
```

Скрипт проверит:
- ✅ Наличие обязательных переменных окружения
- ✅ Подключение к API Portmone
- ✅ Корректность учетных данных
- ✅ Формат ответов API

## Шаг 4: Локальное тестирование (опционально)

Для тестирования без реального API используйте mock-сервер:

```bash
docker compose up portmone-mock
```

В `.env` установите:

```bash
PORTMONE_API_BASE=http://localhost:8082/api/directcash/
```

## Что дальше?

- Подробная документация: [docs/portmone_auth.md](portmone_auth.md)
- Интеграция с бонусным сервисом: [docs/easy.md](easy.md)
- Официальная документация Portmone: https://docs.portmone.com.ua/docs/uk/PortmoneDirectUa/

## Устранение проблем

### Ошибка авторизации

1. Проверьте правильность `PORTMONE_LOGIN` и `PORTMONE_PASSWORD`
2. Убедитесь, что учетные данные получены от менеджера Portmone
3. Проверьте версию протокола: `PORTMONE_VERSION=2`

### TLS ошибки

1. Проверьте путь к сертификату: `PORTMONE_CERT_PATH`
2. Убедитесь, что сертификат в формате PEM
3. Проверьте права доступа к файлу сертификата

### Проблемы с подключением

1. Проверьте доступность API: `curl https://direct.portmone.com.ua/api/directcash/`
2. Проверьте настройки файрвола/прокси
3. Убедитесь, что используется TLS 1.2

## Поддержка

При возникновении проблем:
1. Запустите скрипт проверки: `python scripts/check_portmone_api.py`
2. Проверьте логи приложения
3. Обратитесь к менеджеру Portmone для проверки учетных данных

