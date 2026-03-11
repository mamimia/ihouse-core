# Handoff to New Chat — Phase 239

**Date:** 2026-03-11
**Last Phase Closed:** 239 — Platform Checkpoint VII
**Full Test Suite:** ~5,559 tests. 0 failures. Exit 0.

---

## System State Summary

iHouse Core is a multi-tenant property management and OTA integration platform built on **FastAPI + Supabase**. As of Phase 239:

- **238 closed phases** of development
- **15 OTA adapters** (14 unique + ctrip alias): Airbnb, Booking.com, Expedia, Agoda, Trip.com/Ctrip, Traveloka, Vrbo, GVR, MakeMyTrip, Klook, Despegar, Rakuten, Hotelbeds, Hostelworld
- **61 API router files** under `src/api/`
- **171 test files**, ~5,559 individual tests
- **9 Supabase migrations**
- **Staging infrastructure** (docker-compose.staging.yml + 10 integration smoke tests)
- **5 escalation channels**: LINE, WhatsApp, Telegram, SMS, Email
- **AI copilot layer**: Manager Copilot, Worker Copilot, Financial Explainer, Task Recommendation, Guest Messaging Copilot, Anomaly Alert Broadcaster
- **Full outbound sync framework** with iCal + API push capabilities

## Canonical Documentation

| File | Purpose |
|------|---------|
| `docs/core/current-snapshot.md` | Current system state — **start here** |
| `docs/core/construction-log.md` | All 238 phases with file changes |
| `docs/core/phase-timeline.md` | Chronological phase timeline |
| `docs/core/planning/next-15-phases-240-254.md` | **Next roadmap** |
| `docs/core/planning/next-10-phases-229-238.md` | Previous roadmap (completed) |
| `docs/archive/phases/` | 184 individual phase spec files |
| `BOOT.md` | System boot protocol and rules |

## Key Invariants (Never Break)

1. `apply_envelope` is the single write authority — never bypass
2. `event_log` is append-only
3. `booking_id = "{source}_{reservation_ref}"` — deterministic
4. `tenant_id` from JWT `sub` only — NEVER from payload body
5. `booking_state` is read-only view — no financial calculations
6. Financial reads from `booking_financial_facts` ONLY
7. External channels are escalation fallbacks ONLY
8. No global fallback chain — per-worker channel preference

## What Was Done in This Chat (Phases 234–239)

| Phase | What |
|-------|------|
| 234 | Shift & Availability Scheduler — worker_shifts table + 3 endpoints + 18 tests |
| 235 | Multi-Property Conflict Dashboard — /admin/conflicts/dashboard + 21 tests |
| 236 | Guest Communication History — guest_messages_log + POST/GET endpoints + 19 tests |
| 237 | Staging Environment — docker-compose.staging.yml + 10 integration smoke tests |
| 238 | Ctrip/Trip.com Enhanced Adapter — CTRIP- prefix, CNY default, Chinese name fallback, cancel codes + 16 tests |
| 239 | Platform Checkpoint VII — full audit, snapshot fixes, roadmap (240-254) |

## Next Steps for New Chat

**Start with Phase 240 — Booking Financial Reconciliation Dashboard API.**

Full roadmap: `docs/core/planning/next-15-phases-240-254.md`

## Environment

- Python 3.14 + FastAPI + Supabase
- Tests: `PYTHONPATH=src pytest --tb=short -q`
- Staging: `IHOUSE_ENV=staging pytest tests/integration/ -v`
- Deploy: `docker compose up -d`
