# Telegram Bot Flow & Setup Guide

This guide captures how to configure the Telegram-facing experience and how it aligns with the backend flow that powers `DarnitsaCashBot`. It is derived from the MVP requirements in `prd.md`, the payout details in `easy.md`, and the OCR expectations in `OCR.md`, plus the current implementation under `apps/telegram_bot`, `apps/api_gateway`, and the services in `services/`.

## 1. Scope & Prerequisites

- **Primary goal**: automate “receipt in → payout out” for Ukrainian shoppers, rewarding each accepted Darnitsa receipt with a 1 UAH mobile top-up.
- **Foundational docs**: keep `prd.md`, `OCR.md`, and `easy.md` open while operating the bot to validate assumptions (eligibility window, payout latency, fraud guardrails).
- **Infrastructure**: PostgreSQL, RabbitMQ, Redis, S3-compatible storage, OCR workers, rules engine, and EasyPay/Portmone connectivity must be reachable before switching on the bot.

## 2. Telegram Conversation Blueprint

### 2.1 Onboarding & Consent

1. `/start` (`apps/telegram_bot/handlers/commands.py::cmd_start`) greets the user and displays a `request_contact=True` button translated via `libs.common.i18n`.
2. The handler immediately calls `ReceiptApiClient.register_user()` to insert/refresh the user record with locale + phone if Telegram already shared it.
3. Without a phone number, payouts are blocked. The UX should keep prompting for contact data (see `handle_contact`) until `Receipt.phone_number` exists.
4. Terms/privacy text referenced in `prd.md` should be added to the welcome message or sent as a follow-up template if legal requires explicit consent logging.

### 2.2 Commands & States

| Command | Handler | Purpose |
| --- | --- | --- |
| `/start` | `commands.cmd_start` | Kick off onboarding, surface contact keyboard, register the user. |
| `/help` | `commands.cmd_help` | Explain the 1 UAH reward mechanic and highlight `/history` + `/change_phone`. |
| `/history` | `commands.cmd_history` | Fetch the last receipts through `/bot/history/{telegram_id}` and surface EasyPay references. |
| `/change_phone` | `commands.cmd_change_phone` | Re-open the contact keyboard. Trigger `handle_contact` when the user taps it. |

State storage (phone, locale, last statuses) lives in the backend DB; the bot remains stateless apart from the injected `ReceiptApiClient`.

### 2.3 Receipt Submission UX

1. `media.handle_receipt_photo` listens for `Message.photo`.
2. Bot validates the image size both client-side (`photo.file_size <= 10 MB`) and server-side (`apps/api_gateway/routes/bot.py::upload_receipt` re-checks `MAX_FILE_SIZE` and MIME type).
3. The bot answers with “Processing your receipt…” and streams the bytes to `/bot/receipts` (multipart upload, see `ReceiptApiClient.upload_receipt`).
4. The API gateway stores the file in object storage, enqueues `QueueNames.RECEIPTS`, and returns the initial DB status which the bot echoes back.
5. Non-photo payloads fall through to `fallback_handler`, keeping the chat clean and guiding users back to `/help`.

### 2.4 Localization & Copy Maintenance

- Aiogram uses gettext; translation calls wrap every string via `get_translator` and `.po` files under `apps/telegram_bot/locales/uk|ru/LC_MESSAGES`.
- Update copy by editing the `.po` files and recompiling catalogs via `poetry run pybabel compile`.
- Default locale derives from `Message.from_user.language_code[:2]`, so Ukrainian is default, Russian is fallback, English can be added later per `prd.md`.

### 2.5 Guardrails & Limits

- `apps/api_gateway/dependencies.get_receipt_rate_limiter` caps uploads at **5 per minute per Telegram ID** using Redis keys (`rl:receipt:{telegram_id}`).
- `services/rules_engine/service.py` enforces **max 3 accepted receipts per user per day** (`MAX_RECEIPTS_PER_DAY`) and rejects receipts older than **7 days** from the OCR purchase timestamp.
- `prd.md` also calls out image resolution (≥600 px short edge) and manual review workflow; enrich `media.handle_receipt_photo` responses if you add client-side heuristics (e.g., warn about blurry images).

## 3. Backend Processing Flow

| Step | Component & File | Description |
| --- | --- | --- |
| 1. Intake | `apps/api_gateway/routes/bot.py::upload_receipt` | Persists user + receipt, saves media to S3/MinIO via `StorageClient`, logs analytics, and publishes to `QueueNames.RECEIPTS`. |
| 2. OCR | `services/ocr_worker/worker.py` | Consumes receipt messages, calls the OCR service (`http://ocr-mock:8081/ocr` by default), stores JSON output on the `Receipt`, and emits to `QueueNames.OCR_RESULTS`. |
| 3. Eligibility | `services/rules_engine/service.py` | Loads catalog aliases (`CatalogRepository`), runs `is_receipt_eligible`, writes `LineItem`s, updates status to `accepted` or `rejected`, then publishes to `QueueNames.RULE_DECISIONS`. |
| 4. Bonus orchestration | `services/bonus_service/main.py` | On `status=accepted`, decrypts the MSISDN, creates/upserts `BonusTransaction`, posts to EasyPay/Portmone (see `easy.md`), updates statuses, emits analytics, and pushes status events to `QueueNames.BONUS_EVENTS`. |
| 5. Notifications | `apps/api_gateway/background.py::bonus_event_listener` | Listens on `bonus.events`, then delegates to `libs.common.notifications.NotificationService` to send final messages back to Telegram. |

Each hop preserves a correlation payload (`receipt_id`, `user_id`, `telegram_id`, `checksum`) so logs can be traced end-to-end.

## 4. OCR & Eligibility Expectations

- Follow the detailed preprocessing + Tesseract tuning in `OCR.md` (deskew, adaptive thresholding, `ukr+rus+eng`, confidence thresholds). The mock worker currently hits `ocr-mock`; swap it with the real OCR API by changing the URL and payload schema.
- Store raw OCR JSON in `Receipt.ocr_payload` (already done in `ocr_worker`). Maintain the 0.8 confidence threshold and manual review queue described in `OCR.md`; extend `services/rules_engine` to publish `reason` codes when escalation is needed.
- Deduplication currently uses SHA-256 of the uploaded bytes plus `ReceiptRepository` logic; ensure catalog aliases stay updated (`libs/data/models/catalog.py`) so `is_receipt_eligible` reflects the marketing SKU list.

## 5. Payout & Notification Flow

1. `bonus_service` decrypts `User.phone_number` via `libs.common.crypto.Encryptor` and stores a 1 UAH amount (code default is `100`, adjust to represent kopecks if needed).
2. The service calls EasyPay (or PortmoneDirect per `easy.md`). For production enablement, replace the manual HTTPX call with the official `easypay-api` client, set idempotency references, and honor the retry/backoff policy (3 attempts with exponential wait).
3. Responses update `BonusTransaction.easypay_status` (`IN_PROGRESS` → `SUCCESS` / `FAILED`) and optionally `bonus.easypay_reference`.
4. Analytics events (`payout_success`, `payout_failure`) stream via Redis (`libs/common/analytics.py`), powering the metrics in `prd.md`.
5. `bonus_event_listener` sends user-facing confirmations (“1 UAH top-up completed” vs. “Payment failed, try again”). Customize copy through `NotificationService`.

If Portmone is preferred, follow Section 4 of `easy.md`: call `bills.create`, store returned bill IDs, and wait for the callback endpoint to flip statuses before alerting the user.

## 6. Configuration & Deployment Checklist

1. **Telegram**
   - Set `TELEGRAM_BOT_TOKEN`, optional `TELEGRAM_WEBHOOK_URL` (webhook mode) or run polling via `apps/telegram_bot/main.py`.
   - Configure admin IDs via `TELEGRAM_ADMIN_IDS` to whitelist support staff.
2. **Persistence**
   - Populate `POSTGRES_*` secrets and run migrations (see `libs/data/models/*`).
   - Provide S3-compatible creds: `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`.
3. **Messaging & Caching**
   - Ensure RabbitMQ (`RABBITMQ_*`) and Redis (`REDIS_HOST`, `REDIS_PORT`) are reachable before starting workers.
4. **Security**
   - Generate `ENCRYPTION_SECRET` (32 bytes) for phone encryption.
   - Set JWT secrets if admin APIs are in use.
5. **External services**
   - `EASYPAY_API_BASE`, `EASYPAY_MERCHANT_ID`, `EASYPAY_MERCHANT_SECRET` or Portmone equivalents from `easy.md`.
   - OCR endpoint URL + credentials (update `ocr_worker` to use production host).
6. **Runtime order**
   - Launch dependencies (DB, storage, RabbitMQ, Redis) → start `apps/api_gateway` (FastAPI) → run background listener and schedulers → start `services/ocr_worker`, `services/rules_engine`, `services/bonus_service` → finally start `apps/telegram_bot`.
7. **Receipt API base URL**
   - Override `ReceiptApiClient(base_url=...)` in `apps/telegram_bot/main.py` if the API gateway is not on `http://localhost:8000`.

## 7. Monitoring, Alerts & Recovery

- **Metrics**: Track `receipt_uploaded`, `receipt_accepted`, `receipt_rejected`, `payout_success`, `payout_failure`, EasyPay error rate, OCR latency/confidence, and queue backlogs as laid out in `prd.md` and `OCR.md`.
- **Logs**: Enable structured logging via `configure_logging(settings.log_level)` everywhere; include `receipt_id`, `telegram_id`, and EasyPay references in each log entry to accelerate incident response.
- **Alerting suggestions**:
  - OCR failure rate >5% over 5 minutes.
  - EasyPay/Portmone `status=fail` streak >3 or webhook silence >30 seconds.
  - `bonus.events` queue depth >50 (notifications stuck).
- **Common recovery steps**:
  - **Receipt stuck in `processing`**: requeue the message onto `receipts.incoming` or re-run OCR via a manual endpoint once logs confirm storage availability.
  - **Rules false negatives**: update catalog aliases (`libs/data/models/catalog.py`) and re-run `services/rules_engine` for affected receipts.
  - **Payout failures**: inspect `BonusTransaction.easypay_status`, replay the payout with a fresh idempotency key, and notify support if EasyPay downtime exceeds SLA.
  - **Reminder job**: `apps/api_gateway/background.py::reminder_job` is a placeholder; extend it to ping users who ran `/start` but sent no receipt within 24h as required by `prd.md`.

Keep this document updated whenever handlers, services, or external integrations change so ops, marketing, and support teams have a single source of truth for the bot experience.


