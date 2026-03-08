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

### Financial Model Foundation — Canonical Revenue Layer
- status: resolved
- discovered_in: Phase 62 planning discussion
- resolved_in: Phase 65 (in-memory extraction), Phase 66 (Supabase persistence)
- source_context: product direction — finance-aware platform
- priority: high
- notes: Phase 65 introduced BookingFinancialFacts (frozen dataclass, 5-provider extraction). Phase 66 created the booking_financial_facts Supabase table (append-only, RLS) and financial_writer.py to persist facts after BOOKING_CREATED APPLIED (best-effort, non-blocking). Invariant locked: booking_state must NEVER contain financial data.


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
- status: resolved
- discovered_in: Phase 21, Phase 27
- verified_in: Phase 37
- resolved_in: Phase 44 (ota_ordering_buffer table + buffer_event/get_buffered_events/mark_replayed), Phase 45 (ordering_trigger.py, auto-replay on BOOKING_CREATED)
- source_context: OTA events may arrive out of order
- priority: high
- notes: [Claude] Phase 37 verified current behavior: BOOKING_CANCELED before BOOKING_CREATED raises BOOKING_NOT_FOUND — deterministic rejection, not data loss. Phase 44 introduced ota_ordering_buffer table (Supabase) and ordering_buffer.py (buffer_event, get_buffered_events, mark_replayed). Phase 45 closed the loop: ordering_trigger.py fires automatically on BOOKING_CREATED APPLIED, replays any waiting buffer rows via replay_dlq_row, marks them replayed. E2E verified: CANCELED → buffer → CREATED → auto-trigger → 0 waiting.

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
- status: resolved
- discovered_in: Phase 20 era backlog
- resolved_in: Phase 57 (signature_verifier.py, HMAC-SHA256, 5 providers)
- source_context: webhook authenticity
- priority: medium
- notes: [Claude] Phase 57 introduced signature_verifier.py with HMAC-SHA256 validation for all 5 OTA providers. Each provider has a dedicated header (X-Booking-Signature, X-Expedia-Signature, X-Airbnb-Signature, X-Agoda-Signature, X-TripCom-Signature) and env var (IHOUSE_WEBHOOK_SECRET_{PROVIDER}). Dev-mode skip when secret not set. 403 SIGNATURE_VERIFICATION_FAILED returned on mismatch.

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
- status: resolved
- discovered_in: Phase 38
- resolved_in: Phase 39
- source_context: DLQ rows are preserved but currently unactionable
- priority: high
- notes: [Claude] Phase 39 implemented replay_dlq_row: reads ota_dead_letter, resolves skill, calls apply_envelope with new idempotency key, persists replayed_at/replay_result/replay_trace_id back to row. Never bypasses apply_envelope. Idempotent — re-running APPLIED row is a no-op.

### DLQ Observability and Alerting
- status: resolved
- discovered_in: Phase 38
- resolved_in: Phase 40 (ota_dlq_summary view, dlq_inspector.py), Phase 41 (dlq_alerting.py, DLQ_ALERT_THRESHOLD)
- source_context: operational visibility on rejected OTA events
- priority: medium
- notes: [Claude] Phase 40 added ota_dlq_summary view (group by event_type/rejection_code, pending/replayed counts) and dlq_inspector.py (get_pending_count, get_replayed_count, get_rejection_breakdown). Phase 41 added dlq_alerting.py: check_dlq_threshold emits WARNING to stderr when pending >= threshold. Configurable via DLQ_ALERT_THRESHOLD env var (default 10).

### Idempotent DLQ Replay Tracking
- status: resolved
- discovered_in: Phase 38
- resolved_in: Phase 39
- source_context: safe replay from DLQ
- priority: medium
- notes: [Claude] Phase 39 added replayed_at (timestamptz), replay_result (text), replay_trace_id (text) columns to ota_dead_letter (migration: 20260308174500_phase39_dlq_replay_columns.sql). Replay outcome is written back after every replay attempt.

### booking_id Stability Across Provider Schema Changes
- status: resolved
- discovered_in: Phase 36
- resolved_in: Phase 68
- source_context: booking_id is derived from provider-supplied fields
- priority: medium
- notes: [Claude] Phase 68 introduced booking_identity.py with normalize_reservation_ref(provider, raw_ref) — strips whitespace, lowercases, and applies per-provider prefix stripping (bookingcom: BK-, agoda: AGD-/AG-, tripcom: TC-). All 5 adapters now call normalize_reservation_ref() in normalize() before constructing reservation_id. The locked formula booking_id = {source}_{reservation_ref} (Phase 36) is unchanged. 30 contract tests cover all providers, determinism, and edge cases.

### BOOKING_AMENDED Support
- status: resolved
- discovered_in: Phase 42
- resolved_in: Phase 49 (AmendmentFields schema, amendment_extractor.py), Phase 50 (apply_envelope DB branch, BOOKING_AMENDED enum value), Phase 51-57 (Python pipeline routing), Phase 69 (booking_amended skill, registry wiring, service.py hook)
- source_context: Phase 42 investigated all preconditions; Phase 43 verified status column
- priority: medium
- notes: [Claude] All 10 prerequisites satisfied. Phase 69 wired the full Python pipeline: booking_amended skill (transforms OTA adapter envelope → BOOKING_AMENDED emitted event), registered in kind_registry.core.json and skill_exec_registry.core.json. service.py updated with best-effort BOOKING_AMENDED financial facts write. Adapters already emit booking_id + amendment fields in to_canonical_envelope. Full end-to-end: OTA webhook → pipeline → BOOKING_AMENDED envelope → booking_amended skill → apply_envelope updates booking_state (check_in, check_out via COALESCE). 20 contract tests added (451 total).

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
