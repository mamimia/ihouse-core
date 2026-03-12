> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 294 → New Chat

**Date:** 2026-03-12
**Last Closed Phase:** 294
**Next Phase:** 295

## System State

- **294 phases** completed (1-294)
- **6,216 tests** passing, 0 failures, exit 0
- **TypeScript:** `tsc --noEmit` → 0 errors (Next.js 16 / React 19)
- **77 API routers** in `src/api/`
- **14 OTA adapters** (inbound), 4 outbound
- **5 escalation channels** (LINE, WhatsApp, Telegram, SMS, Email)
- **8 AI copilot** endpoints + audit trail
- **33 Supabase tables** + 1 view, 29 migrations
- **18 frontend pages** (ihouse-ui/)
- **Brand:** Domaniqo (external), iHouse Core (internal codename)

## This Session's Work (Phases 283-294)

| Phase | Title | Key deliverable |
|-------|-------|----------------|
| 283 | Test Suite Isolation Fix | conftest.py, env var leak fix |
| 284 | Supabase Schema Truth Sync | 5 migrations applied |
| 285 | Documentation Integrity Sync XIV | Canonical docs sync |
| 286 | Production Docker Hardening | deploy_checklist.sh |
| 287 | Frontend Foundation | Root redirect, env example |
| 288 | Operations Dashboard UI | Portfolio grid, 60s auto-refresh |
| 289 | Booking Management UI | 3 API methods + types |
| 290 | Worker Task View UI | Audit confirmed complete |
| 291 | Financial Dashboard UI | OTA mix SVG donut, cashflow API |
| 292 | Platform Checkpoint XIV | Roadmap/snapshot/live-system → 292 |
| 293 | Full Archive Integrity Repair | 59 specs + 292 ZIPs + live-system 4 API sections |
| 294 | History & Config Truth Sync | 22 timeline + 40 construction-log gaps, 11 env vars |

## Canonical Documents (Source of Truth)

| File | Purpose |
|------|---------|
| `docs/core/roadmap.md` | System numbers, completed phases, forward planning |
| `docs/core/current-snapshot.md` | Current phase, system status, env vars, tests |
| `docs/core/live-system.md` | Technical architecture, API surface (100+ endpoints) |
| `docs/core/phase-timeline.md` | Chronological phase actions (now complete, 1-294) |
| `docs/core/construction-log.md` | Build log (now complete, 1-294) |
| `BOOT.md` | Protocol rules, branding, file placement |

## What to Do Next

1. **Read** `BOOT.md` first (protocol rules)
2. **Read** `docs/core/current-snapshot.md` (system state)
3. **Read** `docs/core/roadmap.md` (direction)
4. **Plan** the next 10 phases (295-304) — suggested focus areas:
   - Guest portal frontend
   - Owner portal frontend
   - Multi-tenant org structure
   - Production monitoring consumers
   - ML-based anomaly detection

## Key Invariants (Do Not Break)

- `apply_envelope` is the single write authority
- `event_log` is append-only
- `booking_id = "{source}_{reservation_ref}"`
- `booking_state` is read model only — never financial data
- `tenant_id` from JWT only — never payload body
