# iHouse Core — Current Snapshot

## Current Phase
Phase 50 — BOOKING_AMENDED DDL + apply_envelope Branch

## Last Closed Phase
Phase 49 — Normalized AmendmentPayload Schema

## System Status

**The system is production-hardened and amendment-ready.**

apply_envelope is the only authority for canonical state mutations.

Health check: OVERALL OK ✅

## Phase 49 Result

[Claude]

**AmendmentFields** (frozen dataclass) added to `schemas.py`:

| Field | Type | Description |
|-------|------|-------------|
| `new_check_in` | `Optional[str]` | ISO date |
| `new_check_out` | `Optional[str]` | ISO date |
| `new_guest_count` | `Optional[int]` | integer |
| `amendment_reason` | `Optional[str]` | provider note |

**amendment_extractor.py:**

| Function | Maps from |
|----------|-----------|
| `extract_amendment_bookingcom` | `new_reservation_info` |
| `extract_amendment_expedia` | `changes.dates` / `changes.guests` |
| `normalize_amendment` | dispatcher (raises on unknown) |

## BOOKING_AMENDED Prerequisites: 7/10 ✅

| Prerequisite | Status |
|-------------|--------|
| DLQ infrastructure | ✅ |
| booking_id stability | ✅ |
| MODIFY classification | ✅ |
| booking_state.status | ✅ |
| Ordering infrastructure | ✅ |
| Idempotency key format | ✅ |
| Normalized AmendmentPayload | ✅ ← Phase 49 |
| event_kind enum: BOOKING_AMENDED | ❌ (Phase 50) |
| apply_envelope BOOKING_AMENDED branch | ❌ (Phase 50) |
| ACTIVE-state lifecycle guard | ❌ (Phase 50) |

**3 prerequisites remain — all DDL/stored-procedure layer.**

## Full OTA Adapter Layer

| Module | Role |
|--------|------|
| `idempotency.py` | namespaced key generation + validation |
| `payload_validator.py` | boundary validation |
| `amendment_extractor.py` | amendment normalization ← NEW |
| `dead_letter.py` | preserve rejected events |
| `dlq_replay.py` | controlled replay → apply_envelope |
| `dlq_inspector.py` | read-only DLQ observability |
| `dlq_alerting.py` | threshold alerting |
| `booking_status.py` | read booking lifecycle status |
| `ordering_buffer.py` | ordering buffer: write, read, mark |
| `ordering_trigger.py` | auto-trigger replay on BOOKING_CREATED |
| `health_check.py` | consolidated system readiness check |

## Tests
**153 passing** (2 pre-existing SQLite failures, unrelated)
