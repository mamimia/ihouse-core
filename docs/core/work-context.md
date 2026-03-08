# iHouse Core — Work Context

## Current Active Phase

Phase 62 — Per-Tenant Rate Limiting (closed)

## Last Closed Phase

Phase 62 — Per-Tenant Rate Limiting

## Current Objective

HTTP API layer complete (phases 58–62). Phase 63 TBD.

## Key Invariants (Locked — Do Not Change)

- `apply_envelope` is the single write authority — no adapter reads/writes booking_state directly
- `event_log` is append-only
- `booking_id = "{source}_{reservation_ref}"` — deterministic, canonical
- HTTP endpoint routes through `ingest_provider_event` → pipeline → `IngestAPI.append_event` → `CoreExecutor.execute` → `apply_envelope`
- `tenant_id` comes from verified JWT `sub` claim, NOT from payload body (Phase 61+)

## Key Files — HTTP API Layer

| File | Role |
|------|------|
| `src/main.py` | FastAPI app entrypoint |
| `src/api/webhooks.py` | `POST /webhooks/{provider}` |
| `src/api/auth.py` | JWT auth dependency |
| `src/api/rate_limiter.py` | Per-tenant rate limiting |

## Environment Variables

| Var | Default | Effect |
|-----|---------|--------|
| `IHOUSE_WEBHOOK_SECRET_{PROVIDER}` | unset | dev-mode sig skip |
| `IHOUSE_JWT_SECRET` | unset | dev-mode JWT skip → "dev-tenant" |
| `IHOUSE_RATE_LIMIT_RPM` | 60 | req/min per tenant, 0 = disabled |
| `IHOUSE_ENV` | "development" | health response label |
| `PORT` | 8000 | uvicorn port |

## Tests

313 passing (2 pre-existing SQLite skips, unrelated)
