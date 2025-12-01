# Настройка авторизации Portmone Direct API

## Обзор

API Portmone Direct использует REST-технологию с передачей данных через HTTPS (TLS 1.2). Все запросы выполняются методом POST, параметры передаются в теле запроса (не в URL).

## Необходимые данные для авторизации

Для работы с API Portmone Direct необходимо получить от менеджера Portmone следующие данные:

### 1. Обязательные параметры

| Параметр | Описание | Переменная окружения | Пример |
|----------|----------|---------------------|--------|
| **Login** | Логин компании-реселера | `PORTMONE_LOGIN` | `your_login` |
| **Password** | Пароль компании-реселера | `PORTMONE_PASSWORD` | `your_password` |
| **Version** | Версия протокола (рекомендуется "2") | `PORTMONE_VERSION` | `2` |

### 2. Дополнительные параметры

| Параметр | Описание | Переменная окружения | По умолчанию |
|----------|----------|---------------------|--------------|
| **API Base URL** | Базовый URL API | `PORTMONE_API_BASE` | `https://direct.portmone.com.ua/api/directcash/` |
| **TLS Certificate** | Путь к TLS сертификату (если требуется) | `PORTMONE_CERT_PATH` | `None` |
| **Language** | Язык локализации (uk/ru/en) | `PORTMONE_LANG` | `None` (по умолчанию: uk) |
| **Payee ID** | ID получателя платежа | `PORTMONE_PAYEE_ID` | `100000` |
| **Default Currency** | Валюта по умолчанию | `PORTMONE_DEFAULT_CURRENCY` | `UAH` |
| **Webhook Token** | Токен для вебхуков | `PORTMONE_WEBHOOK_TOKEN` | `None` |

## Формат запросов

### Структура запроса

Все запросы отправляются методом POST на URL: `https://direct.portmone.com.ua/api/directcash/`

Параметры передаются в теле POST запроса в формате `application/x-www-form-urlencoded`:

```
method=bills.create&login=your_login&password=your_password&version=2&payeeId=value&contractNumber=value
```

### Пример успешного ответа

```xml
<?xml version="1.0" encoding="utf-8"?>
<rsp status="ok">
    <bill>
        <billId>12345</billId>
        <contractNumber>67890</contractNumber>
    </bill>
</rsp>
```

### Пример ответа с ошибкой (версия протокола 2)

```xml
<?xml version="1.0" encoding="utf-8"?>
<rsp status="fail">
    <error code="Код помилки">Опис помилки</error>
    <error_description>Докладний опис помилки</error_description>
</rsp>
```

## Настройка переменных окружения

### Локальная разработка (.env файл)

Создайте файл `.env` в корне проекта:

```bash
# Portmone API настройки
PORTMONE_LOGIN=your_login_here
PORTMONE_PASSWORD=your_password_here
PORTMONE_VERSION=2
PORTMONE_API_BASE=https://direct.portmone.com.ua/api/directcash/
PORTMONE_LANG=uk
PORTMONE_PAYEE_ID=your_payee_id
PORTMONE_DEFAULT_CURRENCY=UAH

# TLS сертификат (если требуется)
PORTMONE_CERT_PATH=/path/to/certificate.pem

# Webhook токен (для получения уведомлений)
PORTMONE_WEBHOOK_TOKEN=your_webhook_token
```

### Heroku

```bash
heroku config:set PORTMONE_LOGIN=your_login
heroku config:set PORTMONE_PASSWORD=your_password
heroku config:set PORTMONE_VERSION=2
heroku config:set PORTMONE_PAYEE_ID=your_payee_id
heroku config:set PORTMONE_WEBHOOK_TOKEN=your_webhook_token
```

## Проверка подключения

Используйте скрипт для проверки подключения:

```bash
python scripts/check_portmone_api.py
```

Скрипт проверит:
- Наличие обязательных переменных окружения
- Подключение к API
- Корректность учетных данных
- Формат ответов

## Использование в коде

### Базовое использование

```python
from libs.common.config import get_settings
from libs.common.portmone import PortmoneDirectClient

settings = get_settings()
client = PortmoneDirectClient(settings)

try:
    # Вызов API метода
    response = await client.call(
        "bills.create",
        payeeId="123",
        contractNumber="456",
        amount="1.00",
        currency="UAH"
    )
    
    print(f"Bill ID: {response.bill_id}")
    
except PortmoneResponseError as e:
    print(f"Ошибка API: {e.response.errors}")
finally:
    await client.aclose()
```

### Использование контекстного менеджера

```python
async with PortmoneDirectClient() as client:
    response = await client.call("payers.getPayersList")
    # клиент автоматически закроется
```

## Версии протокола

### Версия 1 (по умолчанию, если не указана)

- Базовая функциональность
- Простые сообщения об ошибках

### Версия 2 (рекомендуется)

- Расширенные сообщения об ошибках (`error_description`)
- Локализация ответов (параметр `lang`)
- Дополнительные поля в ответах

Для использования версии 2 установите:

```bash
PORTMONE_VERSION=2
```

## Локализация

Параметр `lang` доступен только в версии протокола 2 и выше:

- `uk` - украинский (по умолчанию)
- `ru` - русский
- `en` - английский

Пример:

```bash
PORTMONE_LANG=ru
```

## TLS сертификаты

Если Portmone требует клиентский TLS сертификат:

1. Получите сертификат от менеджера Portmone
2. Конвертируйте в формат PEM (если необходимо):
   ```bash
   openssl pkcs12 -in certificate.pfx -out certificate.pem -nodes
   ```
3. Укажите путь к сертификату:
   ```bash
   PORTMONE_CERT_PATH=/path/to/certificate.pem
   ```

## Тестирование

### Mock-сервер для локального тестирования

Запустите mock-сервер:

```bash
docker compose up portmone-mock
```

Установите переменную окружения для использования mock:

```bash
PORTMONE_API_BASE=http://localhost:8082/api/directcash/
```

### Тесты

Запустите тесты клиента:

```bash
pytest tests/test_portmone_client.py -v
```

## Безопасность

⚠️ **ВАЖНО:**

1. **Никогда не коммитьте** реальные учетные данные в репозиторий
2. Используйте переменные окружения или секреты для хранения паролей
3. Ограничьте доступ к `.env` файлам (добавьте в `.gitignore`)
4. Используйте разные учетные данные для тестовой и продакшн сред
5. Регулярно обновляйте пароли и сертификаты

## Коды ошибок

Основные коды ошибок авторизации:

- **Неверный логин/пароль** - проверьте `PORTMONE_LOGIN` и `PORTMONE_PASSWORD`
- **TLS ошибки** - проверьте `PORTMONE_CERT_PATH` и формат сертификата
- **Неверная версия протокола** - убедитесь, что `PORTMONE_VERSION` установлен правильно
- **Доступ запрещен** - обратитесь к менеджеру Portmone для проверки прав доступа

Полный список кодов ошибок см. в [документации Portmone](https://docs.portmone.com.ua/docs/uk/PortmoneDirectUa/).

## Поддержка

При возникновении проблем:

1. Проверьте логи приложения
2. Запустите скрипт проверки: `python scripts/check_portmone_api.py`
3. Обратитесь к менеджеру Portmone для проверки учетных данных
4. Проверьте документацию: https://docs.portmone.com.ua/docs/uk/PortmoneDirectUa/

