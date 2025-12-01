# DarnitsaCashBot

Automation platform that ingests Telegram receipts, validates Darnitsa purchases, and triggers EasyPay top-ups. This repository follows the [prd.md](prd.md) specification and the build plan stored in `d-1b5d98.plan.md`.

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

## Quality Gates

- `make lint` — Ruff + mypy
- `make test` — pytest suite (unit + async integration)

## Key Docs

- [PRD](prd.md)
- [Architecture Plan](d-1b5d98.plan.md)

