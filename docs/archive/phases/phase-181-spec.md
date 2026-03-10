# Phase 181 — SSE Live Refresh

**Status:** Open  
**Prerequisite:** Phase 180 (Roadmap Refresh)  
**Date Opened:** 2026-03-10

## Goal

Replace 30-second polling in `/worker` and `/dashboard` with real-time Server-Sent Events (SSE). Task state changes (acknowledge, complete, new assignment) push immediately to connected clients.

## Design

```
Backend:
  src/channels/sse_broker.py        — in-memory asyncio.Queue broker (per-tenant)
  src/api/sse_router.py             — GET /events/stream (StreamingResponse, text/event-stream)

Trigger points (existing routers emit events):
  src/api/worker_router.py          — publish on acknowledge + complete
  src/tasks/task_writer.py          — publish on write_task (new assignment)

Frontend:
  ihouse-ui/app/worker/page.tsx     — replace setInterval with EventSource
  ihouse-ui/app/dashboard/page.tsx  — add EventSource for task/ops refresh
```

## Event envelope (SSE data payload)

```json
{"type": "task_update", "tenant_id": "t1", "task_id": "T-001", "status": "acknowledged"}
{"type": "task_created", "tenant_id": "t1", "task_id": "T-002"}
{"type": "ping"}
```

## Invariants

- Tenant isolation: each connection only receives events for its own tenant_id.
- Dev-mode compatible: if IHOUSE_JWT_SECRET not set, tenant_id = "dev-tenant".
- No DB changes. Pure in-memory broker (asyncio, single process).
- Keep-alive: `:ping\n\n` comment every 20 seconds — prevents proxy timeout.
- Max 1000 queued events per connection before eviction (memory guard).
- Fail-safe: if SSE stream drops, frontend falls back to 60s polling.

## Result

**TBD.**
