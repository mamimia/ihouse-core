# Handoff — iHouse Core

**Date:** 2026-03-08  
**Time:** 22:05 local  
**Context status:** ~80% — open new chat

---

## Project

**Repo:** `mamimia/ihouse-core`  
**Branch:** `checkpoint/supabase-single-write-20260305-1747`  
**Local path:** `/Users/clawadmin/Antigravity Proj/ihouse-core`  
**PYTHONPATH for tests:** `src`  
**Venv:** `.venv` (source `.venv/bin/activate`)

---

## Last closed phase

### Phase 57 — Webhook Signature Verification ✅

**commit:** `4348bc3`

Created `src/adapters/ota/signature_verifier.py`:
- `verify_webhook_signature(provider, raw_body, signature_header)`
- HMAC-SHA256 with `hmac.compare_digest()` (timing-safe)
- Dev mode: `IHOUSE_WEBHOOK_SECRET_{PROVIDER}` not set → skip with warning
- `SignatureVerificationError` raised only when secret set + sig wrong
- All 5 providers: bookingcom, expedia, airbnb, agoda, tripcom
- `compute_expected_signature()` for test fixtures
- `get_signature_header_name()` for header lookup

Tests: 24 tests in `tests/test_signature_verifier.py`

---

## Test suite status

```
270 passed, 2 skipped (CI-safe suite)
```

2 skipped = SQLite tests (require `IHOUSE_ALLOW_SQLITE=1`, not in CI)

---

## OTA Adapter Matrix (all complete)

| Provider   | CREATE | CANCEL | AMENDED | Unique field mapping |
|------------|:------:|:------:|:-------:|----------------------|
| Booking.com| ✅ | ✅ | ✅ | `reservation_id`, `property_id` |
| Expedia    | ✅ | ✅ | ✅ | `reservation_id`, `property_id` |
| Airbnb     | ✅ | ✅ | ✅ | `listing_id → property_id` |
| Agoda      | ✅ | ✅ | ✅ | `booking_ref → reservation_id` |
| Trip.com   | ✅ | ✅ | ✅ | `order_id → reservation_id`, `hotel_id → property_id` |

---

## Next phase

### Phase 58 — HTTP Ingestion Layer (FastAPI endpoint)

**Objective:** Wire everything together into a real HTTP endpoint:

```
POST /webhooks/{provider}
  → validate signature (signature_verifier.py)
  → validate payload (payload_validator.py)
  → ingest_provider_event(provider, payload, tenant_id)
  → return 200 OK with envelope.idempotency_key
```

**Key decisions already made:**
- `tenant_id` comes from the JWT token (Supabase Auth) or a query param
- Signature verification: read raw body BEFORE `json.loads`
- 400 for validation errors, 403 for signature errors, 500 for unexpected

**Files to create:**
- `src/api/webhooks.py` — FastAPI router
- `tests/test_webhook_endpoint.py` — TestClient contract tests (no live server)

**Dependencies already available:**
- `signature_verifier.verify_webhook_signature`
- `payload_validator.validate_ota_payload`
- `service.ingest_provider_event`

---

## Key files

| File | Purpose |
|------|---------|
| `src/adapters/ota/signature_verifier.py` | HMAC-SHA256 webhook verification |
| `src/adapters/ota/service.py` | `ingest_provider_event()` |
| `src/adapters/ota/registry.py` | 5 registered adapters |
| `src/adapters/ota/semantics.py` | Event type → semantic kind |
| `src/adapters/ota/payload_validator.py` | Boundary validation |
| `src/adapters/ota/amendment_extractor.py` | 5 provider extractors |
| `docs/core/BOOT.md` | Operational rules (MUST READ on boot) |
| `docs/core/construction-log.md` | Phase history |

---

## Critical rules (from BOOT.md)

1. **Always read existing files fully before editing** — never blindly overwrite
2. **Context at ~80% → STOP, write handoff immediately**
3. **D = done/yes/continue**
4. **SQLite tests excluded from CI** — require `IHOUSE_ALLOW_SQLITE=1`
5. **E2E Supabase tests excluded from CI** — require live secrets
6. **Phase spec first** → build → close → construction log → commit → push
7. **Lint errors about path with spaces = false positives** — ignore (Pyre2 bug)

---

## How to resume

```bash
cd "/Users/clawadmin/Antigravity Proj/ihouse-core"
source .venv/bin/activate
PYTHONPATH=src python -m pytest --ignore=tests/invariants --ignore=tests/test_booking_amended_e2e.py
# Expected: 270 passed, 2 skipped
```

Then start Phase 58.
