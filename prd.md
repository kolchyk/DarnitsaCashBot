# DarnitsaCashBot – Product Requirements Document

## 1. Overview
- **Vision**: Reward shoppers who purchase Darnitsa pharmaceuticals by crediting their mobile balance automatically after they submit a proof-of-purchase receipt in Telegram.
- **Product summary**: A Telegram bot (`DarnitsaCashBot`) collects receipt photos, a backend extracts Darnitsa line items and prices, and an EasyPay integration tops up the phone number shared by the user with a fixed 1₴ bonus per eligible receipt.
- **Primary users**: Retail customers purchasing Darnitsa products in Ukrainian pharmacies; internal support/marketing analysts.
- **Target release**: MVP within 6 weeks, focusing on Ukrainian market and top-3 mobile operators.

### 1.1 Goals
1. Automate validation of Darnitsa receipts received via Telegram with ≥95% precision for eligible items.
2. Deliver a frictionless bonus payout (≤2 minutes from upload to EasyPay confirmation).
3. Provide marketing with near real-time visibility into redeemed bonuses per product, region, and pharmacy.

### 1.2 Non-goals
- Managing promotions for non-Darnitsa brands.
- Supporting payout channels other than mobile top-up via EasyPay.
- Building a full loyalty wallet or points marketplace.

## 2. Success Metrics & KPIs
- Daily Active Uploaders (unique users sending ≥1 receipt).
- Receipt Acceptance Rate (approved / total uploaded).
- Bonus Fulfillment Time (p90 under 120 seconds).
- EasyPay Error Rate (failed payouts / payout attempts).
- Fraud Rejection Count (receipts flagged as duplicate/invalid).

## 3. Key Assumptions
1. Users have Telegram installed and can share a Ukrainian mobile number.
2. Pharmacies issue fiscal receipts that include product names and prices legible for OCR.
3. EasyPay exposes a REST API for mobile top-ups with synchronous confirmation.
4. Darnitsa marketing can supply a SKU list / regexes to validate product names and optional GTIN markers.

## 4. Personas
- **Budget-conscious Shopper**: buys medication, expects instant gratification for uploading a receipt.
- **Field Marketer**: tracks campaign performance, needs dashboards or exports.
- **Support Specialist**: resolves failed OCR or payout cases via admin tooling or logs.

## 5. User Stories
1. As a shopper, I want to send a photo of my receipt to the bot so that I can receive a mobile top-up reward.
2. As a shopper, I want to know whether my receipt was accepted or rejected and why.
3. As a marketer, I want to see how many bonuses were paid per SKU to measure promo effectiveness.
4. As a support specialist, I want to reprocess a receipt after manual correction to unblock a user.

## 6. User Journey & Flow
1. User opens `DarnitsaCashBot`, taps Start, consents to terms, and shares their mobile number (Telegram `request_contact` button).
2. User snaps or uploads a receipt photo (JPG/PNG, max 10 MB) and optionally adds text notes.
3. Bot confirms receipt of the image and sends “Processing…” message.
4. Backend stores the image, triggers OCR, and parses line items.
5. Rule engine identifies Darnitsa products, validates minimum purchase rules, and computes reward eligibility.
6. Bonus service triggers EasyPay mobile top-up for the stored MSISDN (1₴ per approved receipt).
7. Bot communicates the outcome:
   - Success: “We added 1₴ to +380XX… via EasyPay. Thank you!”
   - Failure: reason (illegible receipt, missing Darnitsa item, duplicate, payout error) and instructions.

## 7. System Architecture Overview
- **Telegram Layer**: Bot webhook hosted behind HTTPS reverse proxy (Cloudflare/NGINX) interfacing with Telegram servers.
- **Receipt Service**: Handles media uploads, stores images in object storage, emits events to processing queue (e.g., RabbitMQ/Kafka).
- **OCR Pipeline**: Stateless workers that call external OCR vendor, normalize text, and persist structured JSON.
- **Catalog & Rules Engine**: Service maintaining Darnitsa SKU metadata and eligibility logic; exposes gRPC/REST to other services.
- **Bonus Service**: Manages idempotent payout requests, interacts with EasyPay API, and updates BonusTransaction records.
- **Admin/API Gateway**: Provides REST APIs for bot, admin dashboard, and external hooks; handles auth, rate limiting, and audit logging.
- **Observability Stack**: Centralized logging, metrics, and alerting (e.g., ELK + Prometheus) with correlation IDs.

## 8. Functional Requirements

### 8.1 Telegram Bot
- Supports Ukrainian and Russian localization (system default Ukrainian, fallback Russian, English optional later).
- Commands: `/start`, `/help`, `/history`, `/change_phone`.
- Guided onboarding: consent text + privacy link + phone number share button.
- Validates that each receipt submission includes at least one image; rejects other file types with friendly prompt.
- Stores per-user state (phone number, onboarding completion, latest receipt status).

### 8.2 Receipt Intake & Storage
- Accept images up to 10 MB, minimum resolution 600 px on shortest edge.
- Store originals in object storage (e.g., S3-compatible or Azure Blob); retain 90 days for auditing.
- Generate compressed preview (≤300 KB) for admin review UI.

### 8.3 OCR & Receipt Parsing
- OCR service must extract:
  - Merchant name, purchase timestamp.
  - Line items: product name, quantity, unit price, total line price.
  - Receipt total.
- Apply language-specific normalization (Ukrainian + transliterated variations).
- Confidence threshold: only accept receipts when Darnitsa line item confidence ≥0.8; otherwise escalate to manual review queue.

### 8.4 Eligibility & Bonus Rules
- Eligible if receipt contains ≥1 Darnitsa SKU from the maintained catalog.
- Reward is fixed at 1₴ per unique receipt, regardless of receipt total or product quantity (MVP).
- Deduplicate receipts by hash of OCR text + total + timestamp; block submissions older than 7 days from purchase date.
- Users can submit max 3 receipts per day (configurable).

### 8.5 EasyPay Integration
- Use EasyPay mobile top-up API with the following fields: merchant credentials, MSISDN, amount (1 UAH), transaction reference, callback URL.
- All requests logged with correlation IDs tying Telegram user, receipt ID, and EasyPay transaction ID.
- Handle synchronous response plus async webhook (if available) to confirm final state.
- Retries: exponential backoff up to 3 attempts when EasyPay returns transient errors; never duplicate payouts for the same receipt.

### 8.6 Notifications & History
- Bot sends status updates (processing, success, failure) with inline buttons to resubmit or change number.
- `/history` lists last 5 receipts with status, timestamp, and EasyPay reference.
- Push reminder message if user starts but does not upload any receipt within 24 hours.

### 8.7 Admin & Support (Phase 2 optional, but consider hooks)
- Minimal dashboard to search receipts by phone or Telegram ID, view OCR output, override decisions, and replay payout.
- Export CSV of aggregated bonuses per product, pharmacy, region for marketing.

## 9. Non-functional Requirements
- **Reliability**: 99% uptime target for Telegram webhook and backend APIs; degraded mode allows manual processing queue.
- **Performance**: OCR plus eligibility check within 90 seconds p95; EasyPay request initiated within 30 seconds of approval.
- **Security**: Encrypt user phone numbers at rest, enforce GDPR-compliant data handling, audit log all admin actions.
- **Scalability**: Design for 10k daily receipts with bursty traffic during campaigns.
- **Compliance**: Follow Ukrainian promotional law; store consent records and opt-out mechanisms.

## 10. Data Model (High-level)
| Entity | Key Attributes | Notes |
| --- | --- | --- |
| User | telegram_id, phone_number, locale, consent_timestamp | Phone encrypted; one-to-many receipts. |
| Receipt | receipt_id, user_id, upload_ts, purchase_ts, merchant, status, ocr_payload_ref | Stores link to image + OCR JSON. |
| LineItem | receipt_id, sku_code, product_name, qty, price, confidence | Derived from OCR + catalog match. |
| BonusTransaction | transaction_id, receipt_id, msisdn, amount, easypay_status, retries | Idempotency via receipt_id. |
| CatalogItem | sku_code, product_aliases, active_flag, last_updated | Managed by marketing/config service. |

## 11. Integrations
1. **Telegram Bot API** – Webhook-based bot hosted on HTTPS endpoint with secret token validation.
2. **OCR Provider** – Could be Google Vision, AWS Textract, or on-prem; must support Ukrainian language packs and returning confidence per word/line.
3. **EasyPay API** – Need merchant contract, sandbox credentials, IP allow-list, and webhook endpoint for payment status.
4. **Analytics/BI** – Stream aggregated events to internal warehouse (e.g., BigQuery, Power BI) via nightly batch or event pipeline.

## 12. Edge Cases & Error Handling
- Blurry/partial receipts → bot requests re-upload with tips (good lighting, full receipt).
- Multiple receipts in one photo → treat as single submission; future enhancement to detect and split.
- Missing phone number consent → block payout until user shares contact.
- EasyPay maintenance window → queue payouts and notify users of delay.
- Duplicate receipts (same fiscal number) → auto reject with explanation.
- Unsupported mobile operator → return error and request alternative number.
- Fraud scenarios (manipulated images) → heuristic check (metadata, repeated totals) and manual review queue.

## 13. Analytics & Monitoring
- Events: `receipt_uploaded`, `receipt_accepted`, `receipt_rejected`, `payout_success`, `payout_failure`.
- Dashboards: daily funnels (uploads → accepted → paid), operator breakdown, SKU-level redemption.
- Alerts: OCR failure rate >5%, EasyPay failures >2% for 5 minutes, queue backlog >100 receipts.
- Log correlation IDs across bot, OCR, rule engine, and EasyPay calls.

## 14. Rollout Plan & Dependencies
1. **Week 1-2**: Finalize legal/privacy text, EasyPay contract, select OCR vendor, build Telegram bot skeleton.
2. **Week 3-4**: Implement OCR pipeline, rules engine, EasyPay integration (sandbox), internal admin views.
3. **Week 5**: End-to-end testing with sample receipts, load tests, fraud rule tuning.
4. **Week 6**: Pilot launch with limited audience (1000 users), monitor, then nationwide release.
5. **Dependencies**: Darnitsa SKU catalog, EasyPay credentials, secure hosting, marketing comms plan.

## 15. Risks & Open Questions
- **OCR accuracy on thermal receipts** – may require heuristics or manual review capacity.
- **EasyPay rate limits** – need confirmation on TPS caps and failover strategy.
- **Fraud prevention** – need additional signals (geolocation, device fingerprint) for scale.
- **Data retention** – confirm legal requirement for storing receipts beyond 90 days.
- **Support volume** – define SLAs and staffing if manual reviews spike.

## 16. Appendices
- **Sequence overview**: Telegram bot → Receipt service → OCR → Catalog matcher → Bonus service → EasyPay → Telegram notification.
- **Open API needs**: Provide REST endpoints for admin review (`/receipts/{id}`), payout status webhook handler (`/webhooks/easypay`).
- **Future enhancements**: variable bonus amounts based on basket value, integration with loyalty ID, support for paperless e-receipts.


