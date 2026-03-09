# Phase 80 — Structured Logging Layer

## Status: CLOSED

## Objective

Add `src/adapters/ota/structured_logger.py` — a zero-dependency structured JSON logging wrapper.
No changes to existing callers. Adoption is incremental in future phases.

## Design

### Log Entry Format

```json
{
  "ts":       "2026-03-09T06:33:00.000000+00:00",
  "level":    "INFO",
  "event":    "webhook_received",
  "trace_id": "req-abc-123",
  "provider": "bookingcom"
}
```

- `ts` — UTC ISO 8601, always present
- `level` — DEBUG / INFO / WARNING / ERROR / CRITICAL
- `event` — snake_case string, required
- `trace_id` — included if set at construction time
- Extra kwargs merged at root level; non-serializable values fall back via `default=str`

### API

```python
class StructuredLogger:
    def __init__(self, name: str, trace_id: str = "")
    def debug / info / warning / error / critical(self, event: str, **kwargs) -> str
    # Each method: builds entry dict → json.dumps() → stdlib logging.log() → returns JSON str

def get_structured_logger(name: str, trace_id: str = "") -> StructuredLogger
```

## Files Added

- `src/adapters/ota/structured_logger.py`
- `tests/test_structured_logger_contract.py`

## Result

**663 passed, 2 skipped** (pre-existing SQLite skips)
30 contract tests (Groups A–G: JSON validity, required fields, level correctness, trace_id, kwargs, fallback, factory).
No Supabase schema changes. No new migrations.
