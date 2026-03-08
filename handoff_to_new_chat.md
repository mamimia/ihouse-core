# iHouse Core — Handoff to New Chat

**Date:** 2026-03-08  
**Reason:** Context approaching ~80% — clean handoff per BOOT.md protocol.

---

## Current System State

| | |
|---|---|
| **Current Phase** | Phase 64 — Enhanced Health Check (CLOSED) |
| **Last Commit** | see `git log --oneline -1` |
| **Test Count** | 320 passed, 2 skipped |
| **Branch** | `checkpoint/supabase-single-write-20260305-1747` |

---

## What Was Built This Session (Phases 60–64)

| Phase | Feature | Tests |
|-------|---------|-------|
| 60 | Request logging middleware — `X-Request-ID`, duration, status | 299 |
| 61 | JWT auth — `verify_jwt`, `tenant_id` from `sub` claim | 307 |
| 62 | Per-tenant rate limiting — sliding window, 429 + `Retry-After` | 313 |
| 63 | OpenAPI docs — `BearerAuth` scheme, response schemas, `/docs` | 313 |
| 64 | Enhanced health check — Supabase ping, DLQ count, 503 support | 320 |

---

## Next Phase: Phase 65 — Financial Data Foundation

**This is the most important next step.** Read the planning note:
> `docs/core/improvements/future-improvements.md` → Section "Financial Model Foundation"

### What Phase 65 does:
1. Add financial field extraction to all 5 OTA adapters (already normalizing payloads but discarding financial fields)
2. Define `BookingFinancialFacts` dataclass — immutable, validated  
3. Add `source_confidence: FULL | PARTIAL | ESTIMATED` per provider
4. **NOT** writing to any DB table yet — dataclass only

### Key invariant (LOCKED from Phase 61):
> `booking_state` is an operational read model only.  
> It must **NEVER** contain financial calculations, payout amounts, commission, or owner-net values.

### Provider financial fields to extract:

| Provider | Available Fields |
|----------|-----------------|
| Booking.com | `total_price`, `currency`, `commission`, `net` |
| Expedia | `total_amount`, `commission_percent` |
| Airbnb | `payout_amount`, `booking_subtotal`, `taxes` |
| Agoda | `selling_rate`, `net_rate` |
| Trip.com | `order_amount`, `channel_fee` |

---

## Key Files — API Layer (New This Session)

| File | Role |
|------|------|
| `src/api/auth.py` | JWT verification dependency |
| `src/api/rate_limiter.py` | Per-tenant rate limiter |
| `src/api/health.py` | Health check logic (Supabase + DLQ) |
| `src/schemas/responses.py` | OpenAPI Pydantic response models |
| `src/api/webhooks.py` | `POST /webhooks/{provider}` — now with JWT + rate limit + OpenAPI |
| `src/main.py` | FastAPI entrypoint — all middleware + routes |

---

## Environment Variables (Important)

| Var | Default | Effect |
|-----|---------|--------|
| `IHOUSE_JWT_SECRET` | unset | dev-mode JWT bypass → `"dev-tenant"` |
| `IHOUSE_WEBHOOK_SECRET_{PROVIDER}` | unset | dev-mode sig skip |
| `IHOUSE_RATE_LIMIT_RPM` | 60 | req/min per tenant, 0 = disabled |
| `SUPABASE_URL` | required | Supabase project URL |
| `SUPABASE_KEY` | required | Supabase anon key |
| `IHOUSE_ENV` | `"development"` | health response label |

---

## How to Start Next Chat

1. Read BOOT.md: `docs/core/BOOT.md`
2. Read this file
3. Read `docs/core/current-snapshot.md`
4. Read `docs/core/improvements/future-improvements.md` (Financial Model Foundation section)
5. Start with: "Phase 65 — Financial Data Foundation"

---

## Test Run Command

```bash
PYTHONPATH=src python -m pytest --ignore=tests/invariants --ignore=tests/test_booking_amended_e2e.py -q
# Expected: 320 passed, 2 skipped
```
