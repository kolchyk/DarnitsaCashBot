# PortmoneDirect Billing Quickstart

This guide explains how to extend `DarnitsaCashBot` so it can create and manage PortmoneDirect bills and mobile top-ups only after receipts are verified. All API traits referenced below come from the official [PortmoneDirect documentation](https://docs.portmone.com.ua/docs/uk/PortmoneDirectUa/) and should be treated as the source of truth for production deployments.

## 1. API Surface Recap
- Base endpoint: `https://direct.portmone.com.ua/api/directcash/`.
- REST over HTTPS (TLS 1.2). Only POST requests are accepted even if the examples display a leading `?`.
- Every call must include the reseller `login`, `password`, `method`, and `version` (defaults to `1` if omitted). Portmone issues the credentials plus the client TLS certificate.
- Responses are XML, UTF‑8 encoded, and wrap the payload inside `<rsp status="ok|fail">`.
- Common request example:
  ```text
  method=bills.create&login=LOGIN&password=PASSWORD&version=2&payeeId=ID&contractNumber=VALUE
  ```
- Success response:
  ```xml
  <rsp status="ok">
      ...
  </rsp>
  ```
- Failure response (protocol `>=2`):
  ```xml
  <rsp status="fail">
      <error code="123">Short message</error>
      <error_description>Detailed explanation</error_description>
  </rsp>
  ```
- Optional localization parameter `lang` (`uk`, `ru`, `en`) adjusts tariff/item names; omit it to keep Ukrainian defaults.
- Date fields use `DD.MM.YYYY`.

## 2. Prerequisites & Secrets
- Python 3.10+ runtime (per `pyproject.toml`).
- PortmoneDirect reseller credentials and TLS bundle.
- Environment variables surfaced via `libs/common/config.py`:
  - `PORTMONE_LOGIN`
  - `PORTMONE_PASSWORD`
  - `PORTMONE_CERT_PATH` (PEM or PFX converted to PEM).
  - `PORTMONE_API_BASE` (default `https://direct.portmone.com.ua/api/directcash/`).
  - `PORTMONE_VERSION` (set to `2` to access extended errors/localization).
  - `PORTMONE_LANG` (optional).
- Existing receipt processing pipeline that publishes `receipt.accepted` events to `QueueNames.RULE_DECISIONS`.
- Optional downstream telecom API contract if PortmoneDirect is only delivering payment orders and not the final airtime execution.

## 3. Client Setup
1. Install an HTTP client with solid TLS support, e.g. `pip install httpx`.
2. Extend `libs/common/config.py` so the new secrets appear on `get_settings()`.
3. Create a thin wrapper around PortmoneDirect:
   ```python
   import httpx

   class PortmoneDirectClient:
       def __init__(self, settings):
           self._base = settings.portmone_api_base
           self._auth = {
               "login": settings.portmone_login,
               "password": settings.portmone_password,
               "version": settings.portmone_version or "2",
           }
           self._lang = settings.portmone_lang
           self._client = httpx.Client(
               base_url=self._base,
               cert=settings.portmone_cert_path,
               timeout=10.0,
           )

       def call(self, method, **params):
           payload = {"method": method, **self._auth, **params}
           if self._lang:
               payload["lang"] = self._lang
           response = self._client.post("", data=payload)
           response.raise_for_status()
           return response.text
   ```
4. Register a webhook in `apps/api_gateway/routes/bot.py` (or a dedicated blueprint) that receives PortmoneDirect status notifications and pushes them into `QueueNames.BONUS_EVENTS`.
5. Normalize XML parsing inside a shared helper so workers can map `<rsp status>` and `<error>` payloads into domain enums.

## 4. Receipt-Gated Flow
1. Bonus worker consumes `receipt.accepted` events, ensures `Receipt.status == "accepted"`, decrypts the MSISDN, and gathers the `payeeId`/`contractNumber`.
2. Prepare the Portmone payload:
   ```python
   payload = {
       "payeeId": bonus.payee_id,
       "contractNumber": receipt.contract_number,
       "amount": f"{bonus.amount:.2f}",
       "currency": "UAH",
       "comment": f"Top-up for receipt {receipt.id}",
   }
   raw_xml = portmone_client.call("bills.create", **payload)
   ```
3. Persist the returned bill/transaction identifiers on `BonusTransaction` for idempotency and reconciliation.
4. Publish `payout_initiated` analytics plus a bot placeholder (“Processing PortmoneDirect top-up…”).
5. When PortmoneDirect posts a callback:
   - Validate the source IP/TLS fingerprint and signature (if enabled).
   - Parse `<rsp status>`; update `bonus.portmone_status` and `receipt.status`.
   - On `status="ok"` trigger the telecom top-up and emit `payout_success`.
   - On `status="fail"` capture `<error code>` and `<error_description>`, move the bonus into a retry/manual bucket, and inform the user.

## 5. Error Handling, Localization & Observability
- Always log the raw XML and derived payload using correlation IDs (`receipt_id`, `bonus_id`, `bill_id`, `telegram_id`).
- Attach `lang` to every request if the bot needs localized tariff/attribute names for user-facing messages.
- Metrics to emit: `portmone_request_total{method}`, `portmone_fail_total{code}`, `portmone_callback_latency`, `payout_success`, `payout_failure`, `payout_timeout`.
- Alert when:
  - Portmone HTTP error rate >2% for 5 minutes.
  - Callback processing SLA exceeds 30 s.
  - The API falls back to protocol version 1 (missing `error_description`), signaling misconfiguration.
- Archive request/response pairs and Portmone XML receipts for at least 90 days for dispute resolution.

## 6. Testing & Rollout
- Use a sandbox (or mock) service to replay XML responses locally:
  - `uvicorn services.portmone_mock.main:app --reload --port 8081`
  - Point `PORTMONE_API_BASE=http://localhost:8081/api/directcash/`.
- Add integration tests that:
  - Simulate `receipt.accepted` → assert exactly one `bills.create` call and ledger update.
  - Replay success/failure callbacks → verify `bonus.portmone_status`, telecom fan-out, and Telegram notifications.
- Run Portmone’s certification checklist before enabling production traffic (TLS chain, credential scope, callback reachability, localization).
- Rollout checklist:
  - [ ] Credentials stored in the secret manager and rotated.
  - [ ] Workers use the shared Portmone client (no ad-hoc HTTP calls).
  - [ ] Callback endpoint exposed over HTTPS with mutual TLS if required.
  - [ ] Observability dashboards updated with the new metrics/alerts.
  - [ ] Runbook documents retry policy and manual fallback procedure.