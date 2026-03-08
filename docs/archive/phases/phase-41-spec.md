# Phase 41 — DLQ Alerting Threshold

## Status

Active

## Depends On

Phase 40 — DLQ Observability (`get_pending_count` from `dlq_inspector.py`)

## Objective

Emit a structured warning when pending DLQ rows exceed a configurable threshold. Gives operators an early signal before silent rejection accumulation becomes a production incident.

## Design

### `DLQAlertResult` dataclass

```python
@dataclass
class DLQAlertResult:
    pending_count: int
    threshold: int
    exceeded: bool
    message: str
```

### `check_dlq_threshold(threshold, client=None) -> DLQAlertResult`

Flow:
1. Call `get_pending_count(client)`
2. If `pending_count >= threshold` → `exceeded=True`, print WARNING to stderr
3. Return `DLQAlertResult`

### Default threshold

Read from env var `DLQ_ALERT_THRESHOLD`. Default: 10.

A helper `check_dlq_threshold_default(client=None)` reads the env var and calls `check_dlq_threshold`.

## Constraints

- No external alerting (webhook, Slack, email) — stderr log only in this phase
- No writes
- No new Supabase tables or migrations
- Must be independently testable without live Supabase

## Completion Conditions

Phase 41 is complete when:
- `dlq_alerting.py` implements `DLQAlertResult`, `check_dlq_threshold`, `check_dlq_threshold_default`
- contract tests cover: not exceeded, exceeded, boundary, env var default, zero pending
- all existing tests still pass
