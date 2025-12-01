# OCR Subsystem – Tesseract Integration PRD

## 1. Purpose & Scope
- Introduce a production-ready OCR subsystem powered by the Python `pytesseract` bindings and the Tesseract 5.x engine.
- Replace vendor OCR calls for fiscal receipts within `DarnitsaCashBot` while matching or exceeding MVP accuracy targets.
- Cover ingestion, pre/post-processing, resource sizing, quality controls, fallbacks, and operational guardrails specific to Tesseract.

## 2. Goals & Non-goals
### Goals
1. Deliver ≥95% receipt acceptance precision for Darnitsa SKU detection using on-prem Tesseract.
2. Keep average OCR processing time ≤4 s per receipt at p90 load (10k images/day).
3. Ensure OCR outputs remain explainable and auditable (retain intermediate artifacts 90 days).
4. Provide hooks for manual review when confidence is below the acceptance threshold.

### Non-goals
- Replacing the existing rule engine, payout logic, or Telegram UX.
- Supporting non-receipt document types (prescriptions, invoices).
- Providing multilingual support beyond Ukrainian, Russian, and fallback English in this phase.

## 3. Success Metrics & KPIs
- OCR Accuracy Rate: accepted receipts / total receipts sent to Tesseract.
- Median & p90 OCR Latency per receipt (goal ≤4 s / ≤8 s).
- Confidence Escalation Rate: share of receipts routed to manual review (<15% target).
- Reprocessing Success Rate: % of escalated receipts resolved after manual correction (>70%).
- GPU/CPU utilization vs. capacity (keep sustained usage ≤70% of provisioned resources).

## 4. Key Assumptions
1. Receipt images remain ≤10 MB and ≥600 px on the shortest edge.
2. Thermal receipts contain Ukrainian or Russian text with occasional Latin characters for SKUs/GTINs.
3. Infrastructure can host native Tesseract binaries (Linux containers preferred) with access to training data.
4. Marketing supplies and updates SKU synonyms/regexes for post-OCR catalog matching.
5. Manual review agents exist to handle low-confidence cases within 24 hours.

## 5. Personas & User Stories
- **OCR Platform Engineer**: maintains Tesseract configs and models; needs observability and rollback.
- **Support Specialist**: reprocesses receipts after manual edits; needs UI hooks.
- **Marketing Analyst**: relies on accurate SKU extraction to evaluate promo performance.

User stories:
1. As an OCR engineer, I want to tune Tesseract configs per receipt layout so I can balance accuracy and throughput.
2. As a support specialist, I want to rerun Tesseract with corrected crops or thresholds to unblock a shopper.
3. As a marketer, I want consistent SKU tagging so I can compare campaign cohorts.

## 6. OCR Flow
1. **Ingestion**: Receipt image arrives from Telegram intake and is stored in object storage.
2. **Pre-processing**: Worker normalizes format, denoises, deskews, and generates crops (header, line items).
3. **Tesseract Execution**: `pytesseract.image_to_data` runs with language packs `ukr+rus+eng`, custom tessdata, and tuned PSM/OCREngine modes.
4. **Post-processing**: Output tokens normalized (upper case, diacritics, transliteration), aggregated into line items, enriched with confidence metrics.
5. **Catalog Matching**: String similarity and regex matching link tokens to Darnitsa SKUs; deduplication + totals validation occurs.
6. **Scoring & Decision**: Combined confidence score determines auto-accept vs. manual review vs. hard reject.
7. **Persistence & Events**: Store raw OCR text, structured JSON, and derived signals; emit events for analytics and downstream services.

## 7. Functional Requirements
### 7.1 Image Intake & Pre-processing
- Support JPG/PNG/HEIC inputs; convert to TIFF for Tesseract if needed.
- Apply configurable pipeline: grayscale, adaptive thresholding, noise reduction, skew correction (Hough transform), contrast stretching.
- Segment receipts into logical zones (merchant header, body, totals) to allow targeted OCR passes.
- Retain both original and pre-processed images with metadata (filters applied, parameters) for audits.

### 7.2 Tesseract Configuration
- Package Tesseract 5.x with `ukr`, `rus`, `eng` traineddata plus custom finetuned data set for Darnitsa receipts.
- Use `pytesseract` to invoke:
  - `image_to_data` (structured output with confidences).
  - `image_to_osd` for orientation detection (fallback if skew >5° remains after preprocessing).
- Profiles:
  - **Full receipt**: `--oem 1` (LSTM), `--psm 4`.
  - **Line-item crop**: `--psm 6`, whitelist digits + Cyrillic letters + currency symbols.
  - **Totals**: `--psm 7`, whitelist digits, comma, dot, ₴, грн.
- Store configs in versioned YAML; allow runtime override via feature flags.

### 7.3 Post-processing & Entity Extraction
- Normalize text (Unicode NFC, remove repeated spaces, standardize ₴).
- Merge tokens into line items by y-coordinate clustering; compute `line_confidence = mean(token_conf * weight)`.
- Apply fuzzy matching (Levenshtein ≤2) and alias dictionaries to map to SKUs.
- Validate numeric consistency: sum(line_totals) ≈ receipt_total within ±1%.
- Derive metadata: fiscal number, merchant name, purchase timestamp via regex heuristics.

### 7.4 Quality Gates & Escalation
- Auto-accept threshold `line_confidence ≥0.8` and SKU match confirmed.
- Auto-reject if:
  - Image unreadable (mean confidence <0.4),
  - Receipt older than allowed window,
  - No merchant or total detected.
- Manual review queue when confidence between 0.4–0.8 or totals mismatch.
- Allow human agents to annotate/correct text, then rerun parsing without re-OCR if possible.

### 7.5 Integration & APIs
- Expose `POST /ocr/tasks` to enqueue receipt processing; respond with task_id.
- Provide `GET /ocr/tasks/{id}` returning status, confidence summary, parsed payload link.
- Publish `ocr.completed`, `ocr.failed`, `ocr.escalated` events with correlation IDs for downstream services.
- Ensure idempotency via receipt checksum to avoid duplicate OCR runs.

### 7.6 Configuration & Model Management
- Store tessdata fine-tunes in object storage with semantic versioning; workers download on boot.
- Maintain feature flag to toggle between vendor OCR and Tesseract for phased rollout.
- Provide CLI tooling to benchmark new configs on labeled datasets before promotion.

## 8. Non-functional Requirements
- **Reliability**: ≥99% task success outside maintenance windows; retries with exponential backoff for transient failures.
- **Performance**: Horizontal autoscaling of worker pods; warm pool sized for 2× p95 load.
- **Security**: Isolate OCR workers in private subnet; restrict access to receipt images; secrets managed via vault.
- **Compliance**: Store OCR artifacts for 90 days, enforce GDPR/PDPA wipe requests downstream.
- **Maintainability**: Configs and tessdata tracked in Git; CI runs regression suite on sample receipts.

## 9. Data Model & Storage
| Entity | Key Fields | Notes |
| --- | --- | --- |
| OCRTask | task_id, receipt_id, status, started_at, finished_at, worker_id | Status = queued/running/completed/failed/escalated. |
| OCRArtifact | artifact_id, task_id, type (raw_text, structured_json, preprocess_image), storage_uri, ttl | Links to object storage; TTL 90 days. |
| ConfidenceSignal | task_id, sku_code, line_confidence, parser_flags | Drives acceptance rules and analytics. |
| ManualReview | review_id, task_id, reviewer_id, adjustments, outcome | References corrected JSON and audit trail. |

## 10. Monitoring & Alerting
- Metrics: task throughput, latency histogram, confidence distribution, escalation counts, worker CPU/RAM.
- Logs: structured JSON with correlation IDs, applied filters, and Tesseract exit codes.
- Alerts:
  - Latency p95 >8 s for 5 min.
  - Confidence <0.6 median for 15 min.
  - Worker error rate >5% per rolling 10 min.
- Dashboards: receipt processing funnel, model version comparison, geographic breakdown of OCR failures.

## 11. Rollout Strategy
1. **Phase 0 (Week 1)**: Stand up tooling, collect 1k labeled receipts, benchmark vs. vendor OCR.
2. **Phase 1 (Weeks 2-3)**: Enable Tesseract for internal testers; run shadow mode alongside vendor.
3. **Phase 2 (Week 4)**: Gradually ramp to 25% of production traffic; monitor latency/confidence.
4. **Phase 3 (Week 5)**: Full switch with vendor as fallback; enable manual review tooling.
5. **Phase 4 (Week 6+)**: Optimize tessdata, add GPU acceleration if CPU saturation observed.

## 12. Risks & Mitigations
- **Thermal noise causing low confidence** → expand preprocessing with adaptive denoise + auto exposure; maintain manual review capacity.
- **Model drift (new receipt layouts)** → schedule monthly re-labeling; add self-serve upload tool for marketers to contribute samples.
- **Resource contention** → implement autoscaling thresholds and job queue prioritization.
- **Language pack gaps** → maintain custom training pipeline with incremental fine-tuning using field data.
- **Fallback complexity** → keep vendor OCR integration dormant but callable via feature flag until Tesseract stability proven.

