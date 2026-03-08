# Phase 46 Spec — System Health Check

## Objective

Build a single callable health check that gives operators a structured readiness report
before expanding the feature surface (BOOKING_AMENDED, production deployment).

## Rationale

Large SaaS companies (Stripe, Twilio, Airbnb) expose a health endpoint before expanding
capabilities. iHouse Core needed one callable that returns a consolidated system-readiness
verdict without raising.

## Deliverables

### New file: `src/adapters/ota/health_check.py`

**Dataclasses:**
- `ComponentStatus(name, ok, detail)` — frozen
- `HealthReport(ok, components, dlq_pending, ordering_buffer_pending, timestamp)` — frozen

**Function:** `system_health_check(client=None) → HealthReport`

**5 components checked:**
1. `supabase_connectivity` — can we query booking_state?
2. `ota_dead_letter` — table accessible?
3. `ota_ordering_buffer` — table accessible?
4. `dlq_threshold` — DLQ pending < threshold (default 10)?
5. `ordering_buffer_waiting` — informational count of waiting events

**Behavior:**
- `ok=True` only if all components ok AND DLQ threshold not exceeded
- Never raises — all exceptions caught per component
- Returns structured `HealthReport` always

## Tests

10 contract tests:
- Healthy state → ok=True
- 5 components present
- Frozen dataclass guard
- Supabase down → ok=False, component marked
- Threshold exceeded → ok=False
- Ordering buffer informational (never blocks ok)
- Never raises on exception
- dlq_pending in report

## E2E Result

OVERALL OK ✅ — all 5 components green on live Supabase in under 1 second.

## Constraints

- No Supabase migrations
- No new tables
- No write paths
- Read-only system inspection

## Outcome

103 tests pass (2 pre-existing SQLite failures unrelated).
