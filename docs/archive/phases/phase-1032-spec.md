# Phase 1032 — Live Staging Proof + Baton-Transfer Closure

**Status:** Closed
**Prerequisite:** Phase 1031 (Assignment Priority Normalization & Canonical Lane Protection)
**Date Closed:** 2026-03-31
**Branch:** `checkpoint/supabase-single-write-20260305-1747`
**Commits:** `fb5b3ea` → `6eedbda` → `a414a8c`

## Goal

Close all deferred live-flow proofs from Phases 1030/1031 by running them on the real staging
environment (Vercel + Railway + Supabase). During the proof pass, two source-of-truth gaps were
found and fixed before the proofs were declared done: a trigger race blocking atomic baton-transfer
promotions, a 500 on the `POST /staff/assignments` existing-row upsert path, and a missing
`GET /permissions/me` endpoint that silently caused the worker promotion banner to never render.

## Invariant (if applicable)

- **INV-1010 (extended):** Baton-transfer may only move PENDING tasks. ACKNOWLEDGED and IN_PROGRESS
  tasks must not move. Atomic promotion of Backup→Primary is guarded by `fn_guard_assignment_priority_uniqueness`
  (UPDATE operations are now exempt from the collision check).
- **INV-1032-A:** The `POST /staff/assignments` upsert path must always write an explicit `priority`
  value. NULL priority is not a valid operational state. Idempotent for existing rows; lane-aware
  computed value for new rows.
- **INV-1032-B:** `GET /permissions/me` is the canonical self-lookup for `comm_preference` including
  `_promotion_notice`. The worker home page MUST call this endpoint (not `/permissions/{user_id}`)
  to render the promotion banner.

## Design / Files

| File | Change |
|------|--------|
| `src/api/permissions_router.py` | MODIFIED — added `GET /permissions/me` endpoint (self-lookup, JWT sub extraction); added `Request` to FastAPI imports; fixed upsert payload to always include `priority` |
| `migrations/phase_1032_baton_transfer_trigger_fix.sql` | NEW — exempts UPDATE operations from collision guard in `fn_guard_assignment_priority_uniqueness` |

## Staging Proofs Confirmed

| Proof | Method | Result |
|-------|--------|--------|
| Baton-transfer E2E | API + DB query | KPG-500 CLEANING: Joey→Backup, แพรวา→Primary. DB confirmed. |
| Promotion notice JSONB write | DB query | `comm_preference._promotion_notice` present, `acknowledged: false` |
| `GET /permissions/me` live | `curl` / Python | HTTP 200, returns notice |
| Worker promotion banner | Browser screenshot | ⭐ "You are now the Primary Worker" rendered at `/worker` |
| `POST /staff/assignments` existing-row | Python requests | HTTP 201 (was 500 before fix) |

## Final Staging State

Caused by proof pass — not a test artifact. This is the real live state:

- **KPG-500 CLEANING lane:** แพรวา = Primary (priority=1), Joey = Backup (priority=2)

## Open Items (Not Blocking Closure)

| Item | Status | Notes |
|------|--------|-------|
| Promotion notice acknowledgement PATCH | Not built | Worker can see banner; dismiss → `acknowledged: true` not wired |
| KPG-500 legacy task distribution (7 Backup / 2 Primary) | Pre-guard artifact | Not a current write-path failure; tasks were assigned before trigger enforcement |
| Amendment reschedule healing for already-assigned tasks | Deferred | Only NULL-assignment healing is built; misassigned task healing is future work |

## Result

All three blocking items confirmed live on staging. Phase 1032 closed.
No test suite changes in this phase (code changes were API-only and backend-only;
existing 7,975 passing tests remain green).
