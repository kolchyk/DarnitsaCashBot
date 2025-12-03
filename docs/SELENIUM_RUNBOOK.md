# Selenium Runbook

Цей документ описує стабільний запуск headless Chromium/Selenium на Heroku та дії при збоях виду `DevToolsActivePort file doesn't exist`.

## 1. Buildpack та залежності

1. Розташуйте buildpack-и у такому порядку:
   ```bash
   heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-apt.git
   heroku buildpacks:add --index 2 heroku/python
   ```
2. `Aptfile` повинен містити:
   - `chromium-browser` та `chromium-chromedriver`
   - бібліотеки для headless режиму (`fonts-liberation`, `libgtk-3-0`, `libnss3`, `libxrandr2`, `libxkbcommon0`, `libasound2`, тощо)
3. Після успішного білду обидва виконувані файли доступні за шляхами:
   - `/app/.apt/usr/bin/chromium-browser`
   - `/app/.apt/usr/bin/chromedriver` (або `/app/.apt/usr/lib/chromium-browser/chromedriver`)

## 2. Налаштування застосунку

- `apps/api_gateway/services/ocr/receipt_scraper.py` автоматично:
  - шукає Chromium/Chrome у `/app/.apt`
  - створює унікальний `--user-data-dir`
  - додає обовʼязкові прапорці (`--headless=new`, `--remote-debugging-port=0`, `--single-process`, `--no-zygote`, `--no-sandbox` тощо)
  - робить до трьох спроб запуску перед помилкою
- Для контрольованого білду **не** вмикайте завантаження драйверів у продакшені. Залишайте `ENABLE_CHROMEDRIVER_AUTO_DOWNLOAD` не встановленою або рівною `0`.
- Для локальної розробки, коли версія Chrome відрізняється, можна тимчасово встановити:
  ```bash
  export ENABLE_CHROMEDRIVER_AUTO_DOWNLOAD=1
  ```
  Це дозволить `chromedriver-autoinstaller` або `webdriver-manager` підтягнути сумісний драйвер у профіль користувача.

## 3. Smoke-тести та перевірки

1. Перевірте наявність бінарників:
   ```bash
   heroku run "ls -l /app/.apt/usr/bin | grep chromium"
   ```
2. Запустіть швидкий smoke-тест (використовує ті ж налаштування, що й прод):
   ```bash
   heroku run "python scripts/test_parse_page.py --smoke"
   ```
   Тест відкриє локальну HTML-сторінку та завершиться кодом `0`, якщо браузер стартує коректно.
3. Для ручного дебагу можна запустити повний сценарій з потрібним URL:
   ```bash
   heroku run "python scripts/test_parse_page.py https://cabinet.tax.gov.ua/cashregs/check?id=... --save-html"
   ```

## 4. Усунення проблем

| Симптом | Дії |
| --- | --- |
| `DevToolsActivePort file doesn't exist` | Переконайтеся, що в логах видно знаходження Chromium і chromedriver. Якщо ні — повторно задеплойте з оновленим `Aptfile`. |
| `Chrome failed to start: crashed` | Перевірте, чи достатньо місця в `/tmp` (`df -h`). Додайте `heroku ps:restart` після очищення. |
| `SessionNotCreatedException` або невідповідна версія | Локально увімкніть `ENABLE_CHROMEDRIVER_AUTO_DOWNLOAD=1`, перезапустіть smoke-тест, після чого вимкніть змінну. |
| Потрібно більше логів | Увімкніть `LOG_LEVEL=DEBUG` та перегляньте `heroku logs --tail --dyno web`. |

## 5. Контрольний список при інциденті

1. `heroku releases:info` — перевірити останній деплой.
2. `heroku run "python scripts/test_parse_page.py --smoke"` — швидка діагностика.
3. Якщо тест падає:
   - `heroku buildpacks` — підтвердіть порядок buildpack-ів.
   - `heroku run "chromium-browser --version"` та `heroku run "chromedriver --version"` — переконайтеся, що версії сумісні.
   - Перевірте, чи не забитий `tmp` (`heroku run "ls /tmp"`).
4. Зробіть нотатки в інцидент-каналі, додайте уривок з `apps/api_gateway/services/ocr/receipt_scraper.py` із точним повідомленням.

Дотримання цього чек-листа забезпечує стабільне виконання headless Selenium та швидке виявлення збоїв.

