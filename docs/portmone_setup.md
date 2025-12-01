# Полное руководство по настройке Portmone Direct API для пополнения мобильного телефона

## Содержание

1. [Обзор](#обзор)
2. [Быстрый старт](#быстрый-старт)
3. [Авторизация и учетные данные](#авторизация-и-учетные-данные)
4. [Настройка переменных окружения](#настройка-переменных-окружения)
5. [Метод bills.create для пополнения телефона](#метод-billscreate-для-пополнения-телефона)
6. [Использование в коде](#использование-в-коде)
7. [Тестирование](#тестирование)
8. [Устранение проблем](#устранение-проблем)
9. [Безопасность](#безопасность)
10. [Дополнительные ресурсы](#дополнительные-ресурсы)

---

## Обзор

Portmone Direct API — это REST API для создания счетов и пополнения баланса мобильных телефонов. API использует HTTPS (TLS 1.2) для безопасной передачи данных. Все запросы выполняются методом POST, параметры передаются в теле запроса в формате `application/x-www-form-urlencoded`.

### Основные характеристики

- **Базовый URL**: `https://direct.portmone.com.ua/api/directcash/`
- **Протокол**: REST over HTTPS (TLS 1.2)
- **Формат запросов**: POST с параметрами в теле запроса
- **Формат ответов**: XML (UTF-8)
- **Версия протокола**: Рекомендуется версия 2

### Основной метод для пополнения телефона

Для пополнения мобильного телефона используется метод **`bills.create`**, который создает счет на пополнение баланса. После создания счета необходимо выполнить оплату через метод `bills.pay` (в текущей реализации используется только `bills.create`).

---

## Быстрый старт

### Шаг 1: Получение учетных данных

Получите от менеджера Portmone следующие данные:

- **LOGIN** — логин компании-реселера
- **PASSWORD** — пароль компании-реселера
- **PAYEE_ID** — ID оператора мобильной связи (для каждого оператора свой)
- **TLS сертификат** — если требуется (опционально)

### Шаг 2: Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```bash
# Обязательные параметры авторизации
PORTMONE_LOGIN=your_login_here
PORTMONE_PASSWORD=your_password_here
PORTMONE_VERSION=2

# Обязательные для пополнения телефона
PORTMONE_PAYEE_ID=your_operator_payee_id
PORTMONE_DEFAULT_CURRENCY=UAH

# Опциональные параметры
PORTMONE_API_BASE=https://direct.portmone.com.ua/api/directcash/
PORTMONE_LANG=uk
PORTMONE_CERT_PATH=/path/to/certificate.pem
PORTMONE_WEBHOOK_TOKEN=your_webhook_token
```

### Шаг 3: Проверка подключения

Запустите скрипт проверки:

```bash
python scripts/check_portmone_api.py
```

Скрипт проверит:
- ✅ Наличие обязательных переменных окружения
- ✅ Подключение к API Portmone
- ✅ Корректность учетных данных
- ✅ Формат ответов API

---

## Авторизация и учетные данные

### Обязательные параметры авторизации

Каждый запрос к Portmone Direct API требует следующих обязательных параметров:

| Параметр | Описание | Переменная окружения | Пример |
|----------|----------|---------------------|--------|
| **Login** | Логин компании-реселера | `PORTMONE_LOGIN` | `your_login` |
| **Password** | Пароль компании-реселера | `PORTMONE_PASSWORD` | `your_password` |
| **Version** | Версия протокола (рекомендуется "2") | `PORTMONE_VERSION` | `2` |

### Дополнительные параметры

| Параметр | Описание | Переменная окружения | По умолчанию |
|----------|----------|---------------------|--------------|
| **API Base URL** | Базовый URL API | `PORTMONE_API_BASE` | `https://direct.portmone.com.ua/api/directcash/` |
| **TLS Certificate** | Путь к TLS сертификату (если требуется) | `PORTMONE_CERT_PATH` | `None` |
| **Language** | Язык локализации (uk/ru/en) | `PORTMONE_LANG` | `None` (по умолчанию: uk) |
| **Payee ID** | ID оператора мобильной связи | `PORTMONE_PAYEE_ID` | `100000` |
| **Default Currency** | Валюта по умолчанию | `PORTMONE_DEFAULT_CURRENCY` | `UAH` |
| **Webhook Token** | Токен для вебхуков | `PORTMONE_WEBHOOK_TOKEN` | `None` |

### Версии протокола

#### Версия 1 (по умолчанию, если не указана)

- Базовая функциональность
- Простые сообщения об ошибках

#### Версия 2 (рекомендуется)

- Расширенные сообщения об ошибках (`error_description`)
- Локализация ответов (параметр `lang`)
- Дополнительные поля в ответах

Для использования версии 2 установите:

```bash
PORTMONE_VERSION=2
```

### Локализация

Параметр `lang` доступен только в версии протокола 2 и выше:

- `uk` — украинский (по умолчанию)
- `ru` — русский
- `en` — английский

Пример:

```bash
PORTMONE_LANG=ru
```

---

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

### TLS сертификаты

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

---

## Метод bills.create для пополнения телефона

### Назначение

Метод `bills.create` создает счет на пополнение баланса мобильного телефона. После успешного создания счета возвращаются идентификаторы (`billId`, `payeeId`), которые используются для последующей обработки платежа.

### Обязательные параметры

| Параметр | Описание | Пример |
|----------|----------|--------|
| `method` | Метод API | `bills.create` |
| `login` | Логин компании-реселера | Из `PORTMONE_LOGIN` |
| `password` | Пароль компании-реселера | Из `PORTMONE_PASSWORD` |
| `version` | Версия протокола | `2` |
| `payeeId` | **ID оператора мобильной связи** в системе Portmone | `2065` (для Київстар) |
| `contractNumber` | **Номер телефона** (MSISDN) в формате `380XXXXXXXXX` | `380991234567` |
| `amount` | Сумма пополнения в формате `"XX.XX"` | `"1.00"` |
| `currency` | Валюта | `"UAH"` |

### Опциональные параметры

| Параметр | Описание | Пример |
|----------|----------|--------|
| `comment` | Комментарий к операции | `"Top-up for receipt 12345"` |
| `lang` | Язык локализации (uk/ru/en) | `"uk"` |

### Формат запроса

Все запросы отправляются методом POST на URL: `https://direct.portmone.com.ua/api/directcash/`

Параметры передаются в теле POST запроса в формате `application/x-www-form-urlencoded`:

```
method=bills.create&login=LOGIN&password=PASSWORD&version=2&payeeId=OPERATOR_ID&contractNumber=380991234567&amount=1.00&currency=UAH&comment=Top-up
```

### Пример успешного ответа

```xml
<?xml version="1.0" encoding="utf-8"?>
<rsp status="ok">
    <bill>
        <billId>12345</billId>
        <payee id="2065">Київстар</payee>
        <contractNumber>380991234567</contractNumber>
        <amount>1.00</amount>
        <currency>UAH</currency>
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

### Важные моменты

#### 1. PayeeId (ID оператора)

**КРИТИЧЕСКИ ВАЖНО**: `payeeId` — это **не ваш логин**, а **ID оператора мобильной связи** в системе Portmone.

Для каждого оператора нужен свой `payeeId`:
- Київстар (Kyivstar)
- Vodafone Україна
- lifecell

Эти ID нужно получить от менеджера Portmone.

**Рекомендация**: Определяйте оператора по номеру телефона и используйте соответствующий `payeeId`:

```python
def get_operator_payee_id(phone_number: str, settings: AppSettings) -> str:
    """Определяет payeeId оператора по номеру телефона."""
    # Київстар: 039, 067, 068, 096, 097, 098
    # Vodafone: 050, 066, 095, 099
    # lifecell: 063, 073, 093
    
    prefix = phone_number[3:5]  # Первые 2 цифры после 380
    
    if prefix in ['39', '67', '68', '96', '97', '98']:
        return settings.portmone_payee_id_kyivstar
    elif prefix in ['50', '66', '95', '99']:
        return settings.portmone_payee_id_vodafone
    elif prefix in ['63', '73', '93']:
        return settings.portmone_payee_id_lifecell
    else:
        return settings.portmone_payee_id  # По умолчанию
```

#### 2. ContractNumber (номер телефона)

Номер телефона должен быть в формате:
- **`380XXXXXXXXX`** (12 цифр, начинается с 380)
- Без пробелов, дефисов и других символов
- Пример: `380991234567`

В текущей реализации номер берется из `User.phone_number` после расшифровки.

#### 3. Amount (сумма)

Сумма передается в формате строки с двумя знаками после запятой:
- `"1.00"` для 1 гривны
- `"10.50"` для 10 гривен 50 копеек

В текущей реализации используется фиксированная сумма **1.00 UAH** (100 копеек = 1 гривна).

---

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
        payeeId="2065",  # ID оператора
        contractNumber="380991234567",  # Номер телефона
        amount="1.00",  # Сумма
        currency="UAH"  # Валюта
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
    response = await client.call(
        "bills.create",
        payeeId="2065",
        contractNumber="380991234567",
        amount="1.00",
        currency="UAH"
    )
    # клиент автоматически закроется
```

### Текущая реализация в проекте

Реализация находится в `services/bonus_service/main.py`:

```python
portmone_payload = {
    "payeeId": context.payee_id,           # ID оператора из настроек
    "contractNumber": context.contract_number,  # Номер телефона
    "amount": f"{context.amount / 100:.2f}",    # Сумма (1.00 UAH)
    "currency": context.currency,               # Валюта (UAH)
    "comment": f"Top-up for receipt {context.receipt_id}",
}

response = await client.call("bills.create", **portmone_payload)
```

### Обработка ошибок

Клиент PortmoneDirectClient предоставляет следующие исключения:

- `PortmoneTransportError` — ошибки транспорта (HTTP, TLS)
- `PortmoneResponseError` — ошибки API (статус "fail" в ответе)

Пример обработки:

```python
from libs.common.portmone import (
    PortmoneDirectClient,
    PortmoneResponseError,
    PortmoneTransportError,
)

try:
    response = await client.call("bills.create", **payload)
except PortmoneResponseError as exc:
    # Ошибка API
    error_code = exc.response.errors[0].code if exc.response.errors else None
    error_description = exc.response.errors[0].description if exc.response.errors else None
    print(f"API Error: {error_code} - {error_description}")
except PortmoneTransportError as exc:
    # Ошибка транспорта (можно повторить запрос)
    print(f"Transport Error: {exc}")
```

### Retry логика

Для обработки временных ошибок транспорта используйте retry логику:

```python
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

async for attempt in AsyncRetrying(
    retry=retry_if_exception_type(PortmoneTransportError),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    stop=stop_after_attempt(3),
):
    with attempt:
        response = await client.call("bills.create", **payload)
```

---

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

### Тестирование с реальным API

⚠️ **ВНИМАНИЕ**: Тестирование с реальным API создаст реальные счета!

Используйте тестовый номер телефона и минимальную сумму (1.00 UAH).

### Проверка настроек

#### Шаг 1: Проверьте учетные данные

```bash
python scripts/check_portmone_api.py
```

Убедитесь, что:
- ✅ `PORTMONE_LOGIN` установлен правильно
- ✅ `PORTMONE_PASSWORD` установлен правильно
- ✅ Подключение к API работает

#### Шаг 2: Получите PayeeId для операторов

**Обратитесь к менеджеру Portmone** и получите `payeeId` для каждого оператора:

- Київстар (Kyivstar)
- Vodafone Україна
- lifecell

Эти ID нужны для правильного пополнения телефонов разных операторов.

---

## Устранение проблем

### Ошибка: Неверный payeeId

**Симптом**: API возвращает ошибку о неверном payeeId.

**Решение**: 
1. Проверьте, что `PORTMONE_PAYEE_ID` содержит ID оператора, а не ваш логин
2. Убедитесь, что используете правильный ID для оператора номера телефона
3. Обратитесь к менеджеру Portmone для получения правильных ID

### Ошибка: Неверный формат номера телефона

**Симптом**: API возвращает ошибку о неверном contractNumber.

**Решение**:
1. Убедитесь, что номер в формате `380XXXXXXXXX` (12 цифр)
2. Проверьте, что номер не содержит пробелов или других символов
3. Убедитесь, что номер начинается с 380

### Ошибка: Неверная сумма

**Симптом**: API возвращает ошибку о неверной сумме.

**Решение**:
1. Убедитесь, что сумма в формате `"XX.XX"` (с точкой, два знака после запятой)
2. Проверьте минимальную сумму пополнения для оператора
3. Убедитесь, что сумма положительная

### Ошибка авторизации

**Симптом**: API возвращает ошибку авторизации.

**Решение**:
1. Проверьте правильность `PORTMONE_LOGIN` и `PORTMONE_PASSWORD`
2. Убедитесь, что учетные данные получены от менеджера Portmone
3. Проверьте версию протокола: `PORTMONE_VERSION=2`

### TLS ошибки

**Симптом**: Ошибки подключения или TLS handshake.

**Решение**:
1. Проверьте путь к сертификату: `PORTMONE_CERT_PATH`
2. Убедитесь, что сертификат в формате PEM
3. Проверьте права доступа к файлу сертификата
4. Убедитесь, что используется TLS 1.2

### Проблемы с подключением

**Симптом**: Не удается подключиться к API.

**Решение**:
1. Проверьте доступность API: `curl https://direct.portmone.com.ua/api/directcash/`
2. Проверьте настройки файрвола/прокси
3. Убедитесь, что используется TLS 1.2

### Основные коды ошибок

- **Неверный логин/пароль** — проверьте `PORTMONE_LOGIN` и `PORTMONE_PASSWORD`
- **TLS ошибки** — проверьте `PORTMONE_CERT_PATH` и формат сертификата
- **Неверная версия протокола** — убедитесь, что `PORTMONE_VERSION` установлен правильно
- **Доступ запрещен** — обратитесь к менеджеру Portmone для проверки прав доступа

Полный список кодов ошибок см. в [документации Portmone](https://docs.portmone.com.ua/docs/uk/PortmoneDirectUa/).

---

## Безопасность

⚠️ **ВАЖНО:**

1. **Никогда не коммитьте** реальные учетные данные в репозиторий
2. Используйте переменные окружения или секреты для хранения паролей
3. Ограничьте доступ к `.env` файлам (добавьте в `.gitignore`)
4. Используйте разные учетные данные для тестовой и продакшн сред
5. Регулярно обновляйте пароли и сертификаты

### Безопасное хранение учетных данных

- **Локальная разработка**: Используйте `.env` файл (добавлен в `.gitignore`)
- **Heroku**: Используйте `heroku config:set` для установки переменных окружения
- **Другие платформы**: Используйте секреты/конфигурацию платформы

### PCI DSS Compliance

Интеграция с PortmoneDirect через стандартный интерфейс не требует PCI DSS сертификации от вас, так как Portmone уже имеет PCI DSS сертификацию. Однако:

- Защищайте API учетные данные (login, password)
- Не храните данные карт в вашей системе
- Используйте HTTPS для всех запросов
- Регулярно обновляйте сертификаты

---

## Дополнительные ресурсы

### Официальная документация

- [Portmone Direct API Documentation](https://docs.portmone.com.ua/docs/uk/PortmoneDirectUa/)
- [Portmone Direct API (English)](https://docs.portmone.com.ua/docs/en/PortmoneDirectEng/)

### Внутренняя документация проекта

- [Telegram Flow](telegram_flow.md) — Опис потоку роботи з Telegram
- [PRD](prd.md) — Product Requirements Document

### Поддержка

При возникновении проблем:

1. Проверьте логи приложения
2. Запустите скрипт проверки: `python scripts/check_portmone_api.py`
3. Обратитесь к менеджеру Portmone для:
   - Получения правильных `payeeId` для операторов
   - Проверки учетных данных
   - Проверки прав доступа к API пополнения телефонов

### Контакты

- **Portmone Support**: Обратитесь к вашему менеджеру Portmone
- **Документация**: https://docs.portmone.com.ua/docs/uk/PortmoneDirectUa/

---

## Приложение: Примеры кода

### Полный пример создания счета на пополнение

```python
import asyncio
from libs.common.config import get_settings
from libs.common.portmone import (
    PortmoneDirectClient,
    PortmoneResponseError,
    PortmoneTransportError,
)

async def create_topup_bill(phone_number: str, amount: float, payee_id: str):
    """Создает счет на пополнение телефона через Portmone."""
    settings = get_settings()
    
    async with PortmoneDirectClient(settings) as client:
        try:
            response = await client.call(
                "bills.create",
                payeeId=payee_id,
                contractNumber=phone_number,
                amount=f"{amount:.2f}",
                currency="UAH",
                comment=f"Top-up for {phone_number}"
            )
            
            print(f"✅ Счет создан успешно!")
            print(f"   Bill ID: {response.bill_id}")
            print(f"   Contract Number: {response.contract_number}")
            
            return response
            
        except PortmoneResponseError as e:
            error = e.response.errors[0] if e.response.errors else None
            print(f"❌ Ошибка API: {error.code if error else 'unknown'} - {error.description if error else 'no description'}")
            raise
            
        except PortmoneTransportError as e:
            print(f"❌ Ошибка транспорта: {e}")
            raise

# Использование
if __name__ == "__main__":
    asyncio.run(create_topup_bill(
        phone_number="380991234567",
        amount=1.00,
        payee_id="2065"  # ID оператора (Київстар)
    ))
```

### Определение оператора по номеру телефона

```python
def get_operator_by_phone(phone_number: str) -> str:
    """Определяет оператора по номеру телефона."""
    if not phone_number.startswith("380") or len(phone_number) != 12:
        raise ValueError("Номер должен быть в формате 380XXXXXXXXX")
    
    prefix = phone_number[3:5]  # Первые 2 цифры после 380
    
    # Київстар: 039, 067, 068, 096, 097, 098
    if prefix in ['39', '67', '68', '96', '97', '98']:
        return "kyivstar"
    
    # Vodafone: 050, 066, 095, 099
    elif prefix in ['50', '66', '95', '99']:
        return "vodafone"
    
    # lifecell: 063, 073, 093
    elif prefix in ['63', '73', '93']:
        return "lifecell"
    
    else:
        return "unknown"

def get_payee_id_for_operator(operator: str, settings) -> str:
    """Возвращает payeeId для оператора."""
    operator_payee_ids = {
        "kyivstar": getattr(settings, "portmone_payee_id_kyivstar", None),
        "vodafone": getattr(settings, "portmone_payee_id_vodafone", None),
        "lifecell": getattr(settings, "portmone_payee_id_lifecell", None),
    }
    
    payee_id = operator_payee_ids.get(operator)
    if payee_id:
        return payee_id
    
    # Fallback на общий payee_id
    return settings.portmone_payee_id
```

---

*Последнее обновление: 2024*

