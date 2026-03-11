# Phase 250 — Booking.com Content API Adapter (Outbound)

**Status:** Closed
**Prerequisite:** Phase 248 (Task Templates)
**Date Closed:** 2026-03-11

## Goal

Allow operators to push property content (name, description, address,
amenities, photos, check-in/out times, cancellation policy) to Booking.com
Partner API. Includes dry_run mode for validation without live HTTP.

## New Files

| File | Type | Description |
|------|------|-------------|
| `src/adapters/outbound/bookingcom_content.py` | NEW | Pure payload builder + PushResult + push_property_content |
| `src/api/content_push_router.py` | NEW | POST /admin/content/push/{property_id} |
| `tests/test_content_push_contract.py` | NEW | 32 contract tests (8 groups) |
| `src/main.py` | MODIFIED | Registered content_push_router |

## Endpoint

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/admin/content/push/{property_id}` | Push content to Booking.com |

### Query params
- `dry_run=true` — validate payload without sending HTTP

### Required body fields
- `bcom_hotel_id` or `external_id`, `name`, `address`, `city`, `country_code`

### Optional fields
- `description`, `star_rating`, `amenities`, `photos`, `check_in_time`, `check_out_time`, `cancellation_policy_code`

## Architecture

```
content_push_router.py
     └── bookingcom_content.push_property_content()
              ├── build_content_payload()   (pure — no network)
              └── HTTP PUT → Booking.com Partner API
                   returns PushResult (frozen dataclass)
```

## Result

**~5,820 tests pass. 0 failures. Exit 0.**
32 new contract tests across 8 groups.
