# Настройка пополнения телефона через Portmone Direct API

## Обзор

Для пополнения мобильного телефона через Portmone Direct API используется метод **`bills.create`**, который создает счет на пополнение баланса телефона.

## Согласно документации Portmone

Согласно [официальной документации Portmone Direct](https://docs.portmone.com.ua/docs/uk/PortmoneDirectUa/):

### Метод: `bills.create`

**Назначение**: Создание счета на пополнение баланса мобильного телефона.

**Обязательные параметры**:
- `method=bills.create` - метод API
- `login` - логин компании-реселера
- `password` - пароль компании-реселера  
- `version` - версия протокола (рекомендуется "2")
- `payeeId` - **ID оператора мобильной связи** в системе Portmone
- `contractNumber` - **номер телефона** (MSISDN) в формате 380XXXXXXXXX
- `amount` - сумма пополнения в формате "XX.XX"
- `currency` - валюта (обычно "UAH")

**Опциональные параметры**:
- `comment` - комментарий к операции
- `lang` - язык локализации (uk/ru/en)

### Пример запроса

```
method=bills.create&login=LOGIN&password=PASSWORD&version=2&payeeId=OPERATOR_ID&contractNumber=380991234567&amount=1.00&currency=UAH&comment=Top-up
```

### Пример успешного ответа

```xml
<?xml version="1.0" encoding="utf-8"?>
<rsp status="ok">
    <bill>
        <billId>12345</billId>
        <contractNumber>380991234567</contractNumber>
        <amount>1.00</amount>
        <currency>UAH</currency>
    </bill>
</rsp>
```

## Текущая реализация в проекте

### Код пополнения телефона

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

### Настройки

Необходимые переменные окружения в `.env`:

```bash
# Обязательные для авторизации
PORTMONE_LOGIN=380992227160              # Ваш логин от Portmone
PORTMONE_PASSWORD=M4Y6NGBB               # Ваш пароль от Portmone
PORTMONE_VERSION=2                       # Версия протокола

# Обязательные для пополнения телефона
PORTMONE_PAYEE_ID=OPERATOR_ID            # ID оператора мобильной связи
                                         # Нужно получить от менеджера Portmone
                                         # для каждого оператора (Київстар, Vodafone, lifecell)

PORTMONE_DEFAULT_CURRENCY=UAH            # Валюта

# Опциональные
PORTMONE_API_BASE=https://direct.portmone.com.ua/api/directcash/
PORTMONE_LANG=uk
PORTMONE_CERT_PATH=                      # TLS сертификат (если требуется)
```

## Важные моменты

### 1. PayeeId (ID оператора)

**КРИТИЧЕСКИ ВАЖНО**: `payeeId` - это не ваш логин, а **ID оператора мобильной связи** в системе Portmone.

Для каждого оператора (Київстар, Vodafone, lifecell) нужен свой `payeeId`. Эти ID нужно получить от менеджера Portmone.

**Текущая проблема**: В коде используется `settings.portmone_payee_id`, который должен содержать ID оператора, а не ваш логин.

### 2. ContractNumber (номер телефона)

Номер телефона должен быть в формате:
- **380XXXXXXXXX** (12 цифр, начинается с 380)
- Без пробелов, дефисов и других символов
- Пример: `380991234567`

В текущей реализации номер берется из `User.phone_number` после расшифровки.

### 3. Amount (сумма)

Сумма передается в формате строки с двумя знаками после запятой:
- `"1.00"` для 1 гривны
- `"10.50"` для 10 гривен 50 копеек

В текущей реализации используется фиксированная сумма **1.00 UAH** (100 копеек = 1 гривна).

## Проверка настроек

### Шаг 1: Проверьте учетные данные

```bash
python scripts/check_portmone_api.py
```

Убедитесь, что:
- ✅ `PORTMONE_LOGIN` установлен правильно
- ✅ `PORTMONE_PASSWORD` установлен правильно
- ✅ Подключение к API работает

### Шаг 2: Получите PayeeId для операторов

**Обратитесь к менеджеру Portmone** и получите `payeeId` для каждого оператора:

- Київстар (Kyivstar)
- Vodafone Україна
- lifecell

Эти ID нужны для правильного пополнения телефонов разных операторов.

### Шаг 3: Настройте определение оператора

**Текущая реализация**: Использует один `PORTMONE_PAYEE_ID` для всех операторов.

**Рекомендация**: Нужно определить оператора по номеру телефона и использовать соответствующий `payeeId`:

```python
# Пример определения оператора по номеру
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

## Тестирование

### Локальное тестирование с mock-сервером

```bash
# Запустите mock-сервер
docker compose up portmone-mock

# В .env установите
PORTMONE_API_BASE=http://localhost:8082/api/directcash/
```

### Тестирование с реальным API

⚠️ **ВНИМАНИЕ**: Тестирование с реальным API создаст реальные счета!

Используйте тестовый номер телефона и минимальную сумму (1.00 UAH).

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
1. Убедитесь, что сумма в формате "XX.XX" (с точкой, два знака после запятой)
2. Проверьте минимальную сумму пополнения для оператора
3. Убедитесь, что сумма положительная

## Дополнительная информация

- [Официальная документация Portmone Direct](https://docs.portmone.com.ua/docs/uk/PortmoneDirectUa/)
- [Документация по авторизации](docs/portmone_auth.md)
- [Быстрый старт](docs/portmone_quickstart.md)

## Контакты поддержки

При возникновении проблем:
1. Проверьте логи приложения
2. Запустите скрипт проверки: `python scripts/check_portmone_api.py`
3. Обратитесь к менеджеру Portmone для:
   - Получения правильных `payeeId` для операторов
   - Проверки учетных данных
   - Проверки прав доступа к API пополнения телефонов

