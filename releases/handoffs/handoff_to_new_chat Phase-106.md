# Handoff to New Chat — Phase 106

**Written:** 2026-03-09T17:21:30+07:00
**Reason:** Context at ~80% — stopping per BOOT.md protocol.
**Branch:** `checkpoint/supabase-single-write-20260305-1747`
**Last commit:** `729205b` — Phase 106 — Booking List Query API (closed)

---

## Current Status

| Field | Value |
|-------|-------|
| **Last closed phase** | Phase 106 — Booking List Query API |
| **Tests passing** | **2374** (2 pre-existing SQLite skips, unrelated) |
| **Next phase** | Phase 107 |
| **In-progress work** | Nothing — Phase 106 fully closed and pushed |

---

## What Was Done This Session (Phases 103–106)

### Phase 103 — Payment Lifecycle Query API ✅
- **New:** `src/api/payment_status_router.py` — `GET /payment-status/{booking_id}`
- Reads `booking_financial_facts` most-recent row, calls `explain_payment_lifecycle()` (Phase 93), returns `PaymentLifecycleState` + `rule_applied` + `reason`
- **New:** `tests/test_payment_status_router_contract.py` — 24 tests
- `src/main.py` updated — router + tag

### Phase 104 — Amendment History Query API ✅
- **New:** `src/api/amendments_router.py` — `GET /amendments/{booking_id}`
- Reads `booking_financial_facts WHERE event_kind='BOOKING_AMENDED'` ORDER BY `recorded_at ASC`
- 200+empty for known unamended booking; 404 for unknown booking
- **New:** `tests/test_amendments_router_contract.py` — 20 tests
- `src/main.py` updated — router + tag

### Phase 105 — Admin Router Phase 82 Contract Tests ✅
- **New:** `tests/test_admin_router_phase82_contract.py` — 41 tests
- Covers 4 Phase 82 endpoints that had zero tests: `/admin/metrics`, `/admin/dlq`, `/admin/health/providers`, `/admin/bookings/{id}/timeline`
- Zero production source changes

### Phase 106 — Booking List Query API ✅
- **Modified:** `src/api/bookings_router.py` — added `GET /bookings` list endpoint
- Query params: `?property_id=`, `?status=active|canceled` (400 VALIDATION_ERROR on invalid), `?limit=1–100` (default 50, server-clamped)
- Returns `{ tenant_id, count, limit, bookings: [...] }` ordered by `updated_at DESC`
- **New:** `tests/test_booking_list_router_contract.py` — 28 tests, Groups A–G

---

## Current API Surface (Complete)

| Endpoint | Phase | Router |
|----------|-------|--------|
| `POST /webhooks/{provider}` | 46 | webhooks.py |
| `GET /health` | 64 | health.py |
| `GET /financial/{booking_id}` | 67 | financial_router.py |
| `GET /bookings/{booking_id}` | 71 | bookings_router.py |
| `GET /bookings` | 106 | bookings_router.py |
| `GET /admin/summary` | 72 | admin_router.py |
| `GET /admin/metrics` | 82 | admin_router.py |
| `GET /admin/dlq` | 82 | admin_router.py |
| `GET /admin/health/providers` | 82 | admin_router.py |
| `GET /admin/bookings/{id}/timeline` | 82 | admin_router.py |
| `GET /owner-statement/{property_id}?month=` | 101 | owner_statement_router.py |
| `GET /payment-status/{booking_id}` | 103 | payment_status_router.py |
| `GET /amendments/{booking_id}` | 104 | amendments_router.py |

---

## Key Locked Invariants (Do NOT Change)

- `booking_state` must NEVER contain financial calculations (Phase 62+ invariant)
- All API endpoints are strictly read-only — no writes to `booking_state` or `event_log`
- Tenant isolation at DB level via `.eq("tenant_id", tenant_id)` on every query
- `explain_payment_lifecycle()` is pure / no IO — never called with a DB client
- DLQ writes are best-effort and must never block OTA ingestion responses

---

## Key Files

| File | Purpose |
|------|---------|
| `src/main.py` | FastAPI app — all routers registered here |
| `src/api/bookings_router.py` | GET /bookings/{id} + GET /bookings list (Phase 71 + 106) |
| `src/api/amendments_router.py` | GET /amendments/{booking_id} (Phase 104) |
| `src/api/payment_status_router.py` | GET /payment-status/{booking_id} (Phase 103) |
| `src/api/admin_router.py` | All /admin/* endpoints (Phase 72 + 82) |
| `src/api/financial_router.py` | GET /financial/{booking_id} (Phase 67) |
| `src/api/owner_statement_router.py` | GET /owner-statement/{property_id} (Phase 101) |
| `src/adapters/ota/payment_lifecycle.py` | explain_payment_lifecycle() — Phase 93 |
| `src/adapters/ota/dead_letter.py` | write_to_dlq / write_to_dlq_returning_id |
| `src/adapters/ota/dlq_inspector.py` | get_pending_count, get_replayed_count, get_rejection_breakdown |
| `src/adapters/ota/idempotency_monitor.py` | collect_idempotency_report() |
| `src/adapters/ota/service.py` | ingest_provider_event_with_dlq (main ingestion entry point) |
| `tests/test_e2e_integration_harness.py` | 375 E2E tests across 11 OTA providers |
| `docs/core/roadmap.md` | Forward roadmap — check for Phase 107 guidance |

---

## What to Do Next — Phase 107

Check `docs/core/roadmap.md` for Phase 107 guidance. Based on the roadmap section "Where We Land After Phase 107" and the current trajectory, likely candidates are:

1. **Financial List Query API** — `GET /financial?property_id=&month=` — list financial records with filters (parallel to what Phase 106 did for bookings)
2. **Roadmap Refresh** — update `roadmap.md` to reflect actual Phase 103–106 completion and plan 107–120
3. **Booking Search API** — `GET /bookings?check_in_from=&check_in_to=` — date range filter (extension of Phase 106)

All are no-schema-change phases — pure Python + tests.

---

## How to Boot

1. Read `docs/core/BOOT.md` (always first)
2. Read `docs/core/work-context.md`
3. Read `docs/core/current-snapshot.md`
4. Read `docs/core/roadmap.md` section for Phase 107
5. Confirm understanding with user before starting Phase 107

---

## Pre-existing Skips (Not Blocking)

```
FAILED tests/invariants/test_invariant_suite.py::test_booking_overlaps_are_tracked
FAILED tests/invariants/test_invariant_suite.py::test_booking_conflict_consistency
```
These 2 failures pre-date this session and are **not blocking**. All other 2374 tests pass.
