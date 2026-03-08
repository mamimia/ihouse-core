# iHouse Core — Work Context

## Current Active Phase

Phase 76 — occurred_at vs recorded_at Separation (closed)

## Last Closed Phase

Phase 76 — occurred_at vs recorded_at Separation

## Current Objective

Phase 77 — TBD.
See `docs/core/improvements/future-improvements.md` → Active Backlog.

## Key Invariants (Locked — Do Not Change)

- `apply_envelope` is the single write authority — no adapter reads/writes booking_state directly
- `event_log` is append-only
- `booking_id = "{source}_{reservation_ref}"` — deterministic, canonical (Phase 36)
- `reservation_ref` is normalized by `normalize_reservation_ref()` before use (Phase 68)
- HTTP endpoint routes through `ingest_provider_event` → pipeline → `IngestAPI.append_event` → `CoreExecutor.execute` → `apply_envelope`
- `tenant_id` comes from verified JWT `sub` claim, NOT from payload body (Phase 61+)
- `booking_state` is an operational read model ONLY — must never contain financial calculations (Phase 62+ invariant)

## Key Files — Booking Identity Layer (Phase 68)

| File | Role |
|------|------|
| `src/adapters/ota/booking_identity.py` | `normalize_reservation_ref(provider, raw_ref)` + `build_booking_id(source, ref)` |

## Key Files — HTTP API Layer (Phases 58–64)

| File | Role |
|------|------|
| `src/main.py` | FastAPI app entrypoint |
| `src/api/webhooks.py` | `POST /webhooks/{provider}` |
| `src/api/auth.py` | JWT auth dependency |
| `src/api/rate_limiter.py` | Per-tenant rate limiting |
| `src/api/health.py` | Dependency health checks (Phase 64) |
| `src/api/financial_router.py` | `GET /financial/{booking_id}` (Phase 67) |
| `src/schemas/responses.py` | OpenAPI Pydantic response models (Phase 63) |

## Environment Variables

| Var | Default | Effect |
|-----|---------|--------|
| `IHOUSE_WEBHOOK_SECRET_{PROVIDER}` | unset | dev-mode sig skip |
| `IHOUSE_JWT_SECRET` | unset | dev-mode JWT skip → "dev-tenant" |
| `IHOUSE_RATE_LIMIT_RPM` | 60 | req/min per tenant, 0 = disabled |
| `IHOUSE_ENV` | "development" | health response label |
| `SUPABASE_URL` | required | Supabase project URL |
| `SUPABASE_KEY` | required | Supabase anon key |
| `PORT` | 8000 | uvicorn port |

## Tests

431 passing (2 pre-existing SQLite skips, unrelated)

