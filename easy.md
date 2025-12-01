# Easypay Mobile Top-Up Quickstart

This guide summarizes the minimum steps required to hook the [`easypay-api`](https://github.com/hivesolutions/easypay-api) Python client into `DarnitsaCashBot` so that a shopper’s mobile balance is topped up only after their receipt is verified.

## 1. Prerequisites
- Python 3.10+ runtime (align with repo `pyproject.toml`).
- Valid Easypay merchant credentials (account ID + API key) with sandbox access.
- Secrets configured as environment variables (example):
  - `EASYPAY_ACCOUNT_ID`
  - `EASYPAY_API_KEY`
  - `EASYPAY_CALLBACK_URL` (public HTTPS endpoint served by `api_gateway`).
- Receipt processing pipeline publishes `receipt.accepted` events to `QueueNames.RULE_DECISIONS`.
- Optional telecom API contract if Easypay is not the final airtime executor.

## 2. Install & Configure the Client
1. `pip install easypay-api`
2. Extend `libs/common/config.py` (or equivalent settings module) with the new secrets so they are exposed by `get_settings()`.
3. Instantiate the client once per worker:
   ```python
   import easypay

   client = easypay.Api(
       account_id=settings.easypay_account_id,
       key=settings.easypay_api_key,
   )
   ```
4. Register a webhook route inside `apps/api_gateway/routes/bot.py` (or dedicated module) that parses Easypay callback payloads and enqueues them to `QueueNames.BONUS_EVENTS`.

## 3. Receipt-Gated Payment Flow
1. Bonus worker consumes `receipt.accepted` messages, ensures `Receipt.status == "accepted"` and decrypts the MSISDN.
2. Construct the payment request using the SDK helper:
   ```python
   payment = client.generate_payment(
       amount=bonus.amount,
       method="mb",
       metadata={
           "receipt_id": str(receipt.id),
           "bonus_id": str(bonus.id),
           "telegram_id": receipt.user.telegram_id,
       },
   )
   ```
3. Persist `payment["id"]` (or `payment["reference"]`) on `BonusTransaction` for idempotency.
4. Publish `payout_initiated` analytics + bot placeholder (“Processing top-up…”).
5. When Easypay sends a webhook:
   - Validate signature/HMAC with the SDK utilities.
   - Re-fetch the transaction if needed (`client.get_payment(payment_id)`).
   - Update `bonus.easypay_status` and `receipt.status`.
   - If `status == "success"`:
     - Call telecom top-up API when required and save returned reference.
     - Publish `payout_success` event for the Telegram bot.
   - Otherwise set `bonus.easypay_status = FAILED`, trigger retries or manual review, and notify the user.

## 4. Observability & Alerting
- Log every request/response pair with correlation IDs: `receipt_id`, `bonus_id`, `payment_id`, `telegram_id`.
- Emit metrics: `payout_initiated`, `payout_success`, `payout_failure`, `payout_timeout`.
- Capture webhook payloads and Easypay PDF/JSON receipts for at least 90 days.
- Alert when:
  - Easypay HTTP error rate >2% for 5 min.
  - Average payout SLA >30 s once webhook received.
  - Signature validation fails (possible security incident).

## 5. Testing Strategy
- Use `services/easypay_mock` as a local sandbox:
  - `uvicorn services.easypay_mock.main:app --reload --port 8080`
  - Point `EASYPAY_API_BASE=http://localhost:8080` to verify request shapes.
- Add integration tests that:
  - Simulate `receipt.accepted` → verify one Easypay call + ledger update.
  - Replay webhook payloads (success/failure) → assert bot notifications.
- Before production cut-over, run Easypay-provided certification script with live sandbox credentials to confirm webhook reachability and signature validation.

## 6. Rollout Checklist
- [ ] Easypay merchant keys stored in secret manager and rotated.
- [ ] Bonus worker uses `easypay.Api` instead of raw HTTP.
- [ ] Webhook route deployed behind HTTPS with signature verification.
- [ ] Telecom (if separate) acknowledges payload contract.
- [ ] Observability dashboards updated with payout metrics.
- [ ] Runbook updated with retry and manual fallback procedure.


