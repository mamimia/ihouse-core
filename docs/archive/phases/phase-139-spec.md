# Phase 139 — Real Outbound Adapters
**Spec version:** 1.0
**Status:** Closed ✅
**Date:** 2026-03-10
**Commit:** `fb6de78`

---

## Objective

Replace the Phase 138 dry-run stub adapters (`ApiFirstAdapter`, `ICalAdapter`) with
real provider-specific adapter implementations, and wire them into the
`outbound_executor.py` dispatch loop via a new adapter registry.

---

## New Files

| File | Role |
|------|------|
| `src/adapters/outbound/__init__.py` | `OutboundAdapter` ABC + `AdapterResult` dataclass |
| `src/adapters/outbound/airbnb_adapter.py` | Airbnb — `POST /v2/calendar_operations` |
| `src/adapters/outbound/bookingcom_adapter.py` | Booking.com — `POST /v1/hotels/availability-blocks` |
| `src/adapters/outbound/expedia_vrbo_adapter.py` | Expedia + VRBO — shared Partner Solutions API |
| `src/adapters/outbound/ical_push_adapter.py` | Hotelbeds / TripAdvisor / Despegar — `PUT *.ics` |
| `src/adapters/outbound/registry.py` | `build_adapter_registry()` — provider → adapter mapping |
| `tests/test_outbound_adapters_contract.py` | 40 contract tests for all adapters + registry |

## Modified Files

| File | Change |
|------|--------|
| `src/services/outbound_executor.py` | Upgraded to look up real adapters via registry; Phase 138 stubs kept as fallback for unknown providers |

---

## Adapter Contract

All adapters implement:

```python
class OutboundAdapter:
    provider: str
    strategy: str  # "api_first" | "ical_fallback"

    def send(self, external_id, booking_id, rate_limit=60, dry_run=False) -> AdapterResult: ...
    def push(self, external_id, booking_id, rate_limit=60, dry_run=False) -> AdapterResult: ...
```

### AdapterResult Fields

| Field | Type | Notes |
|-------|------|-------|
| `provider` | str | Provider name |
| `external_id` | str | OTA listing/property ID |
| `strategy` | str | `api_first` or `ical_fallback` |
| `status` | str | `ok`, `failed`, `dry_run` |
| `http_status` | int? | HTTP status from OTA, if called |
| `message` | str | Human description |

---

## Adapter Details

### Tier A — API First

| Adapter | Endpoint | Env Vars |
|---------|----------|----------|
| `AirbnbAdapter` | `POST {AIRBNB_API_BASE}/v2/calendar_operations` | `AIRBNB_API_KEY`, `AIRBNB_API_BASE` |
| `BookingComAdapter` | `POST {BOOKINGCOM_API_BASE}/v1/hotels/availability-blocks` | `BOOKINGCOM_API_KEY`, `BOOKINGCOM_API_BASE` |
| `ExpediaVrboAdapter` | `POST {EXPEDIA_API_BASE}/v1/properties/{id}/availability` | `EXPEDIA_API_KEY`, `EXPEDIA_API_BASE` |

### Tier B — iCal Fallback

| Adapter | Endpoint | Env Vars |
|---------|----------|----------|
| `ICalPushAdapter (hotelbeds)` | `PUT {HOTELBEDS_ICAL_URL}/{external_id}.ics` | `HOTELBEDS_ICAL_URL`, `HOTELBEDS_API_KEY` |
| `ICalPushAdapter (tripadvisor)` | `PUT {TRIPADVISOR_ICAL_URL}/{external_id}.ics` | `TRIPADVISOR_ICAL_URL` |
| `ICalPushAdapter (despegar)` | `PUT {DESPEGAR_ICAL_URL}/{external_id}.ics` | `DESPEGAR_ICAL_URL` |

---

## Dry-Run Logic (enforced in all adapters)

1. If required env vars absent → `status=dry_run` (no HTTP call)
2. If `IHOUSE_DRY_RUN=true` → `status=dry_run` (no HTTP call)
3. If `dry_run=True` argument → `status=dry_run` (no HTTP call)
4. Otherwise: make real HTTP call, return `ok` or `failed`

---

## Executor Integration

```python
# outbound_executor.py — execute_sync_plan()
use_registry = _ADAPTER_REGISTRY_AVAILABLE and api_adapter is None and ical_adapter is None

if use_registry:
    adapter = _build_registry().get(action.provider)  # returns None for unknown providers
    if adapter is not None:
        ar = adapter.send(...)  # or .push()
        result = ExecutionResult(...)
    else:
        result = _api_cls.send(...)  # fall back to Phase 138 stub
```

Phase 138 stub adapters are retained for unknown providers and for tests
that inject custom adapter classes (`api_adapter=` / `ical_adapter=` params).

---

## Registry

`build_adapter_registry()` returns:

```python
{
    "airbnb":      AirbnbAdapter(),
    "bookingcom":  BookingComAdapter(),
    "expedia":     ExpediaVrboAdapter(provider="expedia"),
    "vrbo":        ExpediaVrboAdapter(provider="vrbo"),
    "hotelbeds":   ICalPushAdapter(provider="hotelbeds"),
    "tripadvisor": ICalPushAdapter(provider="tripadvisor"),
    "despegar":    ICalPushAdapter(provider="despegar"),
}
```

---

## Test Results

40 contract tests — `tests/test_outbound_adapters_contract.py`:
- Per adapter: `dry_run` (no creds), `dry_run` (IHOUSE_DRY_RUN), `ok` (200/204), `failed` (4xx), `failed` (network exc), field propagation
- Registry: all 7 providers present, correct types, provider attribute set

Full suite: **3573 passed**, 2 failed (pre-existing SQLite guards), 3 skipped.
