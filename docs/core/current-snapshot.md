# iHouse Core — Current Snapshot

## Current Phase
Phase 52 — (Next: TBD)

## Last Closed Phase
Phase 51 — Python Pipeline Integration: BOOKING_AMENDED Routing

## System Status

**BOOKING_AMENDED is end-to-end: from OTA webhook → Python pipeline → apply_envelope → Supabase.**

apply_envelope is the only authority for canonical state mutations.

Health check: OVERALL OK ✅

## Phase 51 Result

Pipeline route that was rejected (MODIFY) is now canonical (BOOKING_AMENDED):

```
reservation_modified
  → semantics.py       → BOOKING_AMENDED
  → validator.py       → allowed (was: reject)
  → bookingcom.py      → CanonicalEnvelope(type=BOOKING_AMENDED, booking_id, amendment fields)
  → apply_envelope     → APPLIED
```

**180 tests pass** (2 pre-existing SQLite failures unrelated).

| File | Change |
|------|--------|
| `semantics.py` | `reservation_modified` → `BOOKING_AMENDED` (was `MODIFY`) |
| `validator.py` | `BOOKING_AMENDED` allowed in semantic + canonical validators |
| `bookingcom.py` | `to_canonical_envelope` handles `BOOKING_AMENDED` — builds `booking_id` + `AmendmentFields` |
| `test_ota_replay_harness.py` | Updated stale MODIFY-reject test to reflect new behavior |
| `tests/test_booking_amended_contract.py` | 22 new contract tests |

## Full OTA Adapter Layer

| Module | Role |
|--------|------|
| `semantics.py` | OTA event → semantic kind (CREATE / CANCEL / BOOKING_AMENDED) |
| `validator.py` | Structural + semantic + canonical validation |
| `bookingcom.py` | Provider-specific normalization + envelope construction |
| `amendment_extractor.py` | Provider-agnostic AmendmentFields normalization |
| `idempotency.py` | Namespaced key: `{provider}:{type}:{event_id}` |
| `payload_validator.py` | Boundary validation |
| `dead_letter.py` | DLQ write |
| `dlq_replay.py` | Controlled replay → apply_envelope |
| `dlq_inspector.py` | DLQ observability |
| `dlq_alerting.py` | Threshold alerting |
| `booking_status.py` | Read booking lifecycle status |
| `ordering_buffer.py` | Ordering buffer: write, read, mark |
| `ordering_trigger.py` | Auto-trigger replay on BOOKING_CREATED |
| `health_check.py` | Consolidated system readiness check |

## Tests

**180 passing** (2 pre-existing SQLite failures, unrelated)
