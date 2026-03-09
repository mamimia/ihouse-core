# Handoff to New Chat — Phase 140 Closed

**Date:** 2026-03-10
**Prepared by:** AI (context at ~80% — switching per BOOT.md protocol)
**Handoff rule:** docs/core/BOOT.md §"Context limit — handoff protocol"

---

## Current Phase
Phase 140 — iCal Date Injection ✅ **CLOSED**

## Last Closed Phase
Phase 140 — iCal Date Injection
- Injected real `check_in`/`check_out` from `booking_state` into iCal VCALENDAR `DTSTART`/`DTEND`.
- Commit: `45fa03f` (code) + `b8f86b9` (docs)

## System Test Count
**3589 passing**, 2 pre-existing SQLite guard failures (unrelated), 3 skipped.

---

## What Was Done in This Session

| Phase | Title | Commit |
|-------|-------|--------|
| 139 | Real Outbound Adapters (Airbnb, BookingCom, Expedia/VRBO, iCal push, registry) | `fb6de78` |
| 140 | iCal Date Injection (real DTSTART/DTEND from booking_state) | `45fa03f` |

---

## Next Objective

**Phase 141 — Rate-Limit Enforcement in Outbound Adapters**

### What it means
The `SyncAction.rate_limit` field (already carried through the full chain) is
currently passed into adapters but **never honoured** — adapters fire immediately
at full speed regardless.

Phase 141 should implement a lightweight token-bucket or sleep-based throttle
so each adapter respects the `rate_limit` (calls/minute) declared by the
Provider Capability Registry.

### Key files to touch
| File | What to do |
|------|-----------|
| `src/adapters/outbound/__init__.py` | Add `_throttle(rate_limit)` helper or a `RateLimiter` class |
| `src/adapters/outbound/airbnb_adapter.py` | Call throttle before HTTP |
| `src/adapters/outbound/bookingcom_adapter.py` | Same |
| `src/adapters/outbound/expedia_vrbo_adapter.py` | Same |
| `src/adapters/outbound/ical_push_adapter.py` | Same |
| `tests/test_rate_limit_enforcement_contract.py` | Contract tests |

### Design constraint
- Must be **opt-out-able in tests** (monkeypatch env or inject a no-op throttle).
- Must not block the synchronous request thread if rate_limit is very low — consider a warning log + best-effort instead of blocking forever.

---

## Key Files (State at Handoff)

### Outbound Sync Layer (Phases 135–140)
| File | Role |
|------|------|
| `src/services/outbound_sync_trigger.py` | `build_sync_plan()` — builds per-channel SyncAction list |
| `src/api/sync_trigger_router.py` | `POST /internal/sync/trigger` — plan only |
| `src/services/outbound_executor.py` | `execute_sync_plan()` — fail-isolated dispatch |
| `src/api/outbound_executor_router.py` | `POST /internal/sync/execute` — plan + execute + date fetch |
| `src/adapters/outbound/__init__.py` | `OutboundAdapter` ABC + `AdapterResult` |
| `src/adapters/outbound/registry.py` | `build_adapter_registry()` — 7 providers |
| `src/adapters/outbound/airbnb_adapter.py` | Airbnb API first |
| `src/adapters/outbound/bookingcom_adapter.py` | Booking.com API first |
| `src/adapters/outbound/expedia_vrbo_adapter.py` | Expedia + VRBO API first |
| `src/adapters/outbound/ical_push_adapter.py` | Hotelbeds + TripAdvisor + Despegar iCal push |
| `src/adapters/outbound/booking_dates.py` | `fetch_booking_dates()` — fail-safe date lookup |
| `migrations/phase_135_property_channel_map.sql` | property_channel_map DDL |
| `migrations/phase_136_provider_capability_registry.sql` | provider_capability_registry DDL |

### Key Invariants (Locked — Do NOT Change)
- `apply_envelope` is the single write authority — adapters never write to booking tables
- `event_log` is append-only
- `booking_id = "{source}_{reservation_ref}"` (Phase 36)
- `tenant_id` comes from verified JWT `sub`, never from payload body
- `booking_state` must never contain financial calculations
- iCal `DTSTART`/`DTEND` fallback to `20260101`/`20260102` when dates are absent

### Environment Variables (outbound adapters)
```
AIRBNB_API_KEY, AIRBNB_API_BASE
BOOKINGCOM_API_KEY, BOOKINGCOM_API_BASE
EXPEDIA_API_KEY, EXPEDIA_API_BASE
HOTELBEDS_ICAL_URL, HOTELBEDS_API_KEY
TRIPADVISOR_ICAL_URL, TRIPADVISOR_API_KEY
DESPEGAR_ICAL_URL, DESPEGAR_API_KEY
IHOUSE_DRY_RUN  (global dry-run override)
```

---

## Pre-Existing Blockers (carry forward)

| Issue | Status |
|-------|--------|
| `test_booking_overlaps_are_tracked` — SQLite failure | Pre-existing, unrelated to outbound work |
| `test_booking_conflict_consistency` — SQLite failure | Same |
| Pyre2 lint errors on adapter imports (PYTHONPATH not in Pyre2 config) | Cosmetic, tests all pass with PYTHONPATH=src |

---

## How to Boot the New Chat

1. Start by reading BOOT.md.
2. Read: `docs/core/current-snapshot.md`, `docs/core/work-context.md`.
3. Read only the **latest two sections** of `docs/core/phase-timeline.md` (Phase 139 + Phase 140).
4. Current objective: **Phase 141 — Rate-Limit Enforcement**.
5. Run: `cd src && PYTHONPATH=src .venv/bin/pytest tests/ --tb=no -q` to confirm 3589 baseline.

---

## Branch
`checkpoint/supabase-single-write-20260305-1747`
