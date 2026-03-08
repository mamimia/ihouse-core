# iHouse Core — Work Context

## Current Active Phase

Phase 46 — System Health Check

## Last Closed Phase

Phase 45 — Ordering Buffer Auto-Trigger on BOOKING_CREATED

## Current Objective

Every production SaaS company (Stripe, Twilio, Airbnb) has a single callable that gives operators a complete picture of system health in under a second. Before expanding to new event kinds (BOOKING_AMENDED), iHouse Core needs exactly that.

Build a consolidated `system_health_check()` that verifies every component in the
canonical pipeline: Supabase connectivity, DLQ status, ordering buffer, threshold
alerting — and returns a structured readiness report.

## Why Now

Phase 45 closed the ordering loop. The DLQ, replay, and buffer layers are now complete.

Before adding any new event kind (BOOKING_AMENDED) or going to production:
1. Operators need one call to verify system readiness
2. CI/CD needs a smoke-test function it can invoke
3. SREs need a structured report to diagnose issues in seconds

## Scope

### `src/adapters/ota/health_check.py`

```python
@dataclass(frozen=True)
class ComponentStatus:
    name: str
    ok: bool
    detail: str

@dataclass(frozen=True)
class HealthReport:
    ok: bool
    components: list[ComponentStatus]
    dlq_pending: int
    ordering_buffer_pending: int
    timestamp: str

def system_health_check(client=None) -> HealthReport
```

#### Components checked:
1. **supabase_connectivity** — can we reach the DB? (SELECT 1 via booking_state count)
2. **dlq_table** — ota_dead_letter is accessible
3. **ordering_buffer_table** — ota_ordering_buffer is accessible
4. **dlq_threshold** — DLQ pending < DLQ_ALERT_THRESHOLD (from env)
5. **ordering_buffer_waiting** — how many events are waiting in the buffer

#### `ok` field:
- True only if ALL components are ok AND dlq_threshold not exceeded

### Contract tests:
- all components healthy → ok=True
- supabase unreachable → ok=False, component detail shows error
- DLQ threshold exceeded → ok=False, detail shows count
- ordering buffer with waiting events → reported but does NOT fail ok alone
- frozen dataclass fields correct

Out of scope:
- HTTP endpoint (that is infrastructure concern, not domain logic)
- external alerting (Phase 41 already handles notifications)
