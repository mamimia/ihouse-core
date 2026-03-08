# iHouse Core — Current Snapshot

## Current Phase
Phase 42 — Reservation Amendment Discovery

## Last Closed Phase
Phase 41 — DLQ Alerting Threshold

## System Status

The deterministic event architecture remains fully operational.

`apply_envelope` remains the only authority allowed to mutate canonical booking state.

The DLQ layer (Phases 38–41) is now complete:

| Component | What |
|-----------|------|
| `dead_letter.py` | best-effort write on rejection |
| `dlq_replay.py` | safe, idempotent, manual replay |
| `dlq_inspector.py` + `ota_dlq_summary` view | read-only observability |
| `dlq_alerting.py` | configurable threshold alerting |

## Phase 41 Result

[Claude]

**Module:** `src/adapters/ota/dlq_alerting.py`
- `DLQAlertResult` — frozen dataclass: `pending_count`, `threshold`, `exceeded`, `message`
- `check_dlq_threshold(threshold, client)` — emits `[DLQ ALERT]` to stderr when `pending >= threshold`
- `check_dlq_threshold_default(client)` — reads `DLQ_ALERT_THRESHOLD` env var, falls back to 10

## Canonical External OTA Events

- BOOKING_CREATED
- BOOKING_CANCELED

## Canonical Invariants

- event_log is append-only
- events are immutable
- booking_state is projection-only
- apply_envelope is the only write authority
- booking_id = "{source}_{reservation_ref}" — deterministic and canonical

## Known Open Gaps (Deferred)

| Gap | Status | Priority |
|-----|--------|----------|
| Reservation Amendment (BOOKING_AMENDED) | Phase 42 — discovery | medium |
| External Event Ordering Buffer | deferred | high |
| booking_id Stability Across Provider Schema Changes | deferred | medium |
| DLQ Replay Tracking columns | implemented in Phase 39 | ✅ done |
