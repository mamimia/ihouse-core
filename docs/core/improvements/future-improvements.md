# iHouse Core – Future Improvements

## Purpose

This document is the canonical backlog for forward-looking improvements,
deferred hardening items, and non-immediate architecture work.

It is not a phase timeline.

It is not a construction log.

It exists to keep future work centralized in one place while preserving
append-only historical records in `docs/core/phase-timeline.md`.


## Rules

- new future improvements must be recorded here
- phase-timeline remains historical and append-only
- historical references in older timeline entries are not rewritten
- duplicate backlog items should be merged here into one canonical entry
- each item should include where it was first noticed


## Entry Format

### Title
- status: open | deferred | blocked | resolved
- discovered_in: Phase XX, Phase YY
- source_context: short note
- priority: low | medium | high
- notes: concise implementation context


## Active Backlog

### Event Time vs System Time Separation
- status: deferred
- discovered_in: Phase 20 era backlog
- source_context: distributed OTA ingestion timing semantics
- priority: medium
- notes: separate `occurred_at` from `recorded_at` so delayed or out-of-order external events remain auditable without weakening ordering guarantees. Use `recorded_at` for canonical ordering and preserve `occurred_at` for business history.

### Dead Letter Queue for External Event Failures
- status: deferred
- discovered_in: Phase 20 era backlog
- source_context: external event failure retention
- priority: medium
- notes: add a dedicated dead-letter store for invalid or failed external events so they are preserved for investigation, manual correction, and controlled replay.

### External Event Ordering Protection
- status: deferred
- discovered_in: Phase 21, Phase 27
- source_context: OTA events may arrive out of order
- priority: high
- notes: unify all ordering-related future work here. Covers delayed events, missing events, cancellation before creation, and guarded handling for out-of-order arrival. Must not bypass canonical ingest rules.

### Business Idempotency Beyond Envelope Idempotency
- status: deferred
- discovered_in: Phase 21, Phase 27
- source_context: duplicate business events with different envelope identifiers
- priority: high
- notes: envelope idempotency covers transport retries only. Future work may add a business-idempotency registry or equivalent guard for repeated OTA-originated events that carry different envelope IDs.

### Business Identity Enforcement
- status: deferred
- discovered_in: Phase 21
- source_context: deterministic booking identity hardening
- priority: high
- notes: strengthen identity guarantees around tenant, source, reservation reference, and property identity so retries and OTA updates resolve to the same booking deterministically.

### OTA Schema / Semantic Normalization
- status: deferred
- discovered_in: Phase 21
- source_context: provider field semantics differ
- priority: medium
- notes: introduce stronger channel-specific normalization rules for timezone, currency, guest counts, and similar provider-specific payload semantics while preserving the shared canonical pipeline.

### OTA Integration Hardening
- status: deferred
- discovered_in: Phase 21
- source_context: external ingress protection
- priority: medium
- notes: backlog bucket for rate limiting, webhook replay protection, audit logging, and channel-specific authentication policies around OTA ingress.

### Idempotency Monitoring
- status: deferred
- discovered_in: Phase 20 era backlog
- source_context: operational visibility
- priority: medium
- notes: add metrics and monitoring for duplicate envelope detection, retry storms, and integration-side anomalies.

### Multi Projection Support
- status: deferred
- discovered_in: Phase 20 era backlog
- source_context: read-model expansion
- priority: low
- notes: future projections may include availability, revenue, and analytics read models beyond `booking_state`.

### Replay Snapshot Optimization
- status: deferred
- discovered_in: Phase 20 era backlog
- source_context: long-term replay performance
- priority: low
- notes: when the event log grows large, introduce replay snapshots to reduce rebuild cost without weakening canonical event authority.

### External Event Signature Validation
- status: deferred
- discovered_in: Phase 20 era backlog
- source_context: webhook authenticity
- priority: medium
- notes: support signature validation such as HMAC or equivalent verification for external OTA webhooks.

### OTA Sync Recovery Layer
- status: blocked
- discovered_in: Phase 27
- source_context: synchronization-style OTA notifications
- priority: medium
- notes: some OTA ecosystems emit synchronization signals rather than deterministic lifecycle facts. A future recovery layer may fetch snapshots and derive deterministic outcomes, but it must never mutate canonical state directly and must still feed only deterministic facts into the canonical apply gate.

### Amendment Handling
- status: blocked
- discovered_in: Phase 27 and later OTA evolution notes
- source_context: deterministic support for reservation modifications
- priority: medium
- notes: the current rule remains `MODIFY -> deterministic reject-by-default`. Future amendment support is allowed only after deterministic classification, reservation identity stability, safe ordering guarantees, and state-safe application rules exist.


## Resolved / No Longer Open

### OTA External Surface Hardening
- status: resolved
- discovered_in: Phase 27
- source_context: explicit OTA lifecycle surface
- priority: none
- notes: this was resolved later when the system adopted explicit canonical lifecycle events instead of treating `BOOKING_SYNC_INGEST` as the canonical external business surface. Keep this entry only as migration history, not as active backlog.


## Migration Note

Historical future-looking notes still exist inside older append-only
timeline entries.

Those historical references remain valid as history.

From this point forward, new future improvements must be recorded in
this file instead of being added as new backlog content inside
`docs/core/phase-timeline.md`.

## Follow-up from Phase 33 — OTA runtime to canonical apply alignment

Phase 33 discovered that canonical Supabase business dedup already exists for canonical emitted business events, but the active OTA runtime path appears misaligned with the canonical emitted event contract expected by `apply_envelope`.

Future hardening must verify and align OTA skill routing and emitted event mapping so that OTA-originated `BOOKING_CREATED` and `BOOKING_CANCELED` reach `apply_envelope` in the canonical business shape required for enforcement.

This follow-up is about routing and emitted-event alignment, not reconciliation, amendment handling, adapter-side state mutation, or alternative write paths.
