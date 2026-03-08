# Handoff to New Chat — Phase 67 Complete

## Context Limit Notice

Context at ~80%. Handoff written per `docs/core/BOOT.md` protocol (lines 97-103).

---

## Status

Phase 67 — Financial Facts Query API is **CLOSED**.
Next: **Phase 68 — TBD** (see `future-improvements.md` → Active Backlog).

---

## What Was Built in This Session (Phases 65 Closure → 67)

### Repo Cleanup (no phase number)
- Created `releases/phase-zips/` — 45+ ZIP archives moved from root
- Created `releases/handoffs/` — all handoff files moved from root
- Created `releases/README.md`
- Updated `docs/core/BOOT.md` — ZIP and handoff protocols updated to new paths

### Phase 66 — booking_financial_facts Supabase Projection
- **Table:** `booking_financial_facts` (append-only, RLS, 2 indexes)
- **New:** `src/adapters/ota/financial_writer.py` — best-effort, non-blocking writer
- **Modified:** `src/adapters/ota/service.py` — calls financial_writer after BOOKING_CREATED APPLIED
- **Tests:** `tests/test_financial_writer_contract.py` — 16 contract tests
- **Result:** 388 passed, 2 skipped

### Phase 67 — Financial Facts Query API
- **New:** `src/api/financial_router.py` — `GET /financial/{booking_id}`
  - JWT auth (`Depends(jwt_auth)`), tenant isolation (`.eq("tenant_id", ...)`)
  - Returns most-recent row, `404` if not found, `500` on error (no internals leaked)
  - **NEVER touches `booking_state`**
- **Modified:** `src/main.py` — `financial` tag + router registered
- **Tests:** `tests/test_financial_router_contract.py` — 8 contract tests
- **Result:** 396 passed, 2 skipped

---

## Locked Invariants (Never Change)

1. **`booking_state` must never contain financial data** (locked Phase 62+)
2. **`financial_facts` lives on `NormalizedBookingEvent` + `booking_financial_facts` table** — never in `CanonicalEnvelope`
3. **`apply_envelope` is the sole write authority for canonical state** (locked from early phases)
4. **`MODIFY` events → deterministic reject-by-default** (locked Phase 25)
5. **`booking_id = {source}_{reservation_ref}`** (locked Phase 36)
6. **`canon-event-architecture.md`, `vision.md`, `system-identity.md`** are read-only

---

## Test Counts

| Phase | Tests |
|-------|-------|
| 65 (baseline) | 372 passed, 2 skipped |
| 66 (financial writer) | 388 passed, 2 skipped |
| 67 (financial API) | **396 passed, 2 skipped** |

---

## Repository

Branch: `checkpoint/supabase-single-write-20260305-1747`
Last commit: `e76e1da` — "Phase 67 — Financial Facts Query API"

---

## Supabase

Project URL: `https://reykggmlcehswrxjviup.supabase.co`
Tables: `event_log`, `booking_state`, `ota_dead_letter`, `booking_financial_facts`

---

## What's in `future-improvements.md` — Top Candidates for Phase 68

| Item | Status | Priority |
|------|--------|----------|
| Event Time vs System Time Separation | deferred | medium |
| BOOKING_AMENDED Support | open (4/10 prerequisites) | medium |
| DLQ Controlled Replay | open | high |
| booking_id Stability | open | medium |
| OTA Schema/Semantic Normalization | deferred | medium |

Suggested Phase 68: **DLQ Controlled Replay** (high priority, DLQ infrastructure already exists from Phase 38).

---

## Next Chat Boot Instructions

1. Read `docs/core/BOOT.md`
2. Read `docs/core/current-snapshot.md`
3. Read `docs/core/system-identity.md` (read-only, understand locked invariants)
4. Confirm Phase 67 closed, ask user what Phase 68 direction they want

No unresolved issues. No broken tests. System is stable.
