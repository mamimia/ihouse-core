# iHouse Core — Current Snapshot

## Current Phase
Phase 43 — booking_state Status Column

## Last Closed Phase
Phase 42 — Reservation Amendment Discovery

## System Status

The deterministic event architecture remains fully operational.

`apply_envelope` remains the only authority allowed to mutate canonical booking state.

`MODIFY → deterministic reject-by-default` remains in place.

## Phase 42 Result

[Claude] — Discovery only, no code.

Investigated all 7 preconditions for introducing `BOOKING_AMENDED`.

### Amendment Prerequisites: 3/10 satisfied

| Prerequisite | Status |
|-------------|--------|
| DLQ infrastructure (Phases 38-39) | ✅ Done |
| booking_id stability across events | ✅ Verified |
| MODIFY classification in semantics.py | ✅ Exists |
| Normalized amendment payload schema | ❌ Missing |
| apply_envelope BOOKING_AMENDED branch | ❌ Missing |
| event_kind enum includes BOOKING_AMENDED | ❌ Missing |
| booking_state.status explicit column | ❌ Missing |
| ACTIVE-state amendment guard | ❌ Missing |
| Amendment replay ordering rule | ❌ Missing |
| Idempotency key structure for amendments | ❌ Not defined |

### Key gap identified by Phase 42

`booking_state` has no explicit `status` column. Amendment lifecycle validation (`ACTIVE` required before amending) cannot be enforced without it.

**Phase 43 addresses this gap next.**

## Canonical External OTA Events

- BOOKING_CREATED
- BOOKING_CANCELED
- (BOOKING_AMENDED — future, blocked)

## Canonical Invariants

- event_log is append-only
- events are immutable
- booking_state is projection-only
- apply_envelope is the only write authority
- booking_id = "{source}_{reservation_ref}" — deterministic and canonical
- MODIFY → deterministic reject-by-default

## Known Open Gaps (Deferred)

| Gap | Status | Priority |
|-----|--------|----------|
| booking_state.status column | Phase 43 next | high |
| Normalized AmendmentPayload schema | deferred | medium |
| apply_envelope BOOKING_AMENDED branch | blocked (needs status col first) | medium |
| External Event Ordering Buffer | deferred | high |
| booking_id Stability Across Provider Schema Changes | deferred | medium |
