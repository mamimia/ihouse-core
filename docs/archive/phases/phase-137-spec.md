# Phase 137 — Outbound Sync Trigger
**Spec version:** 1.0
**Status:** Closed ✅
**Date:** 2026-03-09

---

## Objective

Phase 137 is the strategic junction of the Outbound Sync Layer.

It joins `property_channel_map` (Phase 135) and `provider_capability_registry` (Phase 136)
to produce a deterministic `sync_plan` — a per-channel decision of what outbound
availability update strategy to use for a given booking.

## New Files

| File | Role |
|------|------|
| `src/services/outbound_sync_trigger.py` | Pure strategy resolver (no DB calls) |
| `src/api/sync_trigger_router.py` | HTTP router — reads DB, calls service, returns plan |

## Endpoint

```
POST /internal/sync/trigger
Body: { "booking_id": "bk-airbnb-HZ001" }
Auth: JWT required

200 → sync_plan
404 → booking not found
400 → booking_id missing/empty
403 → JWT missing
500 → DB error
```

## Strategy Resolution Rules (deterministic)

| Condition | Strategy |
|-----------|----------|
| `channel.enabled = false` | skip |
| `channel.sync_mode = disabled` | skip |
| Provider not in registry | skip |
| Tier D | skip |
| `sync_mode=api_first` + `supports_api_write=true` | api_first |
| `sync_mode=api_first` + no write API + has iCal | ical_fallback (degraded) |
| `sync_mode=api_first` + no write + no iCal | skip |
| `sync_mode=ical_fallback` + iCal push or pull | ical_fallback |
| `sync_mode=ical_fallback` + no iCal | skip |

## Response Schema

```json
{
  "booking_id":      "bk-airbnb-HZ001",
  "property_id":     "prop-villa-alpha",
  "tenant_id":       "tenant-001",
  "total_channels":  3,
  "api_first_count": 1,
  "ical_count":      1,
  "skip_count":      1,
  "actions": [
    {
      "provider":    "airbnb",
      "external_id": "HZ12345",
      "strategy":    "api_first",
      "reason":      "sync_mode=api_first and provider supports write API (tier=A).",
      "tier":        "A",
      "rate_limit":  120
    }
  ]
}
```

## Invariants

- **Read-only:** never writes to any table. Only reads from booking_state, property_channel_map, provider_capability_registry.
- **apply_envelope untouched:** this is outbound config, not canonical booking state.
- **Deterministic:** pure function — same inputs → same plan every time.

## Test Results

31/31 contract tests passing ✅ (service + HTTP layers separately)
Full suite: 3503 passed, 2 failed (pre-existing SQLite guards), 3 skipped.
