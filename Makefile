PYTHON ?= python
POETRY ?= poetry

.PHONY: install lint fmt test up down migrate

install:
	$(POETRY) install --sync

lint:
	$(POETRY) run ruff check .
	$(POETRY) run mypy apps libs services

fmt:
	$(POETRY) run ruff check . --fix

test:
	$(POETRY) run pytest

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	$(POETRY) run alembic upgrade head

