# iHouse Core — Current Snapshot

## Current Phase
Phase 47 — TBD

## Last Closed Phase
Phase 46 — System Health Check

## System Status

**The system is production-ready for the current feature set.**

`apply_envelope` remains the only authority allowed to mutate canonical booking state.

Health check verified live: OVERALL OK ✅ — all 5 components green.

## Phase 46 Result

[Claude]

Rationale: Large SaaS companies build health checks before expanding feature surface.

**Module:** `health_check.py`

```
system_health_check() → HealthReport
  ├─ ✅ supabase_connectivity
  ├─ ✅ ota_dead_letter
  ├─ ✅ ota_ordering_buffer
  ├─ ✅ dlq_threshold (pending < threshold)
  └─ ✅ ordering_buffer_waiting (informational)
```

- `HealthReport` and `ComponentStatus` are frozen dataclasses
- Never raises — all exceptions caught per component
- E2E live: OVERALL OK ✅

## Full OTA Adapter Layer

| Module | Role |
|--------|------|
| `dead_letter.py` | preserve rejected events |
| `dlq_replay.py` | controlled replay → apply_envelope |
| `dlq_inspector.py` | read-only DLQ observability |
| `dlq_alerting.py` | threshold alerting |
| `booking_status.py` | read booking lifecycle status |
| `ordering_buffer.py` | ordering buffer: write, read, mark |
| `ordering_trigger.py` | auto-trigger replay on BOOKING_CREATED |
| `health_check.py` | consolidated system readiness check ← NEW |

## Tests
**103 passing** (2 pre-existing SQLite failures, unrelated)

## BOOKING_AMENDED Prerequisites: 5/10

| Prerequisite | Status |
|-------------|--------|
| DLQ infrastructure | ✅ |
| booking_id stability | ✅ |
| MODIFY classification | ✅ |
| booking_state.status | ✅ |
| Ordering infrastructure | ✅ |
| Normalized AmendmentPayload | ❌ |
| apply_envelope BOOKING_AMENDED branch | ❌ |
| event_kind enum: BOOKING_AMENDED | ❌ |
| ACTIVE-state guard | ❌ |
| Idempotency key for amendments | ❌ |

## Canonical Invariants

- event_log is append-only
- events are immutable
- booking_state is projection-only
- apply_envelope is the only write authority
- booking_id = "{source}_{reservation_ref}" — deterministic and canonical
- MODIFY → deterministic reject-by-default
