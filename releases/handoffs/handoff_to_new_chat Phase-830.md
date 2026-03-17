> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 830 → Phase 831+

**Date:** 2026-03-17
**Last Closed Phase:** 830 — System Re-Baseline + Data Seed + Zero-State Reset
**Next Phase:** 831 — Prove Manual Booking Intake E2E

---

## System State — True Zero

The system is at **true zero-state**. All data tables are empty (0 rows):

| Table | Rows |
|-------|------|
| properties | 0 |
| booking_state | 0 |
| booking_financial_facts | 0 |
| tasks | 0 |
| ical_connections | 0 |
| tenant_permissions | 0 |
| event_log | 0 |
| All other tables | 0 |

This is intentional. The next chat should begin intake proofs from scratch, like a new customer.

---

## What Was Truly Closed in Phase 830

1. **System re-baseline** — Reality audit of all surfaces/wiring/proofs. Every item classified truthfully.
2. **Data seed script** — `src/scripts/seed_demo.py` with 4 modes: `--dry-run`, `--clean`, `--reset-all-test`, `--reset-all-test-dry-run`
3. **Full environment reset** — ~15,543 test rows deleted across 24+ tables. 5 guardrails (env, tenant prefix, dry-run, FK-safe order, post-verification).
4. **Auth login E2E proven** — dev-login → JWT → /auth/me → /bookings → /properties → /worker/tasks (all 200 OK)
5. **Task lifecycle policy locked** — No production delete. CANCELLED + canceled_reason. Hard delete only in dev/demo scripts.
6. **6 schema mismatches found and fixed** — display_name/name, reservation_ref/booking_ref, ack_sla_minutes NOT NULL, guest_deposit_records/cash_deposits, reported_by/reporter_id, check_in/check_out column names.

## What Is Only Surfaced / Wired (Not E2E Proven)

- Property detail tabs (Photos upload, Issues CRUD, Tasks mutation, Audit data flow)
- Checkout 4-step flow (UI exists, deposit_id wiring corrected, not tested with real data)
- Maintenance flow (page exists, photo upload + state reflection not proven)
- Booking intake page (UI exists, API wiring corrected, not tested from zero)
- Cleaner flow (page + tests committed, not proven E2E)
- Welcome dispatch (wired to endpoint, never tested with real delivery)

## What Is Disconnected / Deferred

- `worker_property_assignments` — table doesn't exist yet, intentionally deferred
- Google OAuth — blocked externally (needs Google Cloud setup)
- PMS layer — proven at pipeline level (Phase 812), deferred behind operational core
- Real messaging delivery (LINE/WhatsApp/Telegram) — adapters built, not live

## Open Gaps (from Operational Core)

See `docs/core/work-context.md` Deferred Items section for full list:
- A-1 to A-4 (Property detail gaps)
- B-1 to B-5 (Staff management gaps)
- D-1 to D-7 (Check-in flow gaps)

---

## Next Steps (Phase 831+)

The next chat should execute the intake proof sequence on a zero-state system:

```
Phase 831 — Create first property via API → verify it appears
Phase 832 — Create first manual booking → verify booking_state + financial_facts
Phase 833 — Connect iCal → pull bookings → verify auto-import
Phase 834 — Verify task auto-generation from bookings
Phase 835+ — Continue per roadmap toward "One Property, End-to-End" checkpoint
```

### Critical rules for next chat

1. **Start from zero** — do NOT assume any data exists
2. **No fixes "on the way"** — every fix must be a numbered phase
3. **Prove, don't assume** — if it hasn't been tested E2E, it's not proven
4. **Schema truth** — always check actual DB schema before writing code
5. **Task lifecycle** — no hard deletes in production flows

---

## Key Files

| File | Purpose |
|------|---------|
| `docs/core/BOOT.md` | Start here — authority rules + closure protocol |
| `docs/core/current-snapshot.md` | Current system state |
| `docs/core/work-context.md` | Active objectives + deferred items |
| `src/scripts/seed_demo.py` | Seed + reset script (4 modes, 5 guardrails) |
| `src/api/session_router.py` | Dev login endpoint (/auth/dev-login) |
| `src/main.py` | FastAPI entry point (uvicorn main:app) |
| `.env` | Environment variables (SUPABASE_URL, keys, etc.) |

## Environment

- FastAPI runs from `src/` directory: `cd src && uvicorn main:app --reload --port 8000`
- Frontend: `cd ihouse-ui && npm run dev` (port 3001 or 8001)
- `.env` is at project root, must be sourced before running scripts
- Supabase project: `reykggmlcehswrxjviup`
