# DarnitsaCashBot

Платформа автоматизації, яка обробляє чеки з Telegram, валідує покупки Darnitsa та виконує поповнення через PortmoneDirect. Цей репозиторій відповідає специфікації [prd.md](docs/prd.md).

## Структура проекту

```text
apps/              # Користувацькі точки входу (Telegram бот, HTTP API)
libs/              # Спільні бібліотеки (конфігурація, доступ до даних, допоміжні функції)
services/          # Функціональні модулі (OCR, правила, виплати)
alembic/           # Міграції бази даних
scripts/           # Допоміжні скрипти для розробки та тестування
docs/              # Документація проекту
docker-compose.yml # Локальна інфраструктура: Postgres (опційно)
```

## Швидкий старт

### Вимоги

- Python 3.11-3.12
- Poetry для управління залежностями
- Docker та Docker Compose для локальної інфраструктури
- Tesseract OCR 5.x з мовними пакетами (`ukr`, `rus`, `eng`)

### Встановлення

```bash
# Встановлення залежностей
poetry install

# Копіювання прикладу конфігурації (якщо є)
# cp env.example .env

# Запуск інфраструктури (Postgres)
make up

# Застосування міграцій бази даних
make migrate

# Запуск API Gateway
poetry run api-gateway
# або
poetry run uvicorn apps.api_gateway.main:app --reload

# Запуск Telegram бота (в окремому терміналі)
poetry run telegram-bot
# або
poetry run python -m apps.telegram_bot.main
```

### Доступні команди

- `make install` — встановлення залежностей через Poetry
- `make lint` — перевірка коду (Ruff + mypy)
- `make fmt` — автоматичне форматування коду
- `make test` — запуск тестів (pytest)
- `make up` — запуск інфраструктури через Docker Compose
- `make down` — зупинка інфраструктури
- `make migrate` — застосування міграцій Alembic

## Налаштування PortmoneDirect

### Підготовка

1. Скопіюйте змінні `PORTMONE_*` з `env.example` (якщо є) та оновіть їх з обліковими даними та TLS-сертифікатом, виданим PortmoneDirect.

2. **Налаштування Portmone API**: Повне керівництво з налаштування Portmone Direct API для поповнення мобільного телефона доступне в [docs/portmone_setup.md](docs/portmone_setup.md).

3. **Перевірка підключення**: Використовуйте скрипт `python scripts/check_portmone_api.py` для перевірки підключення до API та коректності облікових даних.

### Webhook

FastAPI gateway надає ендпоінт `POST /portmone/webhook`. Захистіть його через `PORTMONE_WEBHOOK_TOKEN` та налаштуйте той самий токен на стороні Portmone.

### Моніторинг

Виплати бонусів організовані через Portmone клієнт у `services/bonus_service`. Метрики Prometheus (`portmone_request_total`, `portmone_fail_total{code}`, `portmone_request_latency_seconds`) моніторять стан інтеграції.

## OCR пайплайн

### Встановлення Tesseract

Встановіть Tesseract 5.x локально з мовними пакетами `ukr`, `rus` та `eng`:

- **macOS**: `brew install tesseract tesseract-lang`
- **Debian/Ubuntu**: `sudo apt install tesseract-ocr tesseract-ocr-ukr tesseract-ocr-rus tesseract-ocr-eng`

### Налаштування через змінні середовища

Опціональні параметри доступні через змінні середовища (див. `libs/common/config.py`):

- `TESSERACT_CMD`, `TESSDATA_DIR`, `OCR_LANGUAGES`
- `OCR_AUTO_ACCEPT_THRESHOLD`, `OCR_MANUAL_REVIEW_THRESHOLD`, `OCR_TOTALS_TOLERANCE_PERCENT`
- `OCR_STORAGE_PREFIX`, `OCR_ARTIFACT_TTL_DAYS`, `OCR_SAVE_PREPROCESSED`

### Використання

OCR запускається безпосередньо з ендпоінта `/bot/receipts`, тому окремі воркери та Docker-сервіси більше не потрібні. Переконайтеся, що Tesseract встановлений у середовищі, де працює API Gateway.

## Якість коду

- `make lint` — Ruff + mypy
- `make test` — pytest (unit + async integration)

## Деплой на Heroku

Проект готовий до деплою на Heroku. Детальні інструкції див. у [docs/heroku_database_inspection.md](docs/heroku_database_inspection.md) (якщо є окремий файл про деплой).

Швидкий старт:

```bash
heroku create your-app-name
heroku addons:create heroku-postgresql:mini

# Налаштування buildpack для встановлення системних залежностей (Tesseract OCR)
# Файл .buildpacks вже містить необхідні buildpack, але якщо потрібно налаштувати вручну:
heroku buildpacks:set https://github.com/heroku/heroku-buildpack-apt.git --index 1
heroku buildpacks:set heroku/python --index 2

heroku config:set TELEGRAM_BOT_TOKEN=your_token ENCRYPTION_SECRET=your_secret
git push heroku main
heroku run alembic upgrade head
heroku ps:scale web=1
```

**Важливо**: Проект використовує `Aptfile` для встановлення Tesseract OCR та інших системних залежностей. Файл `.buildpacks` автоматично налаштовує необхідний buildpack. Якщо після деплою виникає помилка `TesseractNotFoundError`, переконайтеся, що buildpack встановлено правильно:

```bash
heroku buildpacks --app your-app-name
```

Має бути:

1. `heroku-buildpack-apt` (для встановлення пакетів з Aptfile)
2. `heroku/python` (для Python залежностей)

### Налаштування Tesseract на Heroku

Код автоматично налаштовує Tesseract для Heroku:
- Автоматично знаходить tesseract у стандартних місцях встановлення (`/usr/bin/tesseract`, `/usr/local/bin/tesseract`)
- Автоматично встановлює `TESSDATA_PREFIX=/usr/share/tesseract-ocr/tessdata` (стандартне розташування для Ubuntu/Heroku)

Для явного вказання шляхів (опціонально), встановіть змінні середовища:

```bash
heroku config:set TESSERACT_CMD=/usr/bin/tesseract
heroku config:set TESSDATA_DIR=/usr/share/tesseract-ocr/tessdata
```

**Перевірка встановлення tesseract після деплою:**

```bash
# Перевірка версії tesseract
heroku run tesseract --version

# Перевірка доступних мовних пакетів
heroku run ls /usr/share/tesseract-ocr/tessdata

# Перевірка через Python/pytesseract
heroku run python -c "import pytesseract; print(pytesseract.get_tesseract_version())"

# Перевірка змінної середовища TESSDATA_PREFIX
heroku run python -c "import os; print('TESSDATA_PREFIX:', os.environ.get('TESSDATA_PREFIX', 'NOT SET'))"
```

## Доступні сервіси

Проект містить кілька сервісів, які можна запускати окремо:

- **API Gateway** (`apps/api_gateway`) — HTTP API для бота та адміністрації
- **Telegram Bot** (`apps/telegram_bot`) — Telegram бот для обробки чеків
- **OCR Worker** (`services/ocr_worker`) — воркер для обробки зображень чеків
- **Bonus Service** (`services/bonus_service`) — сервіс для виплати бонусів
- **Rules Engine** (`services/rules_engine`) — движок правил для валідації чеків

## Ключова документація

- [PRD](docs/prd.md) — Product Requirements Document
- [OCR](docs/OCR.md) — Документація по OCR обробці
- [Portmone Setup](docs/portmone_setup.md) — Повне керівництво з налаштування Portmone Direct API для поповнення мобільного телефона
- [Telegram Flow](docs/telegram_flow.md) — Опис потоку роботи з Telegram
- [Heroku Database Inspection](docs/heroku_database_inspection.md) — Робота з базою даних на Heroku

## Ліцензія

Проект розроблений для Darnitsa.
