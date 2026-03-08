# iHouse Core – Roadmap

> [!NOTE]
> This document is a living directional guide, not a binding contract.
> It is updated every few phases to reflect what we've learned and where we're headed.
> Last updated: Phase 39 closed. [Claude]


## Completed

Phase 21 — External OTA ingestion boundary defined.
Phase 22 — OTA adapter layer introduced with normalization and validation.
Phase 23 — Semantic classification layer introduced for OTA events.
Phase 24 — OTA modification semantic recognition (MODIFY) with deterministic reject-by-default.
Phase 25 — OTA modification resolution rules closed.
Phase 26 — OTA payload contract verification across providers.
Phase 27 — Multi-OTA adapter architecture (shared pipeline, multi-provider registry, Booking.com + Expedia scaffold).
Phase 28–33 — (See phase-timeline.md for full history.)
Phase 34 — OTA canonical emitted event alignment discovery.
Phase 35 — OTA canonical emitted event alignment implementation (BOOKING_CREATED, BOOKING_CANCELED skills).
Phase 36 — Business identity canonicalization (booking_id = {source}_{reservation_ref} verified and locked).
Phase 37 — External event ordering protection discovery (CANCELED before CREATED → BOOKING_NOT_FOUND confirmed, current behavior classified as deterministic rejection).
Phase 38 — Dead Letter Queue implemented (ota_dead_letter table, dead_letter.py, best-effort non-blocking write).
Phase 39 — DLQ controlled replay (replay_dlq_row, idempotency, outcome persistence).


---

## Upcoming — Near Term

These are concrete next-phase candidates based on current system state.


### Phase 40 — DLQ Observability

Goal:
Make the Dead Letter Queue visible and operational without adding new write paths.

Proposed scope:
- A Supabase SQL view `ota_dlq_summary` grouping rejection counts by event_type and rejection_code
- A read-only Python utility `dlq_inspector.py` exposing: pending rows, replayed rows, rejection breakdown
- Contract tests for the inspector (unit, no live Supabase required)

Constraints:
- No new write paths
- No alerting infrastructure (that is Phase 41)
- Must not read booking_state


### Phase 41 — DLQ Alerting Threshold

Goal:
Trigger an observable signal when DLQ accumulates too many unresolved rows.

Proposed scope:
- A simple threshold checker: if DLQ pending count exceeds N → emit a structured warning log
- Configurable threshold via environment variable
- Contract tests for threshold logic


### Phase 42 — Reservation Amendment Discovery

Goal:
Begin the formal discovery phase for BOOKING_AMENDED support.

This phase is discovery only — no implementation.

Key questions:
- What OTA providers emit amendment signals and in what shape?
- Can amendment intent be classified deterministically?
- What does "state-safe amendment application" require from apply_envelope?
- What ordering guarantees are needed before BOOKING_AMENDED can be introduced?

Constraints:
- MODIFY remains deterministic reject-by-default until all discovery questions are answered
- No new canonical event kinds in this phase
- No booking_state reads in adapters


### Phase 43 — booking_id Stability Layer

Goal:
Protect booking identity against provider-side reservoir_ref format changes.

Key questions:
- Which providers are likely to change reservation_ref encoding?
- Should we normalize reservation_ref before forming booking_id?
- What is the migration path for existing booking rows if the stable key changes?

Constraints:
- booking_id rule ({source}_{reservation_ref}) must remain deterministic
- No schema mutation without a migration + replay safety analysis


---

## Medium Term

These are directions we expect to reach within 10-15 phases from now.


### Operational Observability Layer

Structured logging, ingestion metrics, and DLQ alerting across all OTA adapters.

Will cover:
- Rejection rates by provider and event type
- DLQ accumulation trends
- Replay success/failure rates


### OTA Ingestion Replay Harness

Deterministic replay tools to simulate historical OTA event streams against the canonical pipeline. Used for regression testing and incident recovery.


### External Integration Test Harness

End-to-end verification of OTA ingestion from the provider webhook boundary through to Supabase state, covering rejection scenarios, dedup, and replay safety.


### BOOKING_AMENDED Support (Future)

Full deterministic amendment support. Can only begin after:
- multiple OTA providers are live
- ordering buffer or DLQ retry exists
- out-of-order protections are proven in production
- amendment classification is deterministic

Until then: MODIFY → deterministic reject-by-default.


---

## Future OTA Evolution — Amendment Handling

MODIFY remains deterministic reject-by-default.

This section tracks the formal requirements for BOOKING_AMENDED.
See `improvements/future-improvements.md` for the detailed backlog entry.

Requirements before BOOKING_AMENDED can be introduced:

1. Deterministic amendment classification — adapters must distinguish safe amendments from ambiguous modifications
2. Reservation identity stability — booking_id must be stable across amendment events
3. State-safe amendment application — apply_envelope must safely transition previous_state → amended_state
4. Out-of-order protection — amendments must not corrupt state if events arrive late
5. Projection safety — event log must correctly rebuild amended reservations from history