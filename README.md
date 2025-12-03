# DarnitsaCashBot

Платформа автоматизації, яка обробляє чеки з Telegram та валідує покупки Darnitsa.

## Про проект

DarnitsaCashBot — це Telegram бот, який допомагає користувачам отримувати бонуси за покупки продукції Darnitsa. Користувачі надсилають фото чеків у бот, система автоматично розпізнає інформацію з чеків та нараховує бонуси за відповідні покупки.

## Основні можливості

- Автоматичне розпізнавання чеків з фотографій
- Валідація покупок продукції Darnitsa
- Нарахування бонусів за відповідні покупки
- Зручний інтерфейс через Telegram

## Швидкий старт

### Встановлення

```bash
# Встановлення залежностей
poetry install

# Запуск інфраструктури
make up

# Застосування міграцій бази даних
make migrate

# Запуск сервісів
poetry run api-gateway
poetry run telegram-bot
```

### Доступні команди

- `make install` — встановлення залежностей
- `make lint` — перевірка коду
- `make fmt` — форматування коду
- `make test` — запуск тестів
- `make up` — запуск інфраструктури
- `make down` — зупинка інфраструктури
- `make migrate` — застосування міграцій бази даних

## Деплой

Проект готовий до деплою на Heroku. Детальні інструкції див. у документації проекту.

### Headless Selenium на Heroku

1. Додайте Apt buildpack перед Python buildpack:
   ```bash
   heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-apt.git
   heroku buildpacks:add --index 2 heroku/python
   ```
2. Файл `Aptfile` вже містить `chromium-browser`, `chromium-chromedriver` та необхідні системні бібліотеки. Кожен деплой підтягне узгоджені версії браузера й драйвера у `/app/.apt/`.
3. Для відтворюваних билдов тримайте `ENABLE_CHROMEDRIVER_AUTO_DOWNLOAD=0` (значення за замовчуванням). Вмикайте `1` лише локально, якщо потрібно завантажити драйвер під іншу версію Chromium.
4. Після деплою виконайте smoke-тест у dyno/CI:\
   ```bash
   python scripts/test_parse_page.py --smoke
   ```
5. За детальним чек-листом та порадами звертайтесь до `docs/SELENIUM_RUNBOOK.md`.

## Документація

- [PRD](docs/prd.md) — Product Requirements Document
- [OCR](docs/OCR.md) — Документація по OCR обробці
- [Telegram Flow](docs/telegram_flow.md) — Опис потоку роботи з Telegram
- [Selenium Runbook](docs/SELENIUM_RUNBOOK.md) — поради з діагностики headless Chrome

## Ліцензія

Проект розроблений для Darnitsa.
