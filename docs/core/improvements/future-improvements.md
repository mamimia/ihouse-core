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
- status: resolved
- discovered_in: Phase 20 era backlog
- resolved_in: Phase 38
- source_context: external event failure retention
- priority: medium
- notes: [Claude] Phase 38 implemented ota_dead_letter table (append-only, RLS) and dead_letter.py (best-effort, non-blocking). Rejected OTA events are now preserved. E2E verified.

### External Event Ordering Protection
- status: deferred
- discovered_in: Phase 21, Phase 27
- verified_in: Phase 37
- source_context: OTA events may arrive out of order
- priority: high
- notes: [Claude] Phase 37 verified the current behavior. BOOKING_CANCELED before BOOKING_CREATED raises BOOKING_NOT_FOUND (code P0001) from apply_envelope — a deterministic rejection, not silent data loss. There is no buffering, retry, or ordering layer in the active OTA runtime path. The event is lost. Future work must decide whether to add a dead-letter store, a retry queue, or an ordering buffer — but must not bypass canonical ingest rules or introduce adapter-side state reads.

### Business Idempotency Beyond Envelope Idempotency
- status: resolved
- discovered_in: Phase 21, Phase 27
- resolved_in: Phase 36
- source_context: duplicate business events with different envelope identifiers
- priority: high
- notes: [Claude] Phase 36 verified that apply_envelope already provides two layers of business-level dedup: (1) by booking_id, (2) by composite (tenant_id, source, reservation_ref, property_id). E2E test confirmed that a duplicate BOOKING_CREATED with a different request_id returns ALREADY_EXISTS without writing a new booking_state row. No additional business-idempotency registry is required at this stage.

### Business Identity Enforcement
- status: resolved
- discovered_in: Phase 21
- resolved_in: Phase 36
- source_context: deterministic booking identity hardening
- priority: high
- notes: [Claude] Phase 36 verified and formally documented canonical booking_id rule: booking_id = "{source}_{reservation_ref}". This rule is applied consistently in booking_created and booking_canceled skills, and apply_envelope reads booking_id from the emitted event payload. The combination of deterministic booking_id construction and apply_envelope dedup eliminates the risk of duplicate booking_state writes for the same OTA identity.

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


### DLQ Controlled Replay
- status: open
- discovered_in: Phase 38
- source_context: DLQ rows are preserved but currently unactionable
- priority: high
- notes: [Claude] Now that ota_dead_letter exists, the next step is a safe, controlled replay mechanism that reads specific rows from ota_dead_letter and re-processes them through the canonical ingest pipeline (skill → apply_envelope). Replay must never bypass apply_envelope. Replay must be manually triggered, not automatic. Replay must be idempotent — re-running the same DLQ row must be safe. A replay_id or replay_at timestamp should be written back to the DLQ row after successful replay.

### DLQ Observability and Alerting
- status: open
- discovered_in: Phase 38
- source_context: operational visibility on rejected OTA events
- priority: medium
- notes: [Claude] ota_dead_letter is queryable but has no alerting. Future work should add: (1) a daily summary of rejection counts by event_type and rejection_code, (2) alerting when DLQ rows exceed a threshold, (3) a read-only dashboard view on existing Supabase Studio. Must not add new write paths.

### Idempotent DLQ Replay Tracking
- status: open
- discovered_in: Phase 38
- source_context: safe replay from DLQ
- priority: medium
- notes: [Claude] When DLQ replay is implemented, the ota_dead_letter table should include: replayed_at (timestamptz), replay_result (text), replay_trace_id (text). This allows operators to see which DLQ rows have been successfully replayed and which remain pending. Must be added via a migration, not by mutating the original preserved envelope.

### booking_id Stability Across Provider Schema Changes
- status: open
- discovered_in: Phase 36
- source_context: booking_id is derived from provider-supplied fields
- priority: medium
- notes: [Claude] The canonical booking_id rule is {source}_{reservation_ref}. If an OTA provider changes the format of reservation_ref (e.g., strips a prefix, changes encoding), the same booking will generate a different booking_id and bypass the existing dedup. Future work should consider a stable booking identity layer that canonicalizes reservation_ref before inclusion in booking_id.

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

[Claude] Resolved in Phase 34 (discovery) and Phase 35 (implementation).

Phase 34 proved the routing and emitted-event alignment gap. Phase 35 implemented the minimal fix. Phase 36 confirmed that business identity is deterministic and business dedup is enforced by apply_envelope.

This follow-up is fully resolved.
