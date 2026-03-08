# Handoff — Phase 76 → Phase 77
**Created:** 2026-03-09T01:33:00+07:00
**From chat:** 9c5523cc-4b0a-4654-97f7-dde2bfa5dd4b
**Reason:** Context at ~80% — clean handoff per BOOT.md protocol

---

## Last Closed Phase

**Phase 76 — occurred_at vs recorded_at Separation**
- Commit: `4fdd493`
- Branch: `checkpoint/supabase-single-write-20260305-1747`
- Tests: **545 passed, 2 skipped**

---

## Phases Completed This Session

| Phase | Title | Tests |
|-------|-------|-------|
| 73 | Ordering Buffer Auto-Route | +11 |
| 74 | OTA Date/Timezone Normalization | +22 |
| 75 | Production Hardening — API Error Standards | +19 |
| 76 | occurred_at vs recorded_at Separation | +12 |

**Total: 492 → 545 (+53 in this session)**

---

## Next Phase: Phase 77 — OTA Schema Normalization

**Goal:** Unify inconsistent field names across OTA providers into canonical field names.

**Problem:** Every provider uses different field names for the same concept:
- guest count: `num_guests` (Agoda), `guest_count` (Airbnb), `guests` (Trip.com), `number_of_guests` (Booking.com), `count` (Expedia in guests.count)
- booking ID: `reservation_id`, `booking_id`, `confirmation_id`, `order_id`
- property ID: `property_id`, `hotel_id`, `listing_id`, `property_code`

**Approach:**
- Create `src/adapters/ota/schema_normalizer.py`
- Normalize to canonical field names in `NormalizedBookingEvent.payload` at the adapter layer
- Write contract tests covering all 5 providers for each field type

---

## Key System State

### Test Count
- **545 passed, 2 skipped** (pre-existing SQLite skips, unrelated)

### Key Files Modified This Session
| File | What Changed |
|------|-------------|
| `src/adapters/ota/service.py` | Ordering buffer auto-route + recorded_at stamping |
| `src/adapters/ota/dead_letter.py` | write_to_dlq_returning_id() |
| `src/adapters/ota/ordering_buffer.py` | dlq_row_id Optional |
| `src/adapters/ota/date_normalizer.py` | NEW — normalize_date() |
| `src/adapters/ota/amendment_extractor.py` | All 5 providers use normalize_date() |
| `src/api/error_models.py` | NEW — make_error_response() |
| `src/main.py` | X-API-Version header |
| `src/api/bookings_router.py` | Standard error format |
| `src/api/admin_router.py` | Standard error format |
| `src/adapters/ota/schemas.py` | CanonicalEnvelope.recorded_at field |

### New Test Files
- `tests/test_ordering_buffer_autoroute_contract.py` (11 tests)
- `tests/test_date_normalizer_contract.py` (22 tests)
- `tests/test_api_error_standards_contract.py` (19 tests)
- `tests/test_recorded_at_separation_contract.py` (12 tests)

---

## System Architecture Notes

### Error Format (Phase 75 standard)
All new routers return:
```json
{
  "code":     "BOOKING_NOT_FOUND",
  "message":  "Booking not found for this tenant",
  "trace_id": "uuid"
}
```
Legacy routers (`financial_router`, `webhooks`) still use `{"error": "..."}` for backward compat.

### Timestamp Semantics (Phase 76)
- `occurred_at` = OTA provider business event time (untrusted, from OTA payload)
- `recorded_at` = Server ingestion timestamp (always UTC, set by our server, never from OTA)

### Date Normalization (Phase 74)
All OTA amendment dates pass through `normalize_date()` → always `"YYYY-MM-DD"`.
Handles: ISO date, ISO datetime ±TZ, compact YYYYMMDD, slash DD/MM/YYYY.

---

## BOOT Instructions
On next chat start:
1. Read `docs/core/BOOT.md` first
2. Read `docs/core/work-context.md`
3. Read `docs/core/current-snapshot.md`
4. Run: `PYTHONPATH=src pytest tests/ --ignore=tests/invariants -q` to confirm 545 passed
5. Start Phase 77 — OTA Schema Normalization

---

## Doc Files to Read
- `docs/core/work-context.md` — current phase + objective
- `docs/core/current-snapshot.md` — full system state
- `docs/core/phase-timeline.md` — all closed phases
- `docs/archive/phases/phase-76-spec.md` — last phase spec
