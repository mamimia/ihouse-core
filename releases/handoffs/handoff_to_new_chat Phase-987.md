# Handoff to New Chat — Phase 987 (OCR Platform: Full Closure)

## Context and Objective

This handoff closes out the OCR platform work (Phases 982–986).
OCR is now a complete, production-ready capability integrated into the worker wizard flows.

The previous handoff is at: `releases/handoffs/handoff_to_new_chat Phase-981.md`

---

## What Was Built (Phases 982–986)

### Phase 982 — Foundation
- `src/ocr/scope_guard.py` — `validate_capture_type()` raises `OcrScopeViolation` for anything outside the 3 allowed types. DB-level `CHECK` constraint mirrors this.
- `src/ocr/provider_base.py` — `OcrProvider` ABC, `OcrRequest`, `OcrResult`, `OcrResultStatus`, `ConfidenceReport`, `ImageQualityWarning`
- `src/ocr/confidence.py` — `ConfidenceReport` builder with per-field thresholds and `overall_confidence` aggregation
- `src/ocr/provider_router.py` — `ProviderRegistry` and `FallbackOrchestrator` (priority queue + tenant-config override)
- `src/ocr/fallback.py` — `process_ocr_request()`, `test_provider()` — the top-level OCR entry point
- **DB:** `ocr_provider_config`, `ocr_results` tables (migration `20260328230000_phase982_ocr_platform.sql`)

### Phase 983 — Local OCR Providers
- `src/ocr/providers/local_mrz.py` — MRZ/passport line parser, strict uppercase validation, 12+ normalised identity fields
- `src/ocr/providers/local_meter.py` — Tesseract + digit-regex meter reader, noise-aware confidence scoring
- `src/ocr/providers/local_tesseract.py` — Generic Tesseract fallback
- `src/ocr/image_preprocessing.py` — Pillow pipeline: orientation, contrast enhance, quality estimation, Pillow 14+ compatible

### Phase 984 — Azure Document Intelligence Provider
- `src/ocr/providers/azure_di.py` — `AzureDocumentIntelligenceProvider`, `make_azure_provider_from_db_config()`
  - Async `httpx` calls to Azure `prebuilt-idDocument` model
  - 12 normalised Azure→canonical field mappings (see below)
  - Credential masking (INV-OCR-03): API key never logged or stored in raw response
  - Async polling for delayed analyze results

**Azure field mapping (all 12):**
| Azure field | Canonical name |
|---|---|
| `FirstName` + `LastName` | `full_name` |
| `DocumentNumber` | `document_number` |
| `DateOfBirth` | `date_of_birth` |
| `DateOfExpiration` | `passport_expiry` |
| `Sex` | `sex` |
| `CountryRegion` | `issuing_country` |
| `Nationality` | `nationality` |
| `PlaceOfBirth` | `place_of_birth` |
| `MachineReadableZone` | `mrz_line` |
| `Address` | `address` |
| `PersonalNumber` | `personal_number` |
| `DocumentType` | `document_type` |

**Missing field handling:** absent or low-confidence Azure fields are omitted from `extracted_fields`. No placeholder values are fabricated.

**Document type scope:** identity step supports PASSPORT, NATIONAL_ID, DRIVING_LICENSE. Azure uses `prebuilt-idDocument` which covers all three natively.

### Phase 985 — API Router
File: `src/api/ocr_router.py`, registered in `src/main.py`

| Endpoint | Role | Purpose |
|---|---|---|
| `POST /worker/ocr/process` | Worker | Submit image; scope guard fires first |
| `GET /worker/ocr/result/{id}` | Worker | Poll result by ID |
| `PATCH /worker/ocr/result/{id}/confirm` | Worker | Mark extracted fields as correct |
| `PATCH /worker/ocr/result/{id}/correct` | Worker | Submit field corrections |
| `GET /admin/ocr/review-queue` | Admin/Manager | List results awaiting review |
| `GET /admin/ocr/provider-config` | Admin/Manager | Provider config (API keys masked) |
| `POST /admin/ocr/test-connection` | Admin/Manager | Live provider ping (no quota cost) |

### Phase 986 — Pre-fill Wiring
File: `src/api/ocr_router.py` (new prefill endpoint)
Existing files patched: `checkin_identity_router.py`, `checkin_settlement_router.py`, `checkout_settlement_router.py`

**New endpoint:**
`GET /worker/ocr/prefill/{booking_id}/{capture_type}`
- Returns `prefill_fields` (corrected merged over extracted), `low_confidence_fields` (< 0.85), `result_id`
- Always 200 — missing OCR → empty prefill, never blocking

**DB columns added** (`20260329000000_phase986_ocr_prefill_linkage.sql`):
- `guests.ocr_result_id` → FK to `ocr_results.id`, nullable
- `electricity_meter_readings.ocr_result_id` → FK to `ocr_results.id`, nullable

**Existing endpoints now accept optional `ocr_result_id`:**
- `POST /worker/checkin/save-guest-identity` → stamps on guest record
- `POST /worker/bookings/{id}/checkin-settlement` → stamps on opening meter row
- `POST /worker/bookings/{id}/closing-meter` → stamps on closing meter row

---

## Product Invariants (locked)

| ID | Rule |
|---|---|
| **INV-OCR-01** | OCR scope is strictly `identity_document_capture`, `checkin_opening_meter_capture`, `checkout_closing_meter_capture` only. Enforced at API entry (scope_guard) AND DB CHECK constraint. |
| **INV-OCR-02** | OCR results are never auto-applied. Every response includes `review_required: True`. Worker must confirm or correct before submit. |
| **INV-OCR-03** | Azure API keys are never logged, never stored in raw_response. Masked at read-from-config and at response-storage time. |
| **INV-OCR-04** | OCR failure is non-blocking. All providers degrade to `FAILED` status. Worker falls back to manual entry. HTTP 200 always returned. |

---

## Test Coverage

| File | Tests | Covers |
|---|---|---|
| `tests/test_ocr_platform_foundation.py` | 50 | Scope guard, provider registry, fallback orchestrator, confidence, DB schema |
| `tests/test_ocr_local_providers.py` | 55 | MRZ parsing, meter confidence, Tesseract fallback, image preprocessing |
| `tests/test_ocr_azure_provider.py` | 28 | Azure adapter, field mapping, credential masking, polling |
| `tests/test_ocr_router.py` | 28 | Scope enforcement, validation, non-blocking failure, prefill, role guard |
| **Total** | **161** | All green |

---

## What Is NOT Done (explicit boundaries)

1. **Frontend integration** — The worker wizard UI has not been wired to these endpoints yet. The API contract is complete; the UI work is the next phase.
2. **Live Azure validation** — All 28 Azure tests are mocked. Real staging test with actual credentials has not been performed.
3. **Admin UI** — No admin dashboard panel for OCR provider config, connection testing, or review queue exists yet.
4. **Retry / webhook** — No background job for re-processing failed OCR results. Currently single-attempt with graceful failure.

---

## File Map

```
src/
  ocr/
    __init__.py
    scope_guard.py          — validate_capture_type(), OcrScopeViolation
    provider_base.py        — OcrProvider, OcrRequest, OcrResult, OcrResultStatus
    confidence.py           — ConfidenceReport, build_confidence_report()
    provider_router.py      — ProviderRegistry, FallbackOrchestrator
    fallback.py             — process_ocr_request(), test_provider()
    image_preprocessing.py  — preprocess_image(), estimate_image_quality()
    providers/
      __init__.py
      local_mrz.py          — LocalMrzProvider
      local_meter.py        — LocalMeterProvider
      local_tesseract.py    — LocalTesseractProvider
      azure_di.py           — AzureDocumentIntelligenceProvider
  api/
    ocr_router.py           — All OCR API endpoints (Phases 985–986)

supabase/migrations/
  20260328230000_phase982_ocr_platform.sql        — ocr_provider_config, ocr_results
  20260329000000_phase986_ocr_prefill_linkage.sql — guests.ocr_result_id, meter.ocr_result_id

tests/
  test_ocr_platform_foundation.py
  test_ocr_local_providers.py
  test_ocr_azure_provider.py
  test_ocr_router.py
```

---

## Wizard Integration Contract (for next session)

The wizard frontend flow is fully defined. When implementing:

```
Step 1: Worker taps "Scan"
   → POST /worker/ocr/process
   ← { result_id, extracted_fields, field_confidences, quality_warnings, review_required: true }

Step 2: Wizard fetches pre-fill (or uses /process response directly)
   → GET /worker/ocr/prefill/{booking_id}/{capture_type}
   ← { prefill_fields, low_confidence_fields, result_id, review_required: true }

Step 3: Worker reviews all fields. Low-confidence fields highlighted.
   Every field must be editable.

Step 4a: Worker confirms (no changes needed)
   → PATCH /worker/ocr/result/{result_id}/confirm

Step 4b: Worker corrects (changes made)
   → PATCH /worker/ocr/result/{result_id}/correct { corrections: { field: value } }

Step 5: Wizard submits to product entity with ocr_result_id for audit trail
   Identity:      POST /worker/checkin/save-guest-identity { ...fields, ocr_result_id }
   Opening meter: POST /worker/bookings/{id}/checkin-settlement { meter_reading, ocr_result_id }
   Closing meter: POST /worker/bookings/{id}/closing-meter { meter_reading, ocr_result_id }
```

---

## Session Status

- Phase 982: ✅ Complete
- Phase 983: ✅ Complete
- Phase 984: ✅ Complete (mocked; live staging validation pending)
- Phase 985: ✅ Complete
- Phase 986: ✅ Complete
- Phase 987: ✅ Handoff written (this document)
- Next: **Phase 988 — Worker wizard frontend: OCR capture UI**
