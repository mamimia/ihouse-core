# Phase 189 — Booking Mutation Audit Events

**Opened:** 2026-03-10  
**Closed:** 2026-03-10  
**Status:** ✅ Closed

## Goal

Add actor attribution to every operator/worker-facing mutation endpoint by writing to a new append-only `audit_events` table. Prerequisite for the Manager UI activity feed (Phase 190).

## Invariant

> `audit_events` tracks *who did what in the UI*.  
> `event_log` tracks *what happened to the booking* (OTA/system domain events).  
> These are completely orthogonal — no duplication.

## Mutation surfaces instrumented

| Endpoint | Action logged |
|----------|--------------|
| `PATCH /worker/tasks/{id}/acknowledge` | `TASK_ACKNOWLEDGED` |
| `PATCH /worker/tasks/{id}/complete` | `TASK_COMPLETED` |
| `PATCH /bookings/{id}/flags` | `BOOKING_FLAGS_UPDATED` |

## New files

| File | Purpose |
|------|---------|
| `src/services/audit_writer.py` | Best-effort writer — catches all exceptions, logs to stderr, never re-raises |
| `src/api/audit_router.py` | `GET /admin/audit` — tenant-isolated, ordered by `occurred_at DESC` |
| `tests/test_audit_events_contract.py` | 15 contract tests (Groups A, B, C) |

## Modified files

| File | Change |
|------|--------|
| `src/api/worker_router.py` | `_transition_task()` — injects `write_audit_event` in best-effort try/except after successful DB update |
| `src/api/bookings_router.py` | `patch_booking_flags()` — injects `write_audit_event` after successful upsert |
| `src/main.py` | Registers `audit_router` + adds `audit` tag to OpenAPI |

## Supabase migration

`20260310_phase189_audit_events.sql`  
Table: `public.audit_events` — BIGSERIAL PK, append-only, RLS: service_role only.  
Indexes: `ix_audit_events_entity`, `ix_audit_events_actor`.

## Test results

```
tests/test_audit_events_contract.py  ...............  (15 passed)

Full suite exits 0 — pre-existing webhook baseline failures unchanged.
```

## Design notes

- `actor_id = JWT sub` (= `tenant_id`) for Phase 189. Phase 190 will wire a proper `user_id` claim from the permissions layer.
- `audit_writer` double-wrapped: its own internal try/except + an outer guard in the caller router, so a mocked side_effect in tests also cannot break the request response.
- `GET /admin/audit` supports `entity_type`, `entity_id`, `actor_id` filters — enough for the Manager UI "activity feed per booking" and "what did actor X do" views.
