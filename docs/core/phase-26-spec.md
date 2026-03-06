# Phase 26 – OTA Provider Verification

Objective

Verify whether OTA providers expose deterministic modification signals
within their payload schemas that allow safe interpretation of
modification events without booking_state lookup.


Background

Phase 25 established that OTA modification notifications such as:

reservation_modified

cannot currently be interpreted deterministically from the inspected
provider payload surface.


Verification Scope

Provider payload schema inspection for:

Booking.com  
Expedia  
Additional OTA providers


Verification Criteria

A modification event may only be mapped to UPDATE if all of the
following conditions are satisfied:

1. The provider payload explicitly exposes modification subtype.
2. The interpretation requires no booking_state lookup.
3. The interpretation preserves the canonical rule:

one normalized event
→ one canonical envelope


Non-Goals

Phase 26 must NOT:

- introduce booking_state reads
- change canonical schema
- modify apply_envelope
- introduce reconciliation logic inside adapters


Completion Conditions

Phase 26 is considered complete when:

1. OTA provider payload capabilities are verified.
2. Deterministic interpretation rules are either proven or rejected.
3. The canonical ingestion rule for MODIFY is formally confirmed.


Expected Outcomes

Possible outcomes include:

1. A safe deterministic subset is proven.

or

2. The canonical ingestion rule remains:

MODIFY
→ deterministic reject-by-default


