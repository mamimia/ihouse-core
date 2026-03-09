# Handoff to New Chat — Phase 131 Complete

**Prepared by:** Antigravity (current chat)
**Date:** 2026-03-09
**Reason:** Context at ~80%+ — protocol-mandated handoff.

---

## System State Summary

| Key | Value |
|-----|-------|
| Last Closed Phase | **Phase 131 — DLQ Inspector** |
| Test Count | **3,317 passing** (2 pre-existing SQLite guard failures — unrelated, never fix) |
| DB Schema | **No changes since Phase 114** (tasks table) |
| Branch | `checkpoint/supabase-single-write-20260305-1747` |
| Next Phase | **Phase 132** |

---

## What Was Done in This Chat Session (Phases 128–131)

### Phase 128 — Conflict Center ✅
- `src/api/conflicts_router.py` — NEW
- `GET /conflicts?property_id=` — tenant-scoped active booking overlap detection
- `itertools.combinations` per property · CRITICAL(≥3 nights) / WARNING(1-2) · pair dedup (booking_a < booking_b)
- Summary: total_conflicts / properties_affected / bookings_involved
- 39 tests · JWT required · check_out exclusive · reads booking_state only

### Phase 129 — Booking Search Enhancement ✅
- `src/api/bookings_router.py` — MODIFIED (enhanced GET /bookings)
- New filter: `source` (OTA provider)
- New range: `check_out_from` / `check_out_to`
- New sort: `sort_by` (check_in|check_out|updated_at|created_at) + `sort_dir` (asc|desc)
- Response echoes `sort_by` and `sort_dir`
- 31 tests · backward compatible

### Phase 130 — Properties Summary Dashboard ✅
- `src/api/properties_summary_router.py` — NEW
- `GET /properties/summary?limit=` — per-property portfolio view
- Per-property: active_count, canceled_count, next_check_in, next_check_out, has_conflict
- Portfolio: total_active_bookings, total_canceled_bookings, properties_with_conflicts
- Sorted by property_id · limit 1–200 (default 100) · JWT required
- 37 tests

### Phase 131 — DLQ Inspector ✅
- `src/api/dlq_router.py` — NEW
- `GET /admin/dlq?source=&status=&limit=` — list ota_dead_letter entries
- `GET /admin/dlq/{envelope_id}` — single entry with full raw_payload
- Status derived: null→pending · APPLIED/ALREADY_APPLIED/…→applied · other→error
- payload_preview = first 200 chars (list); full payload on single entry
- 44 tests · JWT required · global (not tenant-scoped)

---

## Files Added / Modified This Session

| File | Status |
|------|--------|
| `src/api/conflicts_router.py` | NEW (Phase 128) |
| `src/api/bookings_router.py` | MODIFIED (Phase 129) |
| `src/api/properties_summary_router.py` | NEW (Phase 130) |
| `src/api/dlq_router.py` | NEW (Phase 131) |
| `src/main.py` | MODIFIED — routers registered for 128, 130, 131 |
| `tests/test_conflicts_router_contract.py` | NEW (39 tests) |
| `tests/test_booking_search_contract.py` | NEW (31 tests) |
| `tests/test_properties_summary_router_contract.py` | NEW (37 tests) |
| `tests/test_dlq_router_contract.py` | NEW (44 tests) |
| `docs/archive/phases/phase-128-spec.md` | NEW |
| `docs/archive/phases/phase-129-spec.md` | NEW |
| `docs/archive/phases/phase-130-spec.md` | NEW |
| `docs/archive/phases/phase-131-spec.md` | NEW |
| `docs/core/work-context.md` | UPDATED |
| `docs/core/current-snapshot.md` | UPDATED |
| `docs/core/phase-timeline.md` | APPENDED (Phases 115–131) |
| `docs/core/construction-log.md` | APPENDED (Phases 122–131) |
| `releases/phase-zips/iHouse-Core-Docs-Phase-128.zip` | NEW |
| `releases/phase-zips/iHouse-Core-Docs-Phase-129.zip` | NEW |
| `releases/phase-zips/iHouse-Core-Docs-Phase-130.zip` | NEW |
| `releases/phase-zips/iHouse-Core-Docs-Phase-131.zip` | NEW |

---

## Key Locked Invariants (READ ONLY — NEVER CHANGE)

1. **`apply_envelope`** is the ONLY function allowed to write to `booking_state` or `event_log`.
2. All new API endpoints are **read-only** (no writes to any table).
3. **check_out dates are exclusive** (half-open interval [check_in, check_out)).
4. **JWT auth** required on all `/bookings/*`, `/conflicts`, `/properties/*`, `/admin/*`, `/availability/*`, `/integration-health` endpoints.
5. **`ota_dead_letter`** is global (not tenant-scoped). DLQ reads must NOT filter by tenant_id.
6. The 2 SQLite guard failures in `tests/invariants/test_invariant_suite.py` are **pre-existing and intentional**. Do NOT fix them.
7. Pyre2 lint errors for "Could not find import of fastapi..." are **false positives** — PYTHONPATH issue with Pyre2. Tests pass fine. Do NOT change import structure.

---

## What Is Next (Phase 132+)

Remaining open items from `docs/core/improvements/future-improvements.md`:

### Most actionable without DB migrations:
1. **OTA Reconnection / Retry Monitor** — `GET /admin/buffer` — inspect `ota_ordering_buffer` entries (similar to DLQ Inspector but for buffered events)
2. **Booking Timeline / Audit Trail** — `GET /bookings/{id}/history` — event_log chain for a single booking
3. **Amendment History** — `GET /bookings/{id}/amendments` — BOOKING_AMENDED events from event_log for a booking
4. **Upcoming Arrivals** — `GET /arrivals?days=7` (can be done with existing GET /bookings but a dedicated surface may have value)

### Requires DB migration (new table):
5. **Guest Pre-Arrival / Check-In Intake** — new `guest_intake` table; POST + GET /intake/{booking_id}

### Deferred / blocked:
- OTA Reconciliation / Recovery Layer (partially done in Phase 110)
- Event Time vs System Time Separation (architectural)
- Idempotency Monitoring

**Recommended Phase 132:** `GET /bookings/{id}/history` — booking audit trail from event_log. Clean read-only, no new table, direct operational value.

---

## How to Start the New Chat

1. Read `docs/core/BOOT.md` (you will find it instructs you to read Layer A → governance → snapshot → work-context → live-system → phase-timeline → construction-log).
2. Start with: "Current phase: Phase 132 (open). Last closed: Phase 131 (DLQ Inspector). 3,317 tests passing."
3. Run `PYTHONPATH=src .venv/bin/pytest tests/ --tb=no -q` to confirm green before starting work.
4. Check `docs/core/improvements/future-improvements.md` for next phase selection.

---

## Supabase Project

Supabase MCP was **not available** in this chat session (unauthorized token). All DB work was done via existing migrations. The Supabase project connection string and keys are in `.env` (not committed). Use `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` env vars.

---

## Git State

Branch: `checkpoint/supabase-single-write-20260305-1747`
All phases 128–131 committed. No uncommitted changes expected after this handoff.
