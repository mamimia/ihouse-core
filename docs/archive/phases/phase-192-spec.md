# Phase 192 — Guest Profile Foundation

**Opened:** 2026-03-10
**Closed:** 2026-03-10
**Status:** ✅ Closed

## Goal

Standalone guest identity table and CRUD API. Reference data — completely outside the canonical event spine (`event_log` / `booking_state` / `apply_envelope` untouched).

> **Distinction from Phase 159 `guest_profile`:** Phase 159 is a read-only booking-linked PII extraction from OTA payloads. Phase 192 `guests` is a first-class operator-managed identity record.

## New / modified files

| File | Change |
|------|--------|
| Supabase migration `create_guests_table` | NEW — DDL + RLS |
| `src/api/guests_router.py` | NEW — POST / GET list / GET by id / PATCH |
| `src/main.py` | + `guests_router` registration |
| `tests/test_guests_router_contract.py` | NEW — 18 tests |

## Table DDL

```sql
CREATE TABLE public.guests (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   TEXT NOT NULL,
    full_name   TEXT NOT NULL,
    email       TEXT,
    phone       TEXT,
    nationality TEXT,
    passport_no TEXT,
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Indexes: guests_tenant_id_idx, guests_tenant_email_idx (partial WHERE email IS NOT NULL)
-- RLS: service_role_all policy
```

## Endpoints

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/guests` | `full_name` required; optional: email, phone, nationality, passport_no, notes |
| `GET` | `/guests` | `?search=` (name/email), `?limit=` (1–200, default 200) |
| `GET` | `/guests/{id}` | 404 for unknown + cross-tenant |
| `PATCH` | `/guests/{id}` | Partial update; `updated_at` always refreshed; no DELETE |

## Tests

```
pytest tests/test_guests_router_contract.py -v → 18 passed
Full suite → exit 0, 0 regressions
```
