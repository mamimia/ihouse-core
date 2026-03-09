# Phase 131 — DLQ Inspector

**Status:** Closed
**Prerequisite:** Phase 130 (Properties Summary Dashboard)
**Date Closed:** 2026-03-09

## Goal

Phase 127 (Integration Health Dashboard) showed per-provider DLQ counts.
Phase 131 gives operators deep inspection of individual DLQ entries —
entry-level triage for debugging integration failures and manual replays.

## Endpoints

### `GET /admin/dlq?source=&status=&limit=`

Lists DLQ entries with filtering.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | - | Filter by OTA provider |
| `status` | `pending`\|`applied`\|`error`\|`all` | `all` | Filter by derived status |
| `limit` | int 1–100 | 50 | Max rows |

**Status derivation:**
- `pending` — `replay_result` is null
- `applied` — `replay_result` in `{APPLIED, ALREADY_APPLIED, ALREADY_EXISTS, ALREADY_EXISTS_BUSINESS}`
- `error` — `replay_result` not null and not in applied set

**Response:**
```json
{
  "total": 3,
  "status_filter": "pending",
  "source_filter": "airbnb",
  "entries": [
    {
      "envelope_id": "env_abc",
      "source": "airbnb",
      "replay_result": null,
      "status": "pending",
      "error_reason": null,
      "created_at": "...",
      "replayed_at": null,
      "payload_preview": "{\"booking_id\":\"bk_..."
    }
  ]
}
```

### `GET /admin/dlq/{envelope_id}`

Single entry with **full `raw_payload`** (not truncated).

```json
{
  ...all list fields...,
  "raw_payload": "{full JSON here}"
}
```

## Design Decisions

- **No new table.** Reads `ota_dead_letter` only.
- **status is derived in Python** from `replay_result` field (not stored).
- **payload_preview** in list: first 200 chars. Full payload in single-entry only.
- **Global read** — `ota_dead_letter` is not tenant-scoped.
- **JWT required** (admin surface). Zero write-path changes.
- **Over-fetch then filter**: query `limit*3` rows, filter by status in Python.
  This is correct for the expected DLQ sizes (not a high-volume table).

## Files Changed

| File | Change |
|------|--------|
| `src/api/dlq_router.py` | NEW — GET /admin/dlq, GET /admin/dlq/{envelope_id} |
| `src/main.py` | MODIFIED — register router |
| `tests/test_dlq_router_contract.py` | NEW — 44 tests |

## Result

**3317 tests pass** (2 pre-existing SQLite guard failures, unrelated).
