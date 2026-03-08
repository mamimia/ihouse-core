# iHouse Core — Current Snapshot

## Current Phase
Phase 51 — Python Pipeline Integration (BOOKING_AMENDED routing)

## Last Closed Phase
Phase 50 — BOOKING_AMENDED DDL + apply_envelope Branch

## System Status

**The system is production-hardened and BOOKING_AMENDED is live on Supabase.**

apply_envelope is the only authority for canonical state mutations.

Health check: OVERALL OK ✅

## Phase 50 Result

BOOKING_AMENDED Prerequisites: **10/10 ✅** — all satisfied.

| Prerequisite | Status |
|-------------|--------|
| DLQ infrastructure | ✅ |
| booking_id stability | ✅ |
| MODIFY classification | ✅ |
| booking_state.status | ✅ |
| Ordering infrastructure | ✅ |
| Idempotency key format | ✅ |
| Normalized AmendmentPayload | ✅ |
| event_kind enum: BOOKING_AMENDED | ✅ (Phase 50 Step 1) |
| apply_envelope BOOKING_AMENDED branch | ✅ (Phase 50 Step 2) |
| ACTIVE-state lifecycle guard | ✅ (Phase 50 Step 2) |

**BOOKING_AMENDED branch behavior (live on Supabase):**
- booking_id guard → BOOKING_ID_REQUIRED
- SELECT FOR UPDATE row lock
- ACTIVE-state guard → AMENDMENT_ON_CANCELED_BOOKING if canceled
- Optional new_check_in / new_check_out (COALESCE preserves existing if not supplied)
- Date validation when both provided
- Append-only STATE_UPSERT to event_log
- UPDATE booking_state — status stays 'active'

**E2E verified (tests/test_booking_amended_e2e.py — 5 tests):**
- BOOKING_AMENDED → APPLIED, dates updated ✅
- Partial amendment (check_in only) → COALESCE preserves check_out ✅
- BOOKING_AMENDED on CANCELED → AMENDMENT_ON_CANCELED_BOOKING ✅
- BOOKING_AMENDED on non-existent → BOOKING_NOT_FOUND ✅

## Phase 51 Objective

Wire BOOKING_AMENDED through the Python OTA pipeline:

1. **semantics.py** — `reservation_modified` → `BOOKING_AMENDED` (replace `MODIFY` → reject)
2. **service.py** — BOOKING_AMENDED passes through like CREATED/CANCELED
3. **Contract tests** — `tests/test_booking_amended_contract.py`

## Full OTA Adapter Layer

| Module | Role |
|--------|------|
| `idempotency.py` | namespaced key generation + validation |
| `payload_validator.py` | boundary validation |
| `amendment_extractor.py` | amendment normalization |
| `dead_letter.py` | preserve rejected events |
| `dlq_replay.py` | controlled replay → apply_envelope |
| `dlq_inspector.py` | read-only DLQ observability |
| `dlq_alerting.py` | threshold alerting |
| `booking_status.py` | read booking lifecycle status |
| `ordering_buffer.py` | ordering buffer: write, read, mark |
| `ordering_trigger.py` | auto-trigger replay on BOOKING_CREATED |
| `health_check.py` | consolidated system readiness check |

## Tests
**158 passing** (2 pre-existing SQLite failures, unrelated)
