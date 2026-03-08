# iHouse Core — Current Snapshot

## Current Phase
Phase 48 — TBD

## Last Closed Phase
Phase 47 — OTA Payload Boundary Validation

## System Status

**The system is production-hardened for the current feature set.**

apply_envelope is the only authority allowed to mutate canonical booking state.

Health check: OVERALL OK ✅

## Phase 47 Result

[Claude]

**Module:** `payload_validator.py`

6 validation rules at the OTA boundary, before normalize():

| Rule | Error Code |
|------|-----------|
| provider is non-empty | `PROVIDER_REQUIRED` |
| payload is a dict | `PAYLOAD_MUST_BE_DICT` |
| reservation_id present and non-empty | `RESERVATION_ID_REQUIRED` |
| tenant_id present and non-empty | `TENANT_ID_REQUIRED` |
| occurred_at parseable as ISO datetime | `OCCURRED_AT_INVALID` |
| event_type / type / action / event / status present | `EVENT_TYPE_REQUIRED` |

All errors collected together (not fail-fast). Integrated at top of `process_ota_event`.

## Full OTA Adapter Layer

| Module | Role |
|--------|------|
| `payload_validator.py` | boundary validation ← NEW |
| `dead_letter.py` | preserve rejected events |
| `dlq_replay.py` | controlled replay → apply_envelope |
| `dlq_inspector.py` | read-only DLQ observability |
| `dlq_alerting.py` | threshold alerting |
| `booking_status.py` | read booking lifecycle status |
| `ordering_buffer.py` | ordering buffer: write, read, mark |
| `ordering_trigger.py` | auto-trigger replay on BOOKING_CREATED |
| `health_check.py` | consolidated system readiness check |

## Tests
**119 passing** (2 pre-existing SQLite failures, unrelated)

## BOOKING_AMENDED Prerequisites: 5/10

(unchanged — validator skeleton now exists for amendment payloads when needed)

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
