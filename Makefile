PYTHON ?= python

.PHONY: install install-dev lint fmt test up down migrate

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt

lint:
	ruff check .
	mypy apps libs services

fmt:
	ruff check . --fix

test:
	pytest

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	alembic upgrade head

