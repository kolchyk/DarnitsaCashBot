# DarnitsaCashBot

Automation platform that ingests Telegram receipts, validates Darnitsa purchases, and triggers PortmoneDirect top-ups. This repository follows the [prd.md](prd.md) specification and the build plan stored in `d-1b5d98.plan.md`.

## Project Layout

```
apps/              # User-facing entrypoints (telegram bot, HTTP APIs)
libs/              # Shared libraries (config, data access, helpers)
services/          # Background workers (OCR, rules, payouts, mocks)
tests/             # Unit/integration tests
docker-compose.yml # Local infra: Postgres, Redis, RabbitMQ, MinIO, mocks
```

## Getting Started

```bash
poetry install
cp env.example .env
make up              # start infra dependencies
poetry run uvicorn apps.api_gateway.main:app --reload
poetry run python -m apps.telegram_bot.main
```

## PortmoneDirect Sandbox

- Copy the `PORTMONE_*` variables from `env.example` and update them with the credentials and TLS bundle issued by PortmoneDirect.
- `docker compose up portmone-mock` exposes `http://localhost:8082/api/directcash/`, allowing end-to-end tests without touching the real API. Point `PORTMONE_API_BASE` to this URL in `.env`.
- The FastAPI gateway now exposes `POST /portmone/webhook`. Protect it via `PORTMONE_WEBHOOK_TOKEN` and configure the same token on the Portmone side.
- Bonus payouts are orchestrated through the Portmone client in `services/bonus_service`. Prometheus counters (`portmone_request_total`, `portmone_fail_total{code}`, `portmone_request_latency_seconds`) monitor integration health.

## OCR Worker Setup

- Install Tesseract 5.x locally with the `ukr`, `rus`, and `eng` language packs.  
  - macOS: `brew install tesseract tesseract-lang`  
  - Debian/Ubuntu: `sudo apt install tesseract-ocr tesseract-ocr-ukr tesseract-ocr-rus tesseract-ocr-eng`
- Optional knobs exposed through env vars (see `libs/common/config.py`):
  - `TESSERACT_CMD`, `TESSDATA_DIR`, `OCR_LANGUAGES`
  - `OCR_AUTO_ACCEPT_THRESHOLD`, `OCR_MANUAL_REVIEW_THRESHOLD`, `OCR_TOTALS_TOLERANCE_PERCENT`
  - `OCR_STORAGE_PREFIX`, `OCR_ARTIFACT_TTL_DAYS`, `OCR_SAVE_PREPROCESSED`
- Run the worker with `poetry run ocr-worker` or via Docker: `docker compose up ocr-worker`.
- Artifacts (deskewed TIFFs, raw TSV dumps) are written under the configured storage prefix for 90 days to satisfy the audit requirement described in `OCR.md`.

## Quality Gates

- `make lint` — Ruff + mypy
- `make test` — pytest suite (unit + async integration)

## Heroku Deployment

Проект готов к деплою на Heroku. Подробные инструкции см. в [docs/heroku_deployment.md](docs/heroku_deployment.md).

Быстрый старт:
```bash
heroku create your-app-name
heroku addons:create heroku-postgresql:mini
heroku addons:create heroku-redis:mini
heroku addons:create cloudamqp:lemur
heroku config:set TELEGRAM_BOT_TOKEN=your_token ENCRYPTION_SECRET=your_secret
git push heroku main
heroku run alembic upgrade head
heroku ps:scale web=1 worker=1
```

## Key Docs

- [PRD](prd.md)
- [Architecture Plan](d-1b5d98.plan.md)
- [Heroku Deployment](docs/heroku_deployment.md)

