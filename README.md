# DarnitsaCashBot

Платформа автоматизації, яка обробляє чеки з Telegram, валідує покупки Darnitsa та виконує поповнення через PortmoneDirect. Цей репозиторій відповідає специфікації [prd.md](docs/prd.md).

## Структура проекту

```text
apps/              # Користувацькі точки входу (Telegram бот, HTTP API)
libs/              # Спільні бібліотеки (конфігурація, доступ до даних, допоміжні функції)
services/          # Фонові воркери (OCR, правила, виплати, моки)
alembic/           # Міграції бази даних
scripts/           # Допоміжні скрипти для розробки та тестування
docs/              # Документація проекту
docker-compose.yml # Локальна інфраструктура: Postgres, Redis, MinIO, моки
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

# Запуск інфраструктури (Postgres, Redis, MinIO)
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

2. **Налаштування авторизації**: Детальна інструкція з налаштування авторизації Portmone API доступна в [docs/portmone_auth.md](docs/portmone_auth.md).

3. **Перевірка підключення**: Використовуйте скрипт `python scripts/check_portmone_api.py` для перевірки підключення до API та коректності облікових даних.

### Тестування з моком

`docker compose up portmone-mock` надає доступ до `http://localhost:8082/api/directcash/`, що дозволяє проводити end-to-end тести без звернення до реального API. Встановіть `PORTMONE_API_BASE` на цю URL в `.env`.

### Webhook

FastAPI gateway надає ендпоінт `POST /portmone/webhook`. Захистіть його через `PORTMONE_WEBHOOK_TOKEN` та налаштуйте той самий токен на стороні Portmone.

### Моніторинг

Виплати бонусів організовані через Portmone клієнт у `services/bonus_service`. Метрики Prometheus (`portmone_request_total`, `portmone_fail_total{code}`, `portmone_request_latency_seconds`) моніторять стан інтеграції.

## Налаштування OCR Worker

### Встановлення Tesseract

Встановіть Tesseract 5.x локально з мовними пакетами `ukr`, `rus` та `eng`:

- **macOS**: `brew install tesseract tesseract-lang`
- **Debian/Ubuntu**: `sudo apt install tesseract-ocr tesseract-ocr-ukr tesseract-ocr-rus tesseract-ocr-eng`

### Налаштування через змінні середовища

Опціональні параметри доступні через змінні середовища (див. `libs/common/config.py`):

- `TESSERACT_CMD`, `TESSDATA_DIR`, `OCR_LANGUAGES`
- `OCR_AUTO_ACCEPT_THRESHOLD`, `OCR_MANUAL_REVIEW_THRESHOLD`, `OCR_TOTALS_TOLERANCE_PERCENT`
- `OCR_STORAGE_PREFIX`, `OCR_ARTIFACT_TTL_DAYS`, `OCR_SAVE_PREPROCESSED`

### Запуск воркера

```bash
# Локально
poetry run ocr-worker

# Через Docker
docker compose up ocr-worker
```

### Артефакти

Артефакти (вирівняні TIFF, сирі TSV дампи) зберігаються під налаштованим префіксом сховища протягом 90 днів для задоволення вимог аудиту, описаних у `docs/OCR.md`.

## Якість коду

- `make lint` — Ruff + mypy
- `make test` — pytest (unit + async integration)

## Деплой на Heroku

Проект готовий до деплою на Heroku. Детальні інструкції див. у [docs/heroku_database_inspection.md](docs/heroku_database_inspection.md) (якщо є окремий файл про деплой).

Швидкий старт:

```bash
heroku create your-app-name
heroku addons:create heroku-postgresql:mini
heroku addons:create heroku-redis:mini

# Налаштування buildpack для встановлення системних залежностей (Tesseract OCR)
# Файл .buildpacks вже містить необхідні buildpack, але якщо потрібно налаштувати вручну:
heroku buildpacks:set https://github.com/heroku/heroku-buildpack-apt.git --index 1
heroku buildpacks:set heroku/python --index 2

heroku config:set TELEGRAM_BOT_TOKEN=your_token ENCRYPTION_SECRET=your_secret
git push heroku main
heroku run alembic upgrade head
heroku ps:scale web=1 worker=1
```

**Важливо**: Проект використовує `Aptfile` для встановлення Tesseract OCR та інших системних залежностей. Файл `.buildpacks` автоматично налаштовує необхідний buildpack. Якщо після деплою виникає помилка `TesseractNotFoundError`, переконайтеся, що buildpack встановлено правильно:

```bash
heroku buildpacks --app your-app-name
```

Має бути:

1. `heroku-buildpack-apt` (для встановлення пакетів з Aptfile)
2. `heroku/python` (для Python залежностей)

### Налаштування Tesseract на Heroku

Якщо після деплою виникає помилка `TesseractNotFoundError`, код автоматично намагається знайти tesseract у стандартних місцях встановлення (`/usr/bin/tesseract`, `/usr/local/bin/tesseract`). Для явного вказання шляху до tesseract (рекомендовано для Heroku), встановіть змінну середовища:

```bash
heroku config:set TESSERACT_CMD=/usr/bin/tesseract
```

Перевірка встановлення tesseract:

```bash
heroku run tesseract --version
heroku run python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

## Доступні сервіси

Проект містить кілька сервісів, які можна запускати окремо:

- **API Gateway** (`apps/api_gateway`) — HTTP API для бота та адміністрації
- **Telegram Bot** (`apps/telegram_bot`) — Telegram бот для обробки чеків
- **OCR Worker** (`services/ocr_worker`) — воркер для обробки зображень чеків
- **Bonus Service** (`services/bonus_service`) — сервіс для виплати бонусів
- **Rules Engine** (`services/rules_engine`) — движок правил для валідації чеків

### Моки для тестування

- `portmone-mock` — мок PortmoneDirect API (порт 8082)
- `easypay-mock` — мок Easypay API (порт 8080)
- `ocr-mock` — мок OCR сервісу (порт 8081)

## Ключова документація

- [PRD](docs/prd.md) — Product Requirements Document
- [OCR](docs/OCR.md) — Документація по OCR обробці
- [Portmone Auth](docs/portmone_auth.md) — Налаштування авторизації Portmone
- [Portmone Quickstart](docs/portmone_quickstart.md) — Швидкий старт з Portmone
- [Telegram Flow](docs/telegram_flow.md) — Опис потоку роботи з Telegram
- [Heroku Database Inspection](docs/heroku_database_inspection.md) — Робота з базою даних на Heroku

## Ліцензія

Проект розроблений для Darnitsa.
