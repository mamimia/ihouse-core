# iHouse Core — Current Snapshot

## Current Phase
Phase 49 — TBD

## Last Closed Phase
Phase 48 — Idempotency Key Standardization

## System Status

**The system is production-hardened.**

apply_envelope is the only authority for canonical state mutations.

Health check: OVERALL OK ✅ on live Supabase.

## Phase 48 Result

[Claude]

**Problem:** Raw `external_event_id` as idempotency key → cross-provider collisions possible.

**Solution:** `generate_idempotency_key(provider, event_id, event_type)` — namespaced, deterministic, lowercase.

**Format:** `{provider}:{event_type}:{event_id}`

**Examples:**
- `bookingcom:booking_created:ev_001`
- `expedia:booking_canceled:xid-9182`

Now: same `ev_001` from Booking.com and Expedia → **different keys** ✅

## Full OTA Adapter Layer

| Module | Role |
|--------|------|
| `idempotency.py` | namespaced key generation + validation ← NEW |
| `payload_validator.py` | boundary validation |
| `dead_letter.py` | preserve rejected events |
| `dlq_replay.py` | controlled replay → apply_envelope |
| `dlq_inspector.py` | read-only DLQ observability |
| `dlq_alerting.py` | threshold alerting |
| `booking_status.py` | read booking lifecycle status |
| `ordering_buffer.py` | ordering buffer: write, read, mark |
| `ordering_trigger.py` | auto-trigger replay on BOOKING_CREATED |
| `health_check.py` | consolidated system readiness check |

## Tests
**138 passing** (2 pre-existing SQLite failures, unrelated)

## BOOKING_AMENDED Prerequisites: 5/10 + idempotency format ✅

| Prerequisite | Status |
|-------------|--------|
| DLQ infrastructure | ✅ |
| booking_id stability | ✅ |
| MODIFY classification | ✅ |
| booking_state.status | ✅ |
| Ordering infrastructure | ✅ |
| Idempotency key format (now standardized) | ✅ ← Phase 48 |
| Normalized AmendmentPayload | ❌ |
| apply_envelope BOOKING_AMENDED branch | ❌ |
| event_kind enum: BOOKING_AMENDED | ❌ |
| ACTIVE-state guard | ❌ |

**6/10 prerequisites now satisfied.**

## Canonical Invariants
- event_log is append-only
- events are immutable
- booking_state is projection-only
- apply_envelope is the only write authority
- booking_id = "{source}_{reservation_ref}" — deterministic and canonical
- MODIFY → deterministic reject-by-default
