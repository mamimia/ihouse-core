# iHouse Core — Construction Log

This file records what was actually implemented, in order.
It is not a roadmap.
It must match the DB gate behavior and repo state.

## Phase 17C — Overlap Rules, Business Dedup, Read Model Inquiry (Closed)
- booking_state.check_in and booking_state.check_out added (date)
- Overlap gate enforced on BOOKING_CREATED using half open range [check_in, check_out)
- Business identity dedup enforced on (tenant_id, source, reservation_ref, property_id)
- Read model inquiry functions added:
  - read_booking_by_id(booking_id)
  - read_booking_by_business_key(tenant_id, source, reservation_ref, property_id)

## Phase 18 — Cancellation Aware Overlap (Closed)
- booking_state.status added (text)
- BOOKING_CREATED writes status='active'
- BOOKING_CANCELED sets status='canceled' under row lock and bumps version
- Overlap ignores canceled bookings via:
  status IS DISTINCT FROM 'canceled'
  NULL treated as active for legacy rows
- Cancel allows a new overlapping booking to be created after cancellation

## Phase 19 — Event Version Discipline + DB Gate Validation (Closed)
- Introduced validate_emitted_event as DB gate validation for emitted events
- Validation runs before enum cast, enabling deterministic UNKNOWN_EVENT_KIND
- Transitional policy locked:
  - Missing event_version defaults to 1 only for allowlisted external kinds
  - Missing event_version for non external kinds rejects with EVENT_VERSION_REQUIRED
- Deterministic rejection codes locked:
  - UNKNOWN_EVENT_KIND
  - UNSUPPORTED_EVENT_VERSION
  - INVALID_PAYLOAD
  - EVENT_VERSION_REQUIRED
  - ALREADY_APPLIED
- T3 tests locked:
  - T3.1 missing_version external allowlisted => APPLIED
  - T3.2 unsupported_version => UNSUPPORTED_EVENT_VERSION
  - T3.3 unknown_kind => UNKNOWN_EVENT_KIND


## Phase 20 — Work Context Mechanism (Added)

Introduced docs/core/work-context.md.

Purpose:
Provide a small execution context document that allows a new chat
session to resume work without reconstructing the entire conversation.

This file is temporary per phase and does not override canonical docs.

## Phase 20 — Envelope Event Identity Hardening + Replay Safety (Closed)

Implemented:
- Verified canonical write gate: Supabase RPC apply_envelope is the only authority to mutate booking_state.
- Enforced projection-only discipline: booking_state is materialized exclusively via DB-generated STATE_UPSERT events.
- Verified replay safety: duplicate envelopes must not insert additional events and must not mutate booking_state.
- Verified no redundant STATE_UPSERT mutations detected by database inspection query (0 rows returned).
- Captured full Supabase stored function definitions into artifacts/supabase/Functions.sql for canonical reference.

Operational decision:
- Legacy rows with NULL status remain tolerated for availability checks (treated as active) to preserve forward compatibility.
- Future hardening: backfill and strict non-NULL status enforcement may be scheduled in a later phase.


## Phase 21 — External Ingestion Boundary Definition (Closed)

Defined the canonical OTA ingestion boundary.

Key architectural decisions:
- External payloads must be normalized into canonical envelopes before entering the system.
- Only apply_envelope may write to event_log.
- booking_state remains projection-only.
- External event ingestion limited to allowlisted kinds.

Result:
External integration surface defined without compromising replay safety or canonical event authority.

## Phase 22 — OTA Ingestion Boundary (Closed)

Implemented:
- Introduced dedicated OTA ingestion adapter layer under src/adapters/ota.
- External channel payloads normalized into canonical booking events.
- Validation pipeline implemented prior to canonical envelope creation.
- Canonical envelope conversion enforced before calling apply_envelope.
- Idempotency key propagation from external payload into canonical envelope_id.
- Deterministic ingestion responses: APPLIED / DUPLICATE / REJECTED.

Architecture outcome:
External systems can now integrate with iHouse Core through a strict
anti-corruption boundary that preserves the deterministic event kernel.

External payload semantics are isolated from the canonical event model,
ensuring replay safety and preventing external schema drift from leaking
into the core domain.

## Phase 23 — External Event Semantics Hardening (Closed)

Implemented:

- Added deterministic OTA semantic classification layer.
- Introduced src/adapters/ota/semantics.py.
- OTA events are now explicitly classified into semantic kinds:
  - CREATE
  - CANCEL

Validation pipeline updated:

normalize
-> validate_normalized_event
-> classify_normalized_event
-> validate_classified_event
-> to_canonical_envelope
-> validate_canonical_envelope
-> append_event

Responsibilities of the new layer:

- Deterministic classification of normalized OTA provider events.
- Semantic self-consistency validation of OTA events before envelope creation.
- Deterministic rejection codes for invalid provider semantics.

Architectural invariants preserved:

- No read-side booking lookup added.
- No duplicate detection implemented in application layer.
- No new persistence tables.
- No change to canonical event schema.
- No change to apply_envelope DB gate behavior.

Result:

External OTA payload semantics are now hardened before canonical envelope creation,
while the canonical database gate remains the sole authority for booking identity
and duplicate enforcement.

## Phase 24 — OTA Modification Semantics (Closed)

Implemented:

- Extended OTA semantic classification with the intermediate semantic kind:
  - MODIFY
- Booking.com adapter now explicitly recognizes:
  - reservation_modified
- Modification events no longer fall through as unsupported provider events.
- Unresolved Booking.com modification events are rejected deterministically
  at the adapter boundary.

Validation outcome:

reservation_modified
-> classify_normalized_event => MODIFY
-> validate_classified_event => allowed
-> to_canonical_envelope => deterministic rejection when no safe payload-only resolution exists

Architectural invariants preserved:

- No booking_state lookup added.
- No duplicate detection implemented in application layer.
- No change to canonical DB gate behavior.
- No change to canonical event schema.
- No hidden fallback from MODIFY into CREATE.

Result:

The system now explicitly recognizes OTA modification events while preserving
the deterministic ingestion contract and rejecting unresolved modification
semantics before canonical envelope creation.


---------------------------------------------------------------------

Phase 25 – OTA Modification Resolution Rules (Closed)

The system introduced explicit semantic recognition for OTA
modification events through the canonical event class MODIFY.

Provider payload inspection demonstrated that OTA modification
notifications cannot be deterministically interpreted from payload
alone without state lookup.

To preserve canonical determinism the system retains the rule:

MODIFY
→ deterministic reject-by-default

Future handling of OTA modification notifications may occur through a
separate synchronization or recovery layer outside the canonical event
ingestion boundary.


## Phase 26 — OTA Provider Verification (Closed)

Objective

Verify whether OTA providers expose deterministic modification signals
in their payload schemas.

Providers inspected:

Booking.com  
Expedia  
Airbnb  
Agoda  
Trip.com

Findings

OTA providers emit modification notifications but do not expose
deterministic modification subtypes that can be interpreted without
booking_state lookup.

Most providers follow a model:

notification → fetch reservation snapshot

This model requires state comparison and therefore violates the
canonical adapter contract.

Result

No deterministic payload-only subset for:

MODIFY → UPDATE

could be proven.

Architectural decision

The canonical rule remains:

MODIFY  
→ deterministic reject-by-default


## Phase 27 — Multi-OTA Adapter Architecture (Closed)

Implemented:

- Added shared OTA orchestration pipeline:
  - src/adapters/ota/pipeline.py
- Refactored src/adapters/ota/service.py so the service delegates
  orchestration to the shared pipeline
- Preserved provider-isolated adapters behind the shared pipeline
- Extended src/adapters/ota/registry.py to support multiple providers
- Added an Expedia scaffold adapter:
  - src/adapters/ota/expedia.py

Validation outcome:

- Existing test suite remained green after the refactor
- Multi-provider adapter registration now works without changing:
  - semantics.py
  - validator.py
  - canonical DB gate behavior

Architectural result:

The system now supports multi-provider OTA extension through a shared
ingestion pipeline and provider registry.

Important precision:

- Booking.com remains the concrete provider implementation
- Expedia was introduced as an architectural scaffold adapter used to
  validate multi-provider extensibility
- Airbnb, Agoda, and Trip.com were not implemented in this phase

Invariants preserved:

- apply_envelope remains the only write authority
- booking_state remains projection-only
- MODIFY remains deterministic reject-by-default
- provider semantics remain isolated from the shared pipeline

## Phase 28 — OTA External Surface Canonicalization (Closed)

Objective

Resolve the ambiguity in the OTA external ingestion surface by replacing
the generic transport envelope `BOOKING_SYNC_INGEST` with explicit
canonical business events.

Decision

The system no longer accepts a single external OTA ingestion envelope.

Instead, OTA adapters must emit canonical business events that represent
the deterministic lifecycle outcome of the OTA notification.

New canonical external events:

- BOOKING_CREATED
- BOOKING_CANCELED

Rationale

A single ingestion envelope hides business semantics inside payload
fields and makes the event ledger harder to reason about.

Explicit canonical business events ensure that the event log represents
clear domain facts rather than transport containers.

Implementation change

OTA adapters now emit canonical business events directly after semantic
classification:

CREATE  → BOOKING_CREATED  
CANCEL  → BOOKING_CANCELED

MODIFY events remain unsupported and follow the rule:

MODIFY  
→ deterministic reject-by-default

Architectural invariants preserved

- apply_envelope remains the only write authority
- booking_state remains projection-only
- event_log remains append-only
- adapters must not read booking_state
- adapters must not reconcile booking history

Outcome

The canonical external event surface now represents explicit domain
facts instead of transport envelopes, improving auditability and
multi-provider scalability.

## Phase 29 — OTA Ingestion Replay Harness (Closed)

Implemented:

- Added deterministic OTA replay verification as test tooling.
- Added replay harness coverage for:
  - BOOKING_CREATED
  - BOOKING_CANCELED
  - duplicate replay
  - MODIFY rejection
  - invalid payload rejection
- Verified replay through the orchestration path:
  - ingest_provider_event
  - canonical envelope creation
  - CoreExecutor.execute
- Added minimal OTA contract alignment required for replay execution:
  - tenant_id propagation aligned across service and pipeline
  - classification function naming aligned
  - semantic classification aligned to normalized payload structure
  - ClassifiedBookingEvent shape aligned to schema

Validation outcome:

- Existing test suite remained green after the alignment
- Replay harness scenarios passed
- No new write path was introduced
- apply_envelope remained the sole canonical write authority

Architectural result:

The system now includes deterministic OTA replay verification across
the ingestion-to-execution path without weakening canonical invariants.

---

## Phase 30 – OTA Ingestion Interface Hardening

Status: Active

Objective:
Harden the OTA ingestion interface that connects provider adapters to
the canonical execution path without changing canonical event
semantics.

Confirmed runtime handoff:
ingest_provider_event
→ process_ota_event
→ canonical envelope
→ IngestAPI.ingest
→ CoreExecutor.execute
→ apply_envelope

What this phase locks:

- OTA service entry remains thin
- shared OTA pipeline owns normalization, validation, classification,
  and envelope construction
- provider adapters remain provider-specific only
- core ingest API is the explicit bridge into execution
- CoreExecutor remains the single execution boundary
- OTA code does not call apply_envelope directly

Out of scope:

- reconciliation
- amendment handling
- OTA snapshot fetch
- out-of-order buffering
- historical transport cleanup
- adapter reads from booking_state

Architectural result:
The OTA-to-core handoff is now treated as a first-class explicit
boundary shared by production ingest flow and replay verification.

## Phase 31 — Closure

Closed Phase 31 after completing contract-verification and documentation
hardening for the OTA ingestion boundary.

Completed:
- aligned active docs to `IngestAPI.append_event`
- clarified OTA service language from apply-facing wording to core-ingest wording
- archived closed phase specs under `docs/archive/phases`
- introduced `docs/core/improvements/future-improvements.md`

No canonical business semantics changed.
No alternative write path was introduced.

Next active phase:
Phase 32 – OTA Ingestion Contract Test Verification

## Phase 32 — OTA Ingestion Contract Test Verification (Closed)

Completed:

- added direct executable verification for thin OTA service entry
- added direct executable verification for ordered shared OTA pipeline responsibilities
- added direct executable verification for core ingest rejection when executor wiring is missing
- verified that replay uses the same public ingest contract through IngestAPI.append_event
- verified that no tested OTA runtime path bypasses core ingest or CoreExecutor
- reran relevant smoke and invariant checks successfully

Result:

The OTA-to-core runtime contract locked by Phases 30 and 31 is now verified by executable evidence.

No canonical business semantics changed.
No alternative write path was introduced.
MODIFY remains deterministic reject-by-default.

## Phase 33 — OTA Retry Business Idempotency Discovery (Closed)

Completed:

- inspected OTA identity fields across normalized payload, canonical envelope, executor path, and canonical Supabase apply path
- verified that OTA transport idempotency currently derives from provider external_event_id
- verified that canonical Supabase business handling already exists for canonical emitted business events
- verified that apply_envelope performs canonical business handling from emitted events rather than from the raw OTA envelope alone
- verified that the active OTA runtime path currently appears misaligned with the canonical emitted business event contract expected by apply_envelope
- documented the strongest verified risk as runtime mapping and routing misalignment rather than an intrinsic failure of canonical Supabase business dedup

Result:

Phase 33 did not prove an intrinsic failure of canonical Supabase business dedup.

Phase 33 did establish a likely alignment gap between the active OTA runtime path and the canonical emitted business event contract enforced by apply_envelope.

No canonical business semantics changed.
No alternative write path was introduced.
Next active phase:
Phase 34 — OTA Canonical Event Emission Alignment

## Phase 34 — OTA Canonical Event Emission Alignment (Closed)

Completed:

- [Claude]
- verified `BOOKING_CREATED` routes to `booking-created-noop` skill emitting zero events
- verified `BOOKING_CANCELED` has no active route in `kind_registry`
- verified payload shape mismatch between OTA envelope and `apply_envelope` expectations
- identified exact canonical payload fields required for Supabase enforcement
- defined the minimal alignment change required for Phase 35 (2 skills + registry updates)

Result:

Phase 34 proved a routing and emitted-event alignment gap in the active OTA runtime path.
It did not prove an intrinsic failure of canonical Supabase business dedup.
It did not justify architecture redesign.

No canonical business semantics changed.
No alternative write path was introduced.
No closed semantic decision was reopened.
## Phase 35 — OTA Canonical Emitted Event Alignment Implementation (Closed)

Completed:

- [Claude]
- implemented `booking_created` skill: transforms OTA envelope payload into canonical BOOKING_CREATED emitted event shape
- implemented `booking_canceled` skill: emits BOOKING_CANCELED with booking_id derived from provider + reservation_id
- updated `kind_registry.core.json`: BOOKING_CREATED → booking-created, BOOKING_CANCELED → booking-canceled
- updated `skill_exec_registry.core.json`: routing entries for both new skills, all existing entries preserved
- added 17 contract tests covering skill unit behavior, payload shape, executor routing alignment, and regression guards
- verified E2E against live Supabase: BOOKING_CREATED → status APPLIED, state_upsert_found true
- verified E2E against live Supabase: BOOKING_CANCELED → status APPLIED, state_upsert_found true
- all 30 pytest tests pass (2 pre-existing SQLite invariant failures unrelated to this phase)

Result:

OTA-originated BOOKING_CREATED and BOOKING_CANCELED now reach apply_envelope through the canonical emitted business event contract.
The alignment gap proved by Phase 34 is resolved.

No canonical business semantics changed.
No alternative write path was introduced.
No new canonical event kinds were introduced.
No closed semantic decision was reopened.
## Phase 36 — Business Identity Canonicalization (Closed)

Completed:

- [Claude]
- verified booking_id construction rule is deterministic and consistent: {source}_{reservation_ref}
- verified apply_envelope enforces business-level dedup in two layers: by booking_id and by composite (tenant_id, source, reservation_ref, property_id)
- E2E tested: duplicate BOOKING_CREATED with different request_id returns ALREADY_EXISTS, no new booking_state row written
- formally documented canonical booking_id rule
- resolved backlog items: Business Idempotency Beyond Envelope Idempotency, Business Identity Enforcement
- resolved Phase 33 follow-up note in future-improvements.md

Result:

The canonical booking_id rule is: booking_id = "{source}_{reservation_ref}".
apply_envelope already provides sufficient business-level duplicate protection for current OTA identity patterns.
No additional business-idempotency registry is required at this stage.

No canonical business semantics changed.
No alternative write path was introduced.
No closed semantic decision was reopened.
## Phase 37 — External Event Ordering Protection Discovery (Closed)

Completed:

- [Claude]
- E2E verified: BOOKING_CANCELED before BOOKING_CREATED raises BOOKING_NOT_FOUND (P0001) from apply_envelope
- verified: no buffering, retry, or ordering layer exists in the active OTA runtime path
- verified: correct order (CREATED then CANCELED) returns APPLIED for both — no regression
- classified current behavior: deterministic rejection, not silent data loss
- updated future-improvements.md backlog item with verified behavioral description

Result:

When BOOKING_CANCELED arrives before BOOKING_CREATED, apply_envelope raises BOOKING_NOT_FOUND.
The event is rejected deterministically and is lost — there is no dead-letter store or retry queue.
This is a known open gap, classified as deferred in the backlog.
No canonical invariants are violated by the current behavior.

No canonical business semantics changed.
No alternative write path was introduced.
No closed semantic decision was reopened.
## Phase 38 — Dead Letter Queue for Failed OTA Events (Closed)

Completed:

- [Claude]
- created Supabase table `ota_dead_letter` (append-only, RLS enabled for service_role)
- deployed migration via `supabase db push`: `20260308_phase38_ota_dead_letter.sql`
- implemented `src/adapters/ota/dead_letter.py`: best-effort, non-blocking DLQ write
- updated `src/adapters/ota/service.py`: added `ingest_provider_event_with_dlq` — original thin wrapper preserved unchanged
- added 6 contract tests covering: non-blocking behavior, error swallowing, stderr logging, Supabase insert call, backward compatibility guard
- E2E verified: BOOKING_CANCELED before BOOKING_CREATED → apply_envelope BOOKING_NOT_FOUND → DLQ row written and queryable

Result:

Rejected OTA events are now preserved in `ota_dead_letter` instead of being silently lost.
The DLQ is append-only and never bypasses apply_envelope.
No canonical invariants are violated.
36 tests pass (2 pre-existing SQLite failures unrelated).

No canonical business semantics changed.
No alternative write path was introduced.
No closed semantic decision was reopened.
## Phase 39 — DLQ Controlled Replay (Closed)

Completed:

- [Claude]
- migration `20260308174500_phase39_dlq_replay_columns.sql`: added replayed_at, replay_result, replay_trace_id columns to ota_dead_letter
- deployed via supabase db push, verified E2E (columns queryable and writable)
- implemented `src/adapters/ota/dlq_replay.py`: replay_dlq_row(row_id) — safe, idempotent, always routes through apply_envelope
- updated `future-improvements.md`: marked DLQ as resolved, added 4 new forward-looking items (DLQ Controlled Replay, DLQ Observability, Idempotent DLQ Replay Tracking, booking_id Stability)
- 7 contract tests added: idempotency guard, apply_envelope routing, new idempotency key, unknown event_type, missing row, outcome persistence
- E2E verified: BOOKING_CREATED → BOOKING_CANCELED_IN_DLQ → replay_dlq_row → APPLIED + idempotent second replay

Result:

DLQ rows are now actionable. Operators can replay specific rejected OTA events through the canonical pipeline using replay_dlq_row(row_id). Replay outcome is persisted on the DLQ row.
43 tests pass (2 pre-existing SQLite failures unrelated).

No canonical business semantics changed.
No automatic retry was introduced.
No canonical write path was bypassed.
## Phase 40 — DLQ Observability (Closed)

Completed:

- [Claude]
- Supabase view `ota_dlq_summary` created via migration `20260308184200_phase40_dlq_summary_view.sql`
- implemented `src/adapters/ota/dlq_inspector.py`: get_pending_count(), get_replayed_count(), get_rejection_breakdown()
- 11 contract tests added (all unit/mocked, no live Supabase required)
- E2E verified: inspector returned live data (3 pending, 1 replayed, breakdown by event_type + rejection_code)

Result:

DLQ is now observable. Operators can query pending rejections, replay history, and rejection breakdown using dlq_inspector.py or the ota_dlq_summary view directly in Supabase Studio.
54 tests pass (2 pre-existing SQLite failures unrelated).

No write paths added.
No booking_state reads added.
No canonical event behaviour changed.
## Phase 41 — DLQ Alerting Threshold (Closed)

Completed:

- [Claude]
- implemented `src/adapters/ota/dlq_alerting.py`:
  - `DLQAlertResult` (frozen dataclass): pending_count, threshold, exceeded, message
  - `check_dlq_threshold(threshold, client=None)` — emits structured WARNING to stderr when exceeded
  - `check_dlq_threshold_default(client=None)` — reads DLQ_ALERT_THRESHOLD env var (default: 10)
- 13 contract tests added: threshold/boundary/env logic, stderr emission, frozen dataclass guard
- no Supabase tables, no migrations, no write paths added

Result:

Operators can now call check_dlq_threshold_default() on a schedule and receive a structured WARNING to stderr when unresolved DLQ rows accumulate above threshold.
67 tests pass (2 pre-existing SQLite failures unrelated).
## Phase 42 — Reservation Amendment Discovery (Closed)

Type: Discovery only. No code written.

Completed:

- [Claude]
- Read and analyzed: semantics.py, bookingcom.py, expedia.py, validator.py, apply_envelope SQL
- Answered all 7 discovery questions; findings documented in phase-42-spec.md

Key findings:

1. MODIFY classification already exists in semantics.py and is deterministic
2. Both adapters (Booking.com, Expedia) throw ValueError for MODIFY — by design
3. Amendment payload fields (check_in, check_out, guests) are not normalized — only provider_payload blob
4. apply_envelope needs: new BOOKING_AMENDED enum kind, lifecycle state guard, field merge logic
5. booking_state has no explicit 'status' column — lifecycle state must be derived from event log
6. DLQ layer (Phases 38-39) provides replay infrastructure but no booking-level ordering rule
7. booking_id is stable across amendment events (Q7: ✅)

Prerequisites for BOOKING_AMENDED: 3 of 10 satisfied.

Next recommended phase: Phase 43 — booking_state Status Column (adds explicit ACTIVE/CANCELED status tracking as precondition for amendment lifecycle guard).

MODIFY remains deterministic reject-by-default.
## Phase 43 — booking_state Status Verification (Closed)

Key correction from Phase 42:

Phase 42 claimed booking_state has no status column. After reading the actual schema SQL, the column already exists and apply_envelope already sets it:
- BOOKING_CREATED → status = 'active'
- BOOKING_CANCELED → status = 'canceled'

Completed:

- [Claude]
- E2E verified: BOOKING_CREATED → status=active, BOOKING_CANCELED → status=canceled on live Supabase ✅
- implemented `src/adapters/ota/booking_status.py`: get_booking_status(booking_id, client=None) → str | None
- 9 contract tests: unknown=None, active, canceled, None field, read-only guard (no insert/update/delete), table and field assertions
- future-improvements.md: added BOOKING_AMENDED Support entry with 4/10 prerequisites satisfied
- Amendment prerequisites updated: booking_state.status → ✅ (was ❌ in Phase 42 finding)

Result:

booking_state.status is verified. get_booking_status() is available for future amendment lifecycle guard.
76 tests pass (2 pre-existing SQLite failures unrelated).
No schema changes. No migration.
## Phase 44 — OTA Ordering Buffer (Closed)

Completed:

- [Claude]
- Migration: `ota_ordering_buffer` table — FK to ota_dead_letter, booking_id, event_type, status (waiting|replayed|expired), RLS, index ix_ordering_buffer_booking_waiting
- implemented `src/adapters/ota/ordering_buffer.py`:
  - buffer_event(dlq_row_id, booking_id, event_type, client) → int
  - get_buffered_events(booking_id, client) → list[dict] (only 'waiting' rows)
  - mark_replayed(buffer_id, client) → None
- 10 contract tests — buffer write, field validation, status filter, empty result, mark_replayed table/filter/value
- E2E: buffer → waiting read → mark_replayed → empty confirmed on live Supabase

Result:

Out-of-order OTA events (BOOKING_NOT_FOUND) can now be explicitly buffered by booking_id. When BOOKING_CREATED arrives (Phase 45), the buffer is queryable and ready for replay.
86 tests pass (2 pre-existing SQLite failures unrelated).
## Phase 45 — Ordering Buffer Auto-Trigger on BOOKING_CREATED (Closed)

Completed:

- [Claude]
- implemented `src/adapters/ota/ordering_trigger.py`: trigger_ordered_replay(booking_id, client) → dict
  - reads get_buffered_events(booking_id)
  - for each: replay_dlq_row(dlq_row_id) → mark_replayed(buffer_id)
  - best-effort: failure per row logged to stderr, continues
  - returns {booking_id, replayed, failed, results}
- integrated into service.py: after BOOKING_CREATED APPLIED → trigger_ordered_replay(booking_id), non-blocking
- 7 contract tests: empty buffer, single replay, booking_id passthrough, failure logged not raised, multi-row, partial failure continues, result shape
- E2E verified: CANCELED → DLQ → buffer → CREATED APPLIED → auto-trigger → 0 waiting in buffer

Result:

The ordering loop is now closed. Out-of-order events that were buffered as 'waiting' are automatically replayed when their prerequisite BOOKING_CREATED arrives.
93 tests pass (2 pre-existing SQLite failures unrelated).
## Phase 46 — System Health Check (Closed)

Rationale:

Large SaaS companies (Stripe, Twilio, Airbnb) build a single callable health check before expanding feature surface. Before introducing BOOKING_AMENDED or going to production, iHouse Core needs one call that tells operators whether the system is healthy.

Completed:

- [Claude]
- implemented `src/adapters/ota/health_check.py`:
  - ComponentStatus (frozen dataclass): name, ok, detail
  - HealthReport (frozen dataclass): ok, components[5], dlq_pending, ordering_buffer_pending, timestamp
  - system_health_check(client=None) → HealthReport
  - 5 components: supabase_connectivity, ota_dead_letter, ota_ordering_buffer, dlq_threshold, ordering_buffer_waiting
  - ok=True only if all components ok AND DLQ threshold not exceeded
  - never raises — all exceptions caught per component
- 10 contract tests: healthy, 5 components, frozen, supabase down, threshold exceeded, ordering buffer informational, never raises, dlq_pending in report
- E2E live: OVERALL OK ✅ — all 5 components green, DLQ pending=5 < threshold=10

Result:

Operators can call system_health_check() and get a structured readiness report in under a second.
103 tests pass (2 pre-existing SQLite failures unrelated).
No Supabase migrations. No new tables.
## Phase 47 — OTA Payload Boundary Validation (Closed)

Rationale:

Every production API (Stripe, Twilio) validates inputs at the boundary before the canonical system. Previously, malformed OTA payloads could fail deep inside pipeline with opaque errors. Phase 47 makes rejections explicit and structured at the entry point.

Completed:

- [Claude]
- implemented `src/adapters/ota/payload_validator.py`:
  - PayloadValidationResult (frozen dataclass): valid, errors, provider, event_type_raw
  - validate_ota_payload(provider, payload) → PayloadValidationResult
  - 6 rules: PROVIDER_REQUIRED, PAYLOAD_MUST_BE_DICT, RESERVATION_ID_REQUIRED, TENANT_ID_REQUIRED, OCCURRED_AT_INVALID, EVENT_TYPE_REQUIRED
  - All errors collected together (not fail-fast)
  - Accepts event_type / type / action / event / status as alternatives
- integrated into pipeline.py at top of process_ota_event (before normalize)
- 16 contract tests: valid payload, each rule, multi-error, frozen dataclass, alternative event_type fields, pipeline raises on invalid
- Updated test_ota_pipeline_contract.py to include required fields (backward compat fix)
- 119 tests pass (2 pre-existing SQLite failures unrelated)

Result:

Malformed OTA payloads are caught at the boundary with structured error codes before touching the canonical pipeline. This is a prerequisite for BOOKING_AMENDED support.
## Phase 48 — Idempotency Key Standardization (Closed)

Rationale:

Stripe's idempotency keys are namespaced and deterministic. Previously, both adapters set idempotency_key = raw external_event_id from the OTA provider. Two providers could emit the same event_id for different events, causing cross-provider key collisions.

Completed:

- [Claude]
- implemented `src/adapters/ota/idempotency.py`:
  - generate_idempotency_key(provider, event_id, event_type) → str
  - Format: "{provider}:{event_type}:{event_id}" (lowercase, colon-sanitized)
  - validate_idempotency_key(key) → bool (checks 3-segment format)
- Updated bookingcom.py and expedia.py to use generate_idempotency_key
- 19 contract tests: format, cross-provider uniqueness, cross-type uniqueness, lowercase, colon sanitization, empty raises, validate, adapter integration
- Updated test_ota_replay_harness.py and test_ota_pipeline_contract.py for new key format
- 138 tests pass (2 pre-existing SQLite failures unrelated)

Result:

All OTA idempotency keys are now namespaced, collision-safe, and deterministic. The format is stable and ready for BOOKING_AMENDED keys when implemented.
## Phase 49 — Normalized AmendmentPayload Schema (Closed)

Rationale:

Before adding BOOKING_AMENDED to apply_envelope, we need a canonical, provider-agnostic amendment payload structure. Booking.com puts amendment data in new_reservation_info, Expedia puts it in changes.dates. Phase 50 cannot know about provider-specific shapes.

Completed:

- [Claude]
- Added AmendmentFields (frozen=True) to schemas.py:
  - new_check_in: Optional[str]
  - new_check_out: Optional[str]
  - new_guest_count: Optional[int]
  - amendment_reason: Optional[str]
- implemented `src/adapters/ota/amendment_extractor.py`:
  - extract_amendment_bookingcom(payload) → reads new_reservation_info
  - extract_amendment_expedia(payload) → reads changes.dates, changes.guests
  - normalize_amendment(provider, payload) → dispatcher; raises on unknown provider
  - helpers: _nonempty, _int_or_none
- 15 contract tests: frozen schema, both extractors, missing fields as None, coercion, unknown provider, case-insensitive dispatch, return type
- 153 tests pass

Result:

The normalized AmendmentPayload schema is defined. Both adapters have a tested extraction path. Phase 50 can now implement apply_envelope BOOKING_AMENDED branch using AmendmentFields as the canonical input.

## Phase 50 — BOOKING_AMENDED DDL + apply_envelope Branch (Closed)

Rationale:

The final 3 prerequisites for BOOKING_AMENDED were all SQL/stored-procedure layer changes. Phase 50 delivers them atomically and verifies them E2E on live Supabase.

Completed:

- Step 1 (Phase 50 previous chat): ALTER TYPE event_kind ADD VALUE 'BOOKING_AMENDED' — already deployed ✅
- Step 2: Deployed via `supabase db push` (migration `20260308210000_phase50_step2_apply_envelope_amended.sql`):
  - CREATE OR REPLACE FUNCTION apply_envelope — full replacement including BOOKING_AMENDED branch
  - BOOKING_AMENDED branch logic:
    1. Extract booking_id → raises BOOKING_ID_REQUIRED if missing
    2. SELECT booking_state FOR UPDATE (row-level lock)
    3. ACTIVE-state lifecycle guard → raises AMENDMENT_ON_CANCELED_BOOKING if status='canceled'
    4. Extract new_check_in / new_check_out (both optional)
    5. Validate dates if both provided (check_out > check_in)
    6. Write STATE_UPSERT to event_log (append-only)
    7. UPDATE booking_state: check_in/check_out via COALESCE (preserves existing if not provided), status stays 'active'
- Written `tests/test_booking_amended_e2e.py` — 5 E2E tests, all passing on live Supabase:
  - BOOKING_CREATED → APPLIED ✅
  - BOOKING_AMENDED both dates → APPLIED, check_in/check_out updated, status=active, version=2 ✅
  - BOOKING_AMENDED partial (check_in only) → check_in updated, check_out preserved via COALESCE ✅
  - BOOKING_AMENDED on CANCELED booking → AMENDMENT_ON_CANCELED_BOOKING ✅
  - BOOKING_AMENDED on non-existent booking → BOOKING_NOT_FOUND ✅

Result:

BOOKING_AMENDED prerequisites: 10/10 satisfied.
apply_envelope is the verified single write authority for BOOKING_AMENDED.
158 tests pass (2 pre-existing SQLite failures unrelated).
No canonical invariants changed. No alternative write path introduced.

Next phase: Phase 51 — Python Pipeline Integration (semantics.py + service.py BOOKING_AMENDED routing)


## Phase 51 — Python Pipeline Integration: BOOKING_AMENDED Routing (Closed)

Rationale:

Phase 50 delivered apply_envelope with a full BOOKING_AMENDED branch on Supabase.
Phase 51 wires the Python OTA adapter pipeline to route reservation_modified events
through as canonical BOOKING_AMENDED envelopes, closing the end-to-end loop.

Completed:

- semantics.py: BOOKING_AMENDED added to BookingSemanticKind enum; reservation_modified → BOOKING_AMENDED (was MODIFY)
- validator.py: BOOKING_AMENDED allowed in validate_classified_event; added to SUPPORTED_CANONICAL_TYPES
- bookingcom.py: to_canonical_envelope extended with BOOKING_AMENDED branch — builds booking_id + AmendmentFields from normalize_amendment
- test_ota_replay_harness.py: stale MODIFY-rejection test updated to verify new BOOKING_AMENDED envelope shape
- tests/test_booking_amended_contract.py: 22 new contract tests (semantics, validator, pipeline envelope shape, regression)

Result:

180 tests pass (2 pre-existing SQLite failures unrelated).

reservation_modified → BOOKING_AMENDED → apply_envelope — end-to-end verified.
No canonical invariants changed. No alternative write path introduced. apply_envelope remains sole write authority.

Next phase: Phase 52 — TBD

## Phase 52 — GitHub Actions CI Hardening (Closed)

Rationale:

With 180 tests across unit, contract, and E2E suites, manual test execution is not scalable.
Phase 52 hardens the existing CI workflows to produce a reliable green gate on every push.

Completed:

- Audited existing .github/workflows/ci.yml and ci_invariants.yml against actual repo state
- ci.yml fixes:
  - Removed self-defeating "Enforce no direct pytest invocation" step (found pytest in its own file)
  - Added --ignore=tests/invariants (SQLite tests require IHOUSE_ALLOW_SQLITE=1 — local only)
  - Added --ignore=tests/test_booking_amended_e2e.py (live Supabase tests — manual only)
  - Made HTTP smoke step conditional on IHOUSE_API_KEY secret presence
  - Merged venv + install into single step
- ci_invariants.yml fixes:
  - Replaced broken "run: # comment" step with actual venv+install+pytest commands
  - Added IHOUSE_ALLOW_SQLITE=1 so invariant tests can run on SQLite as intended
- Validated CI command locally: 173 passed, 2 skipped, 0 failed

Result:

CI now produces a reliable green pass on every push without requiring live Supabase or API secrets.
The invariants workflow now actually runs (was a no-op before).
No canonical code touched. No DB changes.

Next phase: Phase 53 — Expedia adapter full implementation (BOOKING_AMENDED support)

## Phase 53 — Expedia Adapter Full Implementation (Closed)

Rationale:

Phase 27 introduced Expedia as a scaffold adapter. Phase 53 completes it to feature parity
with Booking.com, including BOOKING_AMENDED support.

Completed:

- src/adapters/ota/expedia.py — read fully before editing:
  - Added BOOKING_AMENDED branch to to_canonical_envelope()
  - Added normalize_amendment import (reads changes.dates / changes.guests)
  - booking_id = expedia_{reservation_id} — same deterministic rule as bookingcom
  - canonical_payload includes: booking_id, new_check_in, new_check_out, new_guest_count, amendment_reason
  - normalize() unchanged — field mapping already correct
- tests/test_expedia_contract.py: 17 contract tests
  - normalize field mapping
  - BOOKING_CREATED: envelope type, key format, payload fields, tenant propagation
  - BOOKING_CANCELED: envelope type, key format
  - BOOKING_AMENDED: type, booking_id, check_in, check_out, guests, reason, missing fields as None, key format
  - Cross-provider key isolation (same event_id → different keys for expedia vs bookingcom)

Result:

190 tests pass (CI-safe suite: 190 passed, 2 skipped).
Expedia now has feature parity with Booking.com across all 3 event kinds.
No canonical code touched. No DB changes. No apply_envelope changes.

Next phase: Phase 54 — Airbnb adapter

## Phase 54 — Airbnb Adapter (Closed)

Rationale:

Add Airbnb as the third full OTA provider adapter.

Completed:

- amendment_extractor.py (read fully before editing):
  - Added extract_amendment_airbnb() — reads alteration.new_check_in/out/guest_count/reason
  - Added "airbnb" to _SUPPORTED_PROVIDERS
  - Added dispatch in normalize_amendment()
- src/adapters/ota/airbnb.py (new file):
  - normalize(): maps listing_id → property_id (Airbnb-specific field)
  - to_canonical_envelope(): CREATE / CANCEL / BOOKING_AMENDED branches
  - booking_id = airbnb_{reservation_id} — same deterministic rule
- registry.py (read fully before editing): registered AirbnbAdapter
- semantics.py: added Airbnb event type aliases:
  - reservation_create → CREATE
  - reservation_cancel → CANCEL
  - alteration_create / alteration → BOOKING_AMENDED
- tests/test_airbnb_contract.py: 18 contract tests
- tests/test_amendment_schema_contract.py: updated stale "airbnb raises ValueError" test
  - airbnb is now supported; test now uses "tripadvisor" as truly unknown provider
  - Added positive test for airbnb dispatch

Result:

209 tests pass (CI-safe suite: 209 passed, 2 skipped, 0 failed).
All 3 adapters (Booking.com, Expedia, Airbnb) now have feature parity.
No canonical code touched. No DB changes.

Next phase: Phase 55 — TBD (Agoda / Trip.com / Observability / Webhook auth)

## Phase 55 — Agoda Adapter (Closed)

Rationale:

Add Agoda as the fourth full OTA provider adapter.

Completed:

- amendment_extractor.py: extract_amendment_agoda() reads modification.check_in_date/check_out_date/num_guests/reason
- src/adapters/ota/agoda.py: new adapter — booking_ref → reservation_id mapping, CREATE/CANCEL/AMENDED branches
- registry.py: registered AgodaAdapter
- semantics.py: added booking.created / booking.cancelled / booking.canceled / booking.modified aliases
- payload_validator.py: Rule 3 extended to accept booking_ref as valid alternative to reservation_id
- tests/test_agoda_contract.py: 18 contract tests — normalize, CREATE, CANCEL, AMENDED, 4-provider cross-isolation

Result:

227 tests pass (CI-safe suite: 227 passed, 2 skipped).
All 4 adapters (Booking.com, Expedia, Airbnb, Agoda) at full parity.
No canonical code touched. No DB changes.

Next phase: Phase 56 — Trip.com adapter

## Phase 56 — Trip.com Adapter (Closed)

Rationale:

Add Trip.com as the fifth full OTA provider adapter.

Completed:

- amendment_extractor.py: extract_amendment_tripcom() reads changes.check_in/check_out/guests/remark + dispatcher
- src/adapters/ota/tripcom.py: new adapter — order_id → reservation_id, hotel_id → property_id
- registry.py: registered TripComAdapter
- semantics.py: added order_created / order_cancelled / order_canceled / order_modified aliases
- payload_validator.py: Rule 3 extended to accept order_id (Trip.com's reservation token)
- tests/test_tripcom_contract.py: 18 contract tests + 5-provider cross-isolation

Result:

246 tests pass (CI-safe suite: 246 passed, 2 skipped).
All 5 OTA adapters at full parity: Booking.com, Expedia, Airbnb, Agoda, Trip.com.
No canonical code touched. No DB changes.

Next phase: Phase 57 — Hardening (webhook auth, payload signature verification)

## Phase 57 — Webhook Signature Verification (Closed)

Rationale:

Security hardening — 5 adapters with no signature verification is a critical gap.
Any attacker could send fake webhooks. HMAC-SHA256 closes this entirely.

Completed:

- src/adapters/ota/signature_verifier.py:
  - verify_webhook_signature(provider, raw_body, signature_header) — main entry point
  - compute_expected_signature() — test fixture helper
  - get_signature_header_name() — utility
  - SignatureVerificationError — raised only when secret configured + sig wrong
  - Dev mode: secret not set → skip with warning (no CI breakage)
  - Constant-time comparison via hmac.compare_digest() (timing attack safe)
  - sha256= prefix stripped before comparison
- tests/test_signature_verifier.py: 24 tests
  - Dev-mode skip (2): no secret → no raise
  - Correct signature (3): with prefix, without prefix, with whitespace
  - Wrong signature (4): tampered body, wrong secret, missing header, garbage
  - Unknown provider (1): ValueError not SignatureVerificationError
  - All 5 providers (10): skip + verify parametrized
  - Header names (2)
  - compute_expected_signature (2)

Result:

270 tests pass (270 passed, 2 skipped).
Pipeline not yet wired to HTTP layer — Phase 58 will integrate into FastAPI/handler.

Next phase: Phase 58 — HTTP ingestion layer (FastAPI endpoint) with signature verification

## Phase 58 — HTTP Ingestion Layer (Closed)

Rationale:

Phase 57 delivered HMAC-SHA256 signature verification. Phase 58 wires
signature verification, payload validation, and OTA ingestion into a
single FastAPI HTTP endpoint — the real production boundary.

Completed:

- src/api/__init__.py: package init
- src/api/webhooks.py: FastAPI APIRouter
  - POST /webhooks/{provider}
  - reads raw body BEFORE json.loads (required by signature verifier)
  - verify_webhook_signature → 403 SignatureVerificationError or unknown provider
  - validate_ota_payload → 400 if invalid (with codes list)
  - ingest_provider_event → 200 with idempotency_key
  - 500 on any unexpected exception (never surfaces internals)
  - tenant_id sourced from payload (JWT auth deferred to future phase)
- tests/test_webhook_endpoint.py: 16 contract tests (TestClient, CI-safe):
  - dev-mode skip (no secret), correct sig, wrong sig, missing header
  - invalid payload (400 + codes), non-JSON body, unknown provider
  - ingest crash → 500, tenant_id propagation, 200 body assertions
  - all 5 providers parametrized

Result:

286 tests pass (286 passed, 2 skipped).
No canonical business semantics changed.
No new Supabase tables or migrations.
No alternative write path introduced.

Also updated stale docs (not updated since Phase 51):
- docs/core/current-snapshot.md
- docs/core/work-context.md
- docs/core/live-system.md

Next phase: Phase 59 — TBD

## Phase 59 — FastAPI App Entrypoint (Closed)

Rationale:

Phase 58 delivered the webhook router but had no host app.
Phase 59 creates src/main.py — the unified production entrypoint.

Completed:

- src/main.py: FastAPI app (title="iHouse Core", version="0.1.0")
  - lifespan context manager (startup + shutdown logs)
  - GET /health → 200 {"status": "ok", "version": "0.1.0", "env": "<env>"}
  - Mounts api.webhooks.router (POST /webhooks/{provider})
  - __main__ block: uvicorn.run with IHOUSE_ENV-aware reload
  - No auth middleware yet (Phase 61), no logging middleware yet (Phase 60)
- tests/test_main_app.py: 6 contract tests
  - GET /health → 200, body fields present
  - POST /webhooks/bookingcom routes correctly through assembled app
  - Unknown route → 404 not 500
  - /health requires no auth
  - app.title == "iHouse Core"
  - app.version == "0.1.0"

Result:

292 tests pass (292 passed, 2 skipped).
No canonical business semantics changed.
No new Supabase tables or migrations.
app/main.py unchanged.

Next phase: Phase 60 — Structured request logging middleware

## Phase 60 — Structured Request Logging Middleware (Closed)

Rationale:

Before adding auth (Phase 61), operators need visibility into every request.
Logging with request_id enables correlation across distributed logs.

Completed:

- src/main.py: added @app.middleware("http") request_logging
  - UUID4 request_id per request, stored in request.state.request_id
  - → log line on entry: method + path
  - ← log line on exit: method + path + status_code + duration_ms
  - X-Request-ID response header set on every response (200/400/403/404/500)
  - Unhandled exception caught, logged with traceback, returns 500 safely
- tests/test_logging_middleware.py: 7 contract tests
  - X-Request-ID present on 200, health, 403, 400
  - UUID validity (uuid.UUID parse + version==4)
  - Different requests get different IDs
  - No interference with existing endpoints

Result:

299 tests pass (299 passed, 2 skipped).
No canonical business semantics changed.
No new Supabase tables or migrations.

Next phase: Phase 61 — JWT Auth Middleware

## Phase 61 — JWT Auth Middleware (Closed)

Rationale:

Phase 60 added request logging. Now tenant_id must come from a verified JWT,
not from the OTA payload body. This closes the authorization gap.

Completed:

- src/api/auth.py: verify_jwt() + jwt_auth Depends
  - HMAC-HS256 via PyJWT
  - sub claim = tenant_id
  - Dev mode: IHOUSE_JWT_SECRET not set → returns "dev-tenant" with warning
  - 403 on: missing creds, malformed, wrong secret, expired, missing sub, empty sub
- src/api/webhooks.py: tenant_id: str = Depends(jwt_auth) added to route
  - Manual tenant_id extraction from payload removed
- src/adapters/ota/payload_validator.py: Rule 4 (TENANT_ID_REQUIRED) removed
  - TENANT_ID_REQUIRED constant kept for backward compat but no longer enforced
- tests/test_auth.py: 8 contract tests (verify_jwt directly, CI-safe)
- tests/test_payload_validator_contract.py: updated to remove TENANT_ID_REQUIRED assertions
- tests/test_webhook_endpoint.py: test 9 updated to assert tenant_id == "dev-tenant"

Result:

307 tests pass (307 passed, 2 skipped).
No canonical business semantics changed.
No new Supabase tables or migrations.

Next phase: Phase 62 — Per-tenant Rate Limiting

## Phase 62 — Per-Tenant Rate Limiting (Closed)

Rationale:

Phase 61 added JWT auth — tenant_id is now verified.
Phase 62 adds the final protective layer: per-tenant rate limiting.

Completed:

- src/api/rate_limiter.py: InMemoryRateLimiter
  - Sliding window per tenant (keyed by tenant_id from JWT)
  - Configurable via IHOUSE_RATE_LIMIT_RPM (default 60/min/tenant)
  - Dev bypass: IHOUSE_RATE_LIMIT_RPM=0 → never raises
  - Thread-safe: threading.Lock per tenant, meta_lock for bucket map
  - 429 with Retry-After header on excess
  - Interface abstracted for future Redis swap
  - Module-level singleton (shared per process)
- src/api/webhooks.py: _: None = Depends(rate_limit) added to route
  - After jwt_auth Depends — tenant_id is available when rate limit fires
- tests/test_rate_limiter.py: 6 contract tests
  - Under limit, at limit, over limit, tenant isolation,
    window reset (1s sleep), dev bypass (rpm=0)

Result:

313 tests pass (313 passed, 2 skipped).
No canonical business semantics changed.
No new Supabase tables or migrations.

Phases 59-62 summary:
  59 — FastAPI app entrypoint (src/main.py)
  60 — Request logging middleware (X-Request-ID)
  61 — JWT auth (tenant_id from sub claim)
  62 — Per-tenant rate limiting (sliding window, 429 + Retry-After)

## Phase 63 — OpenAPI Docs (Closed)

Rationale:

External teams and tooling need a machine-readable, accurate API spec.
FastAPI auto-generates /docs and /redoc but the content was minimal.
Phase 63 enriches the spec to production quality.

Completed:

- src/schemas/__init__.py: new package
- src/schemas/responses.py: Pydantic models for all HTTP response bodies
  - HealthResponse, WebhookAcceptedResponse, ErrorResponse,
    ValidationErrorResponse, RateLimitErrorResponse
- src/main.py: full OpenAPI metadata
  - _DESCRIPTION: markdown description of system + request flow
  - contact, license_info, openapi_tags
  - BearerAuth HTTPBearer security scheme injected via custom openapi()
- src/api/webhooks.py: POST /webhooks/{provider}
  - tags, summary, response_model
  - responses: 200/400/403/429/500 with model + description
  - 429 includes Retry-After header documented
  - openapi_extra with security + x-provider-notes
  - Docstring rewritten as markdown (rendered in /docs)
- src/main.py: GET /health enriched with response_model and responses dict

Result:

313 tests pass (313 passed, 2 skipped).
No business logic changes. /docs and /redoc now production-quality.

## Phase 64 — Enhanced Health Check (Closed)

Rationale:

Phase 63 added OpenAPI docs. GET /health was minimal ("status": "ok").
Phase 64 adds real dependency checks so operators know if the system is healthy.

Completed:

- src/api/health.py: run_health_checks(version, env) → HealthResult
  - Check 1: Supabase REST ping — latency_ms measured
  - Check 2: DLQ unprocessed row count (ota_dead_letter WHERE replayed_at IS NULL)
  - status logic:
    - "ok" — all checks pass, DLQ empty
    - "degraded" — checks pass but DLQ count > 0 (still 200)
    - "unhealthy" — Supabase unreachable (503)
  - Non-raising: all errors caught, surfaced as check result
  - Uses stdlib urllib (no extra dependencies)
- src/main.py: GET /health now calls run_health_checks
  - Returns 503 if unhealthy
  - OpenAPI responses dict updated: 200 + 503
- src/schemas/responses.py: HealthResponse enriched with checks Dict[str, Any]
- tests/test_health.py: 7 contract tests (CI-safe, mocked urllib)

Result:

320 tests pass (320 passed, 2 skipped).
No canonical business semantics changed.
No new Supabase tables or migrations.

## Phase 65 — Financial Data Foundation (Closed)

- [Claude]
- New: src/adapters/ota/financial_extractor.py
  - BookingFinancialFacts (frozen=True dataclass): provider, total_price, currency, ota_commission, taxes, fees, net_to_property, source_confidence, raw_financial_fields
  - Per-provider extractors: _extract_bookingcom, _extract_expedia, _extract_airbnb, _extract_agoda, _extract_tripcom
  - Public API: extract_financial_facts(provider, payload) → BookingFinancialFacts
  - source_confidence: FULL / PARTIAL / ESTIMATED
  - All fields Optional — no exception on absent provider fields
- Modified: src/adapters/ota/schemas.py — NormalizedBookingEvent gains financial_facts: Optional[BookingFinancialFacts] = None
- Modified: all 5 adapters (bookingcom, expedia, airbnb, agoda, tripcom) — normalize() now calls extract_financial_facts()
- New: tests/test_financial_extractor_contract.py — 52 contract tests
  - Immutability (FrozenInstanceError), per-provider extraction, empty payload safety, confidence
  - Integration: adapter.normalize() → financial_facts is BookingFinancialFacts instance for all 5 providers
  - Invariant: financial_facts does not appear in canonical envelope

Invariant (locked Phase 62+): booking_state must NEVER contain financial data. Enforced: financial_facts lives on NormalizedBookingEvent only.

Result: 372 tests pass (372 passed, 2 skipped).
No canonical business semantics changed.
No Supabase tables or migrations. No booking_state writes.

## Phase 66 — booking_financial_facts Supabase Projection (Closed)

- [Claude]
- New: src/adapters/ota/financial_writer.py
  - write_financial_facts(booking_id, tenant_id, event_kind, facts, client) → None
  - Best-effort, non-blocking — exceptions logged to stderr, never raised
  - Converts Decimal fields to string for NUMERIC column compatibility
- New: scripts/migrate_phase66_financial_facts.py (migration helper)
- DB migration: booking_financial_facts table
  - Columns: id, booking_id, tenant_id, provider, total_price, currency, ota_commission, taxes, fees, net_to_property, source_confidence, raw_financial_fields (JSONB), event_kind, recorded_at
  - RLS enabled: service_role_insert + service_role_select policies
  - Indexes: ix_bff_booking_id, ix_bff_tenant_id
- Modified: src/adapters/ota/service.py — after BOOKING_CREATED APPLIED, calls write_financial_facts (best-effort, wrapped in try/except)
- New: tests/test_financial_writer_contract.py — 16 contract tests (all mocked, CI-safe)

Invariant (locked Phase 62+): booking_state must NEVER contain financial data.
booking_financial_facts is a separate append-only projection table.

E2E verified: BOOKING_CREATED payload → financial_writer → Supabase row queryable with correct fields.

Result: 388 tests pass (388 passed, 2 skipped).
No canonical business semantics changed. No booking_state writes.

## Phase 67 — Financial Facts Query API (Closed)

- [Claude]
- New: src/api/financial_router.py
  - GET /financial/{booking_id} — reads booking_financial_facts, JWT auth, tenant isolation
  - Returns most-recent row by recorded_at DESC, 404 if not found, 500 on Supabase error
  - Never reads from booking_state
- Modified: src/main.py — added 'financial' OpenAPI tag, included financial_router
- New: tests/test_financial_router_contract.py — 8 contract tests (all mocked, CI-safe)
  - T1: 200 + correct fields, T2: 404 unknown, T3: 403 no auth, T4: tenant isolation → 404
  - T5: most recent row, T6: schema completeness, T7: 500 no internals leaked, T8: tenant_id queried

Result: 396 tests pass (396 passed, 2 skipped).
No canonical business semantics changed. No booking_state writes.




## Phase 68 — booking_id Stability (Closed)

- [Claude]
- New: `src/adapters/ota/booking_identity.py`
  - `normalize_reservation_ref(provider, raw_ref) → str`
    - Base: strip + lowercase
    - bookingcom: strip BK- prefix
    - agoda: strip AGD-/AG- prefix
    - tripcom: strip TC- prefix
    - expedia, airbnb: base normalization only
    - Unknown provider: base normalization only
  - `build_booking_id(source, reservation_ref) → str`
    - Applies normalize_reservation_ref, then returns `{source}_{ref}` — locked formula unchanged
- New: `tests/test_booking_identity_contract.py` — 30 contract tests
  - Base normalization, per-provider rules, unknown provider, determinism, build_booking_id, idempotency
- Modified: all 5 adapters (bookingcom, expedia, airbnb, agoda, tripcom)
  - normalize() now calls normalize_reservation_ref() on reservation_ref before setting reservation_id
- Modified: docs/core/improvements/future-improvements.md
  - DLQ Controlled Replay → resolved (Phase 39)
  - DLQ Observability and Alerting → resolved (Phase 40-41)
  - Idempotent DLQ Replay Tracking → resolved (Phase 39)
  - booking_id Stability → resolved (Phase 68)

Result: 431 tests pass (431 passed, 2 skipped).
No Supabase schema changes. booking_id formula unchanged.

## Phase 69 — BOOKING_AMENDED Python Pipeline (Closed)

- [Claude]
- New: `src/core/skills/booking_amended/skill.py`
  - run(payload) → SkillOutput
  - Reads: booking_id (or falls back to {provider}_{reservation_id}), new_check_in, new_check_out, new_guest_count, amendment_reason
  - Emits: BOOKING_AMENDED event with only explicitly-amended fields (COALESCE-safe)
  - Invariant: never reads booking_state, never bypasses apply_envelope
- Modified: `src/core/kind_registry.core.json` — BOOKING_AMENDED → booking-amended
- Modified: `src/core/skill_exec_registry.core.json` — booking-amended → core.skills.booking_amended.skill
- Modified: `src/adapters/ota/service.py` — BOOKING_AMENDED financial facts best-effort write after APPLIED
- New: `tests/test_booking_amended_skill_contract.py` — 20 contract tests
  - Full amendment, partial (check_in only, check_out only, guest_count only, reason only)
  - booking_id fallback construction
  - Skill contract (reason, no state_upserts, exactly one emitted event)
  - None field exclusion (4 tests)
- Modified: `docs/core/improvements/future-improvements.md` — 3 items marked resolved:
  - External Event Ordering Protection (Phases 44-45)
  - External Event Signature Validation (Phase 57)
  - BOOKING_AMENDED Support (Phase 69)

Result: 451 tests pass (451 passed, 2 skipped).
No Supabase schema changes. No new migrations.
Full BOOKING_AMENDED pipeline is live end-to-end.

## Phase 77 — OTA Schema Normalization (Closed)

- [Claude]
- created `src/adapters/ota/schema_normalizer.py`: normalize_schema(provider, payload) → dict
  - adds canonical_guest_count, canonical_booking_ref, canonical_property_id to payload copy
  - raw original fields preserved; missing fields → None (no KeyError)
- updated all 5 OTA adapters: bookingcom, airbnb, expedia, agoda, tripcom — call normalize_schema() in normalize()
- 27 contract tests added (tests/test_schema_normalizer_contract.py): Groups A–E
- 4 existing adapter contract tests updated (superset check for Phase 77 compat)

Result: 572 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 78 — OTA Schema Normalization (Dates + Price) (Closed)

- [Claude]
- Extended `src/adapters/ota/schema_normalizer.py`: 4 new helpers + 4 new canonical keys
  - canonical_check_in, canonical_check_out, canonical_currency, canonical_total_price
  - Raw str values; no Decimal conversion; no adapter changes needed
- 26 contract tests added (Groups F–I in test_schema_normalizer_contract.py)

Result: 598 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 79 -- Idempotency Monitoring (Closed)

- [Claude]
- Created `src/adapters/ota/idempotency_monitor.py`
  - `IDEMPOTENCY_REJECTION_CODES` frozenset
  - `IdempotencyReport` frozen dataclass (6 fields)
  - `collect_idempotency_report()` -- reads ota_dead_letter + ota_ordering_buffer
- 35 contract tests (Groups A--F in test_idempotency_monitor_contract.py)

Result: 633 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 80 -- Structured Logging Layer (Closed)

- [Claude]
- Created `src/adapters/ota/structured_logger.py`
  - `StructuredLogger` class (debug/info/warning/error/critical)
  - `get_structured_logger(name, trace_id)` factory
  - JSON entry: {ts, level, event, trace_id?, ...kwargs}
  - Non-serializable fallback via default=str
- 30 contract tests (Groups A-G in test_structured_logger_contract.py)

Result: 663 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 81 -- Tenant Isolation Audit (Closed)

[Claude] Audited all admin/bookings/financial endpoints for tenant_id isolation.

Audit result:
- `bookings_router.py` — all queries have `.eq("tenant_id", tenant_id)` ✅
- `admin_router.py` — booking_state (active/canceled/total/last) + booking_financial_facts all filtered ✅
- `admin_router.py` — ota_dead_letter is global by design (no tenant_id column) — documented ✅
- `financial_router.py` — query correctly filtered; 404/500 responses used old format → fixed ✅

Files added:
- `src/adapters/ota/tenant_isolation_checker.py` — TenantIsolationReport (frozen dataclass), check_query_has_tenant_filter(), audit_tenant_isolation()
- `tests/test_tenant_isolation_checker_contract.py` — 24 contract tests (Groups A–D)

Files modified:
- `src/api/financial_router.py` — 404/500 now use make_error_response (Phase 75 standard)
- `tests/test_financial_router_contract.py` — T2/T7 updated: assert ["error"] → assert ["code"]

Result: 687 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 82 -- Admin Query API (Closed)

[Claude] Extended admin_router.py with 4 new operator-facing query endpoints.

Added endpoints:
- GET /admin/metrics — collect_idempotency_report() → total_dlq_rows, pending_dlq_rows, already_applied_count, idempotency_rejection_count, ordering_buffer_depth, checked_at
- GET /admin/dlq — get_pending_count(), get_replayed_count(), get_rejection_breakdown() from dlq_inspector.py
- GET /admin/health/providers — per-provider last recorded_at from event_log (bookingcom/airbnb/expedia/agoda/tripcom). status: ok|unknown
- GET /admin/bookings/{id}/timeline — all event_log events for a booking ordered by recorded_at asc

Added helper functions:
- _get_provider_health(db, tenant_id) → list — never raises, returns provider entries
- _get_booking_timeline(db, tenant_id, booking_id) → list — never raises, returns event entries

All endpoints: JWT auth required, read-only, use make_error_response for 404/500.
DLQ endpoints global by design (ota_dead_letter has no tenant_id).
Timeline and health/providers are tenant-scoped via event_log.

Files added:
- tests/test_admin_query_api_contract.py — 35 contract tests (Groups A–E)

Files modified:
- src/api/admin_router.py — 4 new endpoints, 2 new helpers, module docstring updated

Result: 722 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 83 -- Vrbo Adapter (Closed)

[Claude] Added Vrbo as the 6th OTA provider following the standard adapter pattern.

Vrbo field quirks: unit_id (not property_id), arrival_date/departure_date (shared with tripcom), guest_count (shared with airbnb), traveler_payment (total), manager_payment (net), service_fee (platform fee).
Amendment pattern: alteration.* (same top-level key as airbnb, different field names).
booking_id: vrbo_{normalized_reservation_id} (Phase 36 invariant).

Files added:
- src/adapters/ota/vrbo.py — VrboAdapter (normalize + to_canonical_envelope for all 3 event types)
- tests/test_vrbo_adapter_contract.py — 45 contract tests (Groups A-H)

Files modified:
- src/adapters/ota/schema_normalizer.py — added vrbo to all 7 canonical field helpers
- src/adapters/ota/financial_extractor.py — added _extract_vrbo (traveler_payment/manager_payment/service_fee)
- src/adapters/ota/amendment_extractor.py — added extract_amendment_vrbo, vrbo branch in dispatcher
- src/adapters/ota/booking_identity.py — added vrbo to _PROVIDER_RULES (no prefix stripping)
- src/adapters/ota/registry.py — registered VrboAdapter under "vrbo"

Result: 767 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 84 -- Reservation Timeline / Audit Trail (Closed)

[Claude] Built a unified per-booking audit trail aggregating events from 4 source tables.

reservation_timeline.py: pure read-only module, never raises.
Structures: TimelineEvent (frozen dataclass), ReservationTimeline (dataclass).
Public API: build_reservation_timeline(db, tenant_id, booking_id) -> ReservationTimeline.

Sources:
- event_log: canonical events (BOOKING_CREATED/AMENDED/CANCELED), tenant-scoped.
- booking_financial_facts: financial snapshots (FINANCIAL_RECORDED), tenant-scoped.
- ota_dead_letter: DLQ entries (DLQ_INGESTED), global (no tenant_id).
- ota_ordering_buffer: buffered events (BUFFERED), global.

Events sorted by recorded_at ascending. partial=True if any source query fails.
Each fetcher returns (events, failed_bool) and swallows all exceptions.

Files added:
- src/adapters/ota/reservation_timeline.py — TimelineEvent, ReservationTimeline, build_reservation_timeline, 4 private fetchers
- tests/test_reservation_timeline_contract.py — 45 contract tests (Groups A-H)

Result: 812 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 85 -- Google Vacation Rentals Adapter (Closed)

[Claude] Added GVR as the 7th OTA adapter. Key architectural difference documented:
GVR is a distribution surface (Google Search/Maps/Hotels), not a marketplace.
Adapter pattern is IDENTICAL to other providers — difference is in field names and extra field.

Field differences vs classic OTAs:
- gvr_booking_id (not reservation_id) for the booking reference
- property_id = standard field (shared with bookingcom/expedia)
- check_in / check_out (not arrival_date/departure_date)
- booking_value (total), google_fee (commission), net_amount (net, derived if absent)
- connected_ota: extra field forwarded in CREATE/CANCEL envelopes
- Amendment pattern: modification.{check_in, check_out, guest_count, reason}

Financial: net_amount derived = booking_value - google_fee when absent (confidence=ESTIMATED).

Files added:
- src/adapters/ota/gvr.py — GVRAdapter with full architectural doc
- tests/test_gvr_adapter_contract.py — 50 contract tests (Groups A-I)

Files modified:
- schema_normalizer.py + financial_extractor.py + amendment_extractor.py + booking_identity.py + registry.py

Result: 862 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 86 -- Conflict Detection Layer (Closed)

[Claude] Purely read-only conflict detection over booking_state (ACTIVE rows only).

Detects 4 categories:
- DATE_OVERLAP (ERROR): two ACTIVE bookings on same property, dates overlap
- MISSING_PROPERTY (ERROR): ACTIVE booking has no property_id
- MISSING_DATES (WARNING): ACTIVE booking has no check_in or check_out
- DUPLICATE_REF (ERROR): same (provider, reservation_id) appears in two bookings

Public API: detect_conflicts(db, tenant_id) -> ConflictReport.
Never raises. partial=True if DB query fails. Results sorted ERROR first.
_get_field reads top-level first, falls back to state_json (jsonb).
Date overlap uses exclusive checkout (turnaround day = no conflict).

Files added:
- src/adapters/ota/conflict_detector.py — ConflictKind, ConflictSeverity, Conflict, ConflictReport, detect_conflicts
- tests/test_conflict_detector_contract.py — 58 contract tests (Groups A-I)

Result: 920 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 87 -- Tenant Isolation Hardening (Closed)

[Claude] System-level isolation policy layer — extends Phase 81.

TABLE_REGISTRY canonical classification (5 tables):
- TENANT_SCOPED (requires_filter=True): event_log, booking_state, booking_financial_facts
- GLOBAL (requires_filter=False): ota_dead_letter, ota_ordering_buffer
  Global rationale: no tenant_id column — isolation via booking_id routing.

New functions:
- get_table_policy(table_name) → TableIsolationPolicy | None
- check_cross_tenant_leak(tenant_a, tenant_b, rows) → CrossTenantLeakResult
- audit_system_isolation() → SystemIsolationReport (all_compliant=True confirmed)

Integration tests verify Phase 81 + Phase 87 agreement at both query-level and table-level.

Files added:
- src/adapters/ota/tenant_isolation_enforcer.py
- tests/test_tenant_isolation_enforcer_contract.py — 54 contract tests (Groups A-I)

Result: 974 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 88 -- Traveloka Adapter (Closed)

[Claude] Traveloka — SE Asia Tier 1.5 OTA (dominant platform in Indonesia, Thailand, Vietnam).

Field mapping: booking_code (TV- prefix stripped) → reservation_id, property_code → property_id,
check_in_date/check_out_date → canonical dates, num_guests → guest count,
booking_total → total_price, currency_code (not 'currency') → currency, traveloka_fee → commission.

Financial: FULL if booking_total + currency_code + net_payout; ESTIMATED if net derived from booking_total - traveloka_fee.
Amendment block: modification.{check_in_date, check_out_date, num_guests, modification_reason}.
Prefix stripping: _strip_traveloka_prefix strips TV- / tv-.

Files changed:
- src/adapters/ota/traveloka.py (NEW)
- src/adapters/ota/schema_normalizer.py (+8 traveloka, currency_code special case)
- src/adapters/ota/financial_extractor.py (_extract_traveloka + ESTIMATED net derivation)
- src/adapters/ota/amendment_extractor.py (extract_amendment_traveloka + dispatcher)
- src/adapters/ota/booking_identity.py (_strip_traveloka_prefix + registry entry)
- src/adapters/ota/registry.py (TravelokaAdapter registered)
- tests/test_traveloka_adapter_contract.py (53 contract tests Groups A-I)

Result: 1029 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 89 -- OTA Reconciliation Discovery (Closed)

[Claude] Discovery-only phase. Defined the canonical reconciliation data model.

New: src/adapters/ota/reconciliation_model.py
  - ReconciliationFindingKind (StrEnum, 7 values): BOOKING_MISSING_INTERNALLY,
    BOOKING_STATUS_MISMATCH, DATE_MISMATCH, FINANCIAL_FACTS_MISSING,
    FINANCIAL_AMOUNT_DRIFT, PROVIDER_DRIFT, STALE_BOOKING
  - ReconciliationSeverity (StrEnum, 3 values): CRITICAL, WARNING, INFO
  - FINDING_SEVERITY: canonical kind → severity mapping (locked)
  - CORRECTION_HINTS: canonical kind → human-readable guidance (locked)
  - _make_finding_id(kind, booking_id) → 12-char hex (sha256[:12], deterministic)
  - ReconciliationFinding (frozen dataclass): .build() factory — auto-assigns
    finding_id, severity, correction_hint from canonical maps
  - ReconciliationReport (dataclass): .build() auto-derives critical/warning/info
    counts from findings list; has_critical(), has_warnings(), is_clean() helpers
  - ReconciliationSummary (frozen dataclass): .from_report() — compact view,
    top_kind tie-breaking: most-frequent → CRITICAL first → alphabetical

New: tests/test_reconciliation_model_contract.py — 87 contract tests (Groups A-I)
  Group A: FindingKind enum (10 tests)
  Group B: Severity enum (5 tests)
  Group C: FINDING_SEVERITY mapping (9 tests)
  Group D: CORRECTION_HINTS mapping (7 tests)
  Group E: ReconciliationFinding.build() factory (13 tests + parametric)
  Group F: finding_id determinism (6 tests)
  Group G: ReconciliationReport.build() (11 tests)
  Group H: Report helper methods (8 tests)
  Group I: ReconciliationSummary.from_report() (12 tests)

New invariant: The reconciliation layer is READ-ONLY. It never writes to
booking_state or any Supabase table. Corrections require a new canonical event.

Result: 1116 passed, 2 skipped.
No Supabase schema changes. No new migrations. No booking_state writes.

## Phase 90 -- External Integration Test Harness (Closed)

[Claude] End-to-end deterministic pipeline harness for all 8 OTA providers.
No production code changes. Infrastructure-only. CI-safe.

New: tests/test_e2e_integration_harness.py — 276 tests (Groups A-H)

Group A: All 8 providers × 8 assertions → BOOKING_CREATED
Group B: All 8 providers × 4 assertions → BOOKING_CANCELED
Group C: All 8 providers × 6 assertions → BOOKING_AMENDED
Group D: booking_id Phase 36 invariant + prefix stripping
Group E: idempotency_key non-empty, deterministic, event-differentiated
Group F: Invalid payload boundary rejection
Group G: Cross-provider isolation (same raw ref → different booking_id)
Group H: Pipeline idempotency (same payload → same envelope)

Key engineering notes:
  - payload_validator accepts reservation_id/booking_ref/order_id only.
    gvr_booking_id and booking_code require reservation_id duplication.
  - Traveloka event_types must match semantics.py known values (not BOOKING_CONFIRMED etc.)

Result: 1392 passed, 2 skipped.
No Supabase schema changes. No new migrations. No booking_state writes.

## Phase 91 -- OTA Replay Fixture Contract (Closed)

[Claude] YAML fixture-driven replay harness for all 8 OTA providers.
No production code changes. Test infrastructure only. CI-safe.

New files:
  tests/fixtures/ota_replay/bookingcom.yaml (2 docs)
  tests/fixtures/ota_replay/expedia.yaml   (2 docs)
  tests/fixtures/ota_replay/airbnb.yaml    (2 docs)
  tests/fixtures/ota_replay/agoda.yaml     (2 docs)
  tests/fixtures/ota_replay/tripcom.yaml   (2 docs)
  tests/fixtures/ota_replay/vrbo.yaml      (2 docs)
  tests/fixtures/ota_replay/gvr.yaml       (2 docs)
  tests/fixtures/ota_replay/traveloka.yaml (2 docs)
  tests/test_ota_replay_fixture_contract.py — 273 tests (Groups A-E)

Key eng note: pyyaml (test dependency) installed to .venv.
GVR + Traveloka need reservation_id duplicated (payload_validator requirement).
Traveloka uses event_reference (not event_id) as the idempotency source field.

Result: 1665 passed, 2 skipped.
No Supabase schema changes. No new migrations. No booking_state writes.

---

## Phase 97 closure — 2026-03-09

Klook Replay Fixture Contract.

Added YAML replay fixtures for Klook to the OTA replay harness. Expanded EXPECTED_PROVIDERS from 9→10, fixture count invariant 18→20.

New files:
  tests/fixtures/ota_replay/klook.yaml (2 docs)
    klook_create: BOOKING_CONFIRMED / KL-ACTBK-REPLAY-001 / SGD / participants=3
    klook_cancel: BOOKING_CANCELLED / same ref

Modified:
  tests/test_ota_replay_fixture_contract.py
    — EXPECTED_PROVIDERS: added "klook"
    — test_e4: 18→20 fixture count invariant
    — docstring header: 9→10 providers
    — D1 comment: klook uses event_id (standard)

Result: 341 replay tests pass. 1977 total tests pass, 2 skipped.
No production code changes. No Supabase migrations.

---

## Phase 98 closure — 2026-03-09

Despegar Adapter (Tier 2 — Latin America).

Integrated Despegar — dominant OTA in LATAM (Argentina, Brazil, Mexico, Chile, Colombia, Peru). Fields: reservation_code (DSP- stripped), hotel_id, passenger_count, check_in/check_out, total_fare, despegar_fee, net_amount. Multi-currency: ARS, BRL, MXN, CLP, COP, PEN, USD.

Also patched payload_validator.py: Rule 3 now accepts reservation_code and booking_code in addition to reservation_id/booking_ref/order_id. This was a latent gap that would have blocked any DSP-style provider.

New files:
  src/adapters/ota/despegar.py — DespegarAdapter
  tests/test_despegar_adapter_contract.py — 61 tests (Groups A-H)

Modified:
  src/adapters/ota/registry.py          — DespegarAdapter registered
  src/adapters/ota/booking_identity.py  — _strip_despegar_prefix (DSP-→ stripped)
  src/adapters/ota/schema_normalizer.py — 6 helpers
  src/adapters/ota/amendment_extractor.py — extract_amendment_despegar
  src/adapters/ota/financial_extractor.py — _extract_despegar (FULL/ESTIMATED/PARTIAL)
  src/adapters/ota/payload_validator.py — Rule 3 extended
  docs/core/current-snapshot.md
  docs/core/work-context.md

OTA adapters: 11 total (8 Tier 1 + MMT + Klook + Despegar).
Result: 2038 tests pass, 2 skipped.
No Supabase schema changes. No new migrations. No booking_state writes.

---

### Phase 99 closure — 2026-03-09

Despegar Replay Fixture Contract.

New files:
  tests/fixtures/ota_replay/despegar.yaml — 2 fixtures (despegar_create ARS + despegar_cancel)

Modified:
  tests/test_ota_replay_fixture_contract.py — EXPECTED_PROVIDERS 10→11, test_e4 count 20→22, D1 docstring updated

Replay harness now covers 11 providers × 2 = 22 fixtures (375 replay tests).
Result: 2074 tests pass, 2 skipped.
No adapter code changes. No Supabase changes. No migrations.

---

### Phase 100 closure — 2026-03-09

Owner Statement Foundation.

New files:
  src/adapters/ota/owner_statement.py — StatementConfidenceLevel, OwnerStatementEntry, OwnerStatementSummary, build_owner_statement()
  tests/test_owner_statement_contract.py — 60 tests, Groups A-G

Aggregation rules locked:
  - Canceled bookings excluded from financial totals (gross/net/commission), included in entries
  - Multi-currency guard: currency="MIXED", totals=None when >1 currency
  - Confidence breakdown counts all entries (including canceled)
  - StatementConfidenceLevel: PARTIAL→INCOMPLETE > all FULL→VERIFIED > otherwise MIXED

Result: 2134 tests pass, 2 skipped.
No adapter changes. No Supabase changes. No migrations.

---

### Phase 101 closure — 2026-03-09

Owner Statement Query API.

New files:
  src/api/owner_statement_router.py — GET /owner-statement/{property_id}?month=YYYY-MM
  tests/test_owner_statement_router_contract.py — 28 tests, Groups A-E

Modified:
  src/api/error_models.py — PROPERTY_NOT_FOUND + INVALID_MONTH codes added
  src/main.py — owner_statement_router registered + tag added

Result: 2162 tests pass, 2 skipped.
No DB schema changes. No migrations. No booking_state writes.

---

### Phase 102 closure — 2026-03-09

E2E Integration Harness Extension (8 → 11 providers).

Modified files:
  tests/test_e2e_integration_harness.py — 3 new provider factory sets (MMT/Klook/Despegar), PROVIDERS extended to 11
  src/adapters/ota/payload_validator.py — booking_id added as valid identity field for MakeMyTrip

E2E harness: 375 tests, all 11 providers × Groups A-H.
Result: 2261 tests pass, 2 skipped.

---

### Phase 103 closure — 2026-03-09

Payment Lifecycle Query API.

New files:
  src/api/payment_status_router.py — GET /payment-status/{booking_id}
  tests/test_payment_status_router_contract.py — 24 tests, Groups A-E

Modified:
  src/main.py — payment_status_router registered + tag added

Result: 2285 tests pass, 2 skipped.
No DB schema changes. No migrations. No booking_state reads.

---

### Phase 104 closure — 2026-03-09

Amendment History Query API.

New files:
  src/api/amendments_router.py — GET /amendments/{booking_id}
  tests/test_amendments_router_contract.py — 20 tests, Groups A-F

Modified:
  src/main.py — amendments_router registered + tag added

Data source: booking_financial_facts WHERE event_kind='BOOKING_AMENDED', ORDER BY recorded_at ASC.
Result: 2305 tests pass, 2 skipped.
No DB schema changes. No migrations. No booking_state reads.

---

### Phase 105 closure — 2026-03-09

Admin Router Phase 82 Contract Tests.

New files:
  tests/test_admin_router_phase82_contract.py — 41 tests, Groups A-E

Endpoints covered for the first time:
  GET /admin/metrics  (idempotency report — idempotency_monitor.py)
  GET /admin/dlq      (DLQ inspector — dlq_inspector.py)
  GET /admin/health/providers (per-provider last ingest)
  GET /admin/bookings/{id}/timeline (event_log per booking)

Result: 2346 tests pass, 2 skipped. Zero source code changes.

---

### Phase 106 closure — 2026-03-09

Booking List Query API.

Modified:
  src/api/bookings_router.py — GET /bookings added after GET /bookings/{booking_id}
  Query params: property_id (optional), status (active|canceled, 400 on invalid), limit (1-100, default 50)

New files:
  tests/test_booking_list_router_contract.py — 28 tests, Groups A-G

Result: 2374 tests pass, 2 skipped.
No DB schema changes. No migrations. booking_state read-only.

### Phase 107 closure — 2026-03-09

Roadmap Refresh.

Modified:
  docs/core/roadmap.md — completed-phases table extended Phase 93–106; forward plan Phase 107–126 written; "where we land" updated to Phase 126

New files:
  docs/archive/phases/phase-107-spec.md — phase spec

Result: 2374 tests pass, 2 skipped.
Documentation-only phase. Zero production source changes.

### Phase 108 closure — 2026-03-09

Financial List Query API.

Modified:
  src/api/financial_router.py — GET /financial list endpoint added; docstring updated to Phase 108; month YYYY-MM regex validation; provider + month + limit filters; December boundary arithmetic

New files:
  tests/test_financial_list_router_contract.py — 27 tests, 1 intentional skip, Groups A–G
  docs/archive/phases/phase-108-spec.md — phase spec

Result: 2401 tests pass, 2 pre-existing SQLite skips, 1 intentional skip.
No DB schema changes. No migrations. booking_financial_facts read-only.

### Phase 109 closure — 2026-03-09

Booking Date Range Search.

Modified:
  src/api/bookings_router.py — GET /bookings extended: check_in_from + check_in_to (YYYY-MM-DD), ISO 8601 regex validation, gte/lte on check_in column; 400 VALIDATION_ERROR on bad format

New files:
  tests/test_booking_date_range_contract.py — 36 tests, Groups A–G
  docs/archive/phases/phase-109-spec.md — phase spec

Result: 2437 tests pass, 2 pre-existing SQLite skips.
No DB schema changes. booking_state read-only.

### Phase 110 closure — 2026-03-09

OTA Reconciliation Implementation.

New files:
  src/reconciliation/__init__.py — package marker
  src/reconciliation/reconciliation_detector.py — run_reconciliation(), FINANCIAL_FACTS_MISSING + STALE_BOOKING detectors (pure read-only)
  tests/test_reconciliation_detector_contract.py — 27 tests, Groups A–J
  docs/archive/phases/phase-110-spec.md — phase spec

Modified:
  src/api/admin_router.py — GET /admin/reconciliation endpoint added (include_findings param)

Result: 2464 tests pass, 2 pre-existing SQLite skips.
No DB schema changes.

### Phase 111 closure — 2026-03-09

Task System Foundation.

New files:
  src/tasks/__init__.py — package marker
  src/tasks/task_model.py — TaskKind(5), TaskStatus(5), TaskPriority(4), WorkerRole(5) enums; PRIORITY_URGENCY, PRIORITY_ACK_SLA_MINUTES, KIND_DEFAULT_WORKER_ROLE, KIND_DEFAULT_PRIORITY mapping tables; VALID_TASK_TRANSITIONS, TERMINAL_STATUSES; Task dataclass with .build() factory, .with_status(), .can_transition_to(), .is_terminal()
  tests/test_task_model_contract.py — 68 tests, Groups A–I
  docs/archive/phases/phase-111-spec.md — phase spec

Invariant locked: CRITICAL ACK SLA = 5 minutes.
Invariant locked: task_id is deterministic (hash-based).

Result: 2532 tests pass, 2 pre-existing SQLite skips.
No DB schema changes. Pure data model — no DB I/O.

### Phase 112 closure — 2026-03-09

Task Automation from Booking Events.

New files:
  src/tasks/task_automator.py — tasks_for_booking_created() [CHECKIN_PREP+CLEANING], actions_for_booking_canceled() [TaskCancelAction], actions_for_booking_amended() [TaskRescheduleAction]; TaskCancelAction + TaskRescheduleAction frozen dataclasses
  tests/test_task_automator_contract.py — 48 tests, Groups A–J
  docs/archive/phases/phase-112-spec.md — phase spec

Automation rules locked:
  BOOKING_CREATED → CHECKIN_PREP (HIGH) + CLEANING (MEDIUM), both due on check_in
  BOOKING_CANCELED → TaskCancelAction for all PENDING tasks
  BOOKING_AMENDED → TaskRescheduleAction for CHECKIN_PREP + CLEANING if check_in changed

Result: 2580 tests pass, 2 pre-existing SQLite skips.
No DB schema changes. Pure functions — callers persist actions.

### Phase 113 closure — 2026-03-09

Task Query API.

New files:
  src/tasks/task_router.py — GET /tasks (filters: property_id, status, kind, due_date, limit 1-100), GET /tasks/{task_id} (404 tenant-isolated), PATCH /tasks/{task_id}/status (VALID_TASK_TRANSITIONS enforced, 422 INVALID_TRANSITION, canceled_reason defaults to "Canceled via API")
  tests/test_task_router_contract.py — 50 tests, Groups A–P
  docs/archive/phases/phase-113-spec.md — phase spec

Modified:
  src/api/error_models.py — ErrorCode.NOT_FOUND + ErrorCode.INVALID_TRANSITION added
  src/main.py — task_router registered

Result: 2630 tests pass, 2 pre-existing SQLite skips.
PATCH /tasks/{id}/status writes only to `tasks` table. Never touches booking_state, event_log, or booking_financial_facts.




## Phase 114 — Task Persistence Layer: Supabase `tasks` Table DDL (Closed)

New files:
  supabase/migrations/20260309180000_phase114_tasks_table.sql — CREATE TABLE tasks (18 columns), 3 RLS policies, 3 composite indexes
  docs/archive/phases/phase-114-spec.md — phase spec

Table columns: task_id (TEXT PK, deterministic sha256[:16]), tenant_id, kind, status, priority, urgency, worker_role, ack_sla_minutes, booking_id, property_id, due_date, title, description, created_at (TIMESTAMPTZ DEFAULT now()), updated_at (TIMESTAMPTZ DEFAULT now()), notes (JSONB DEFAULT '[]'), canceled_reason

RLS:
  tasks_service_role_all — service role full bypass
  tasks_tenant_read — authenticated SELECT, JWT sub claim isolation
  tasks_tenant_update — authenticated UPDATE, JWT sub claim isolation

Indexes: ix_tasks_tenant_status, ix_tasks_tenant_property, ix_tasks_tenant_due_date

Result: Migration applied via `supabase db push`. E2E verified: INSERT/SELECT/UPDATE/DELETE all confirmed on live Supabase.
2630 tests still passing — no Python source changes, infra-only phase.
Invariant: PATCH /tasks/{id}/status writes ONLY to `tasks`. Never touches booking_state, event_log, or booking_financial_facts.

### Phase 121 closure — 2026-03-09

Owner Statement Generator (Ring 4).

Modified:
  src/api/owner_statement_router.py — complete Ring 4 rewrite:
    - Property_id filter applied at DB level (eq("property_id")) instead of client-side ilike
    - Per-booking line items with: check_in, check_out, gross, ota_commission, net_to_property,
      epistemic_tier (A/B/C), lifecycle_status, event_kind, source_confidence, recorded_at
    - management_fee_pct query param (0.0–100.0) — deducted from aggregated net_to_property
      to produce owner_net_total; management_fee_amount shown separately
    - OTA_COLLECTING bookings: appear in line_items for auditability but net EXCLUDED from
      owner_net_total (Phase 120 honesty invariant)
    - Multi-currency guard: MIXED currency → all monetary totals None
    - Dedup: most-recent recorded_at per booking_id (_dedup_latest from Ring 1)
    - PDF export: ?format=pdf → text/plain response with Content-Disposition: attachment
    - Overall epistemic_tier in summary (worst of all line item tiers)
    - Imports _tier, _worst_tier, _project_lifecycle_status from financial_dashboard_router
    - Imports _dedup_latest, _fmt, _month_bounds, _to_decimal, _canonical_currency from
      financial_aggregation_router

  tests/test_owner_statement_router_contract.py — updated Phase 101 tests for Phase 121 shape:
    - Mock chain updated (gte/lt instead of ilike)
    - Assertions updated to new response shape (summary.* fields)

New files:
  tests/test_owner_statement_phase121_contract.py — 49 tests, Groups A–I
  docs/archive/phases/phase-121-spec.md — phase spec

New invariants locked (Phase 121):
  Management fee applied AFTER OTA commission on aggregated net_to_property.
  OTA_COLLECTING net NEVER included in owner_net_total.
  PDF export: text/plain only — no external PDF library dependency.

Result: 2909 tests pass, 2 pre-existing SQLite skips.
No DB schema changes. All reads from booking_financial_facts only.

## Phase 122 — OTA Financial Health Comparison (Closed)

GET /financial/ota-comparison: per-OTA revenue, commission, NET confidence breakdown.
New: src/api/ota_comparison_router.py, tests/test_ota_comparison_router_contract.py
Result: tests passing. No DB schema changes.

## Phase 123 — Worker-Facing Task Surface (Closed)

GET /worker/tasks (worker_role/status/date/limit filters), PATCH /worker/tasks/{id}/acknowledge (PENDING→ACKNOWLEDGED), PATCH /worker/tasks/{id}/complete (IN_PROGRESS→COMPLETED). VALID_TASK_TRANSITIONS enforced. Notes appended on complete.
New: src/api/worker_router.py, tests/test_worker_router_contract.py (41 tests)
No DB schema changes.

## Phase 124 — LINE Escalation Channel (Closed)

LINE messaging integration for SLA breach escalation. POST /line/webhook for LINE ack (PENDING→ACKNOWLEDGED). HMAC-SHA256 sig validation (dev=skip).
New: src/channels/line_escalation.py, src/api/line_webhook_router.py
Tests: test_line_escalation_contract.py + test_line_webhook_router_contract.py (57 tests)
No DB schema changes.

## Phase 125 — Hotelbeds Adapter Tier 3 B2B Bedbank (Closed)

Hotelbeds B2B bedbank adapter: net_rate (property receives directly), markup_amount (Hotelbeds margin), HB- prefix strip on voucher_ref. Financial extractor FULL/ESTIMATED/PARTIAL confidence. Amendment extractor.
New: src/adapters/ota/hotelbeds.py, tests/test_hotelbeds_adapter_contract.py (42 tests)
Registry registered.

## Phase 126 — Availability Projection (Closed)

GET /availability/{property_id}?from=&to= — per-date occupancy from booking_state. CONFLICT detection for dates with >1 ACTIVE booking. check_out exclusive. Zero write-path changes. JWT required.
New: src/api/availability_router.py, tests/test_availability_router_contract.py.

## Phase 127 — Integration Health Dashboard (Closed)

GET /integration-health: all 13 OTA providers — last_ingest_at, lag_seconds (recorded_at - occurred_at), buffer_count (ota_ordering_buffer), dlq_count (ota_dead_letter), stale_alert (24h threshold). summary block (ok/stale/unknown/total_dlq/total_buffer/has_alerts). JWT required. Best-effort per provider (error → "unknown" status).
New: src/api/integration_health_router.py, tests/test_integration_health_router_contract.py (37 tests)
Result: 3166 tests pass.

## Phase 128 — Conflict Center (Closed)

GET /conflicts?property_id= — cross-property tenant-scoped ACTIVE booking overlap detection. itertools.combinations per property. CRITICAL(≥3 nights)/WARNING(1-2). Pair deduplication (booking_a < booking_b lexicographically). Summary: total_conflicts/properties_affected/bookings_involved. JWT required. check_out exclusive.
New: src/api/conflicts_router.py, tests/test_conflicts_router_contract.py (39 tests)
Result: 3205 tests pass. No DB schema changes.

## Phase 129 — Booking Search Enhancement (Closed)

GET /bookings enhanced: source(OTA provider filter .eq("source")), check_out_from/check_out_to date range, sort_by(check_in|check_out|updated_at|created_at, default updated_at), sort_dir(asc|desc, default desc). Response echoes sort_by/sort_dir. Backward compatible (all existing callers unaffected). Validation: sort_by/sort_dir 400 on invalid. Date validation loop consolidated.
Modified: src/api/bookings_router.py
New: tests/test_booking_search_contract.py (31 tests)
Result: 3236 tests pass. No DB changes.

## Phase 130 — Properties Summary Dashboard (Closed)

GET /properties/summary?limit= — per-property portfolio view. Per-property: active_count, canceled_count, next_check_in (earliest upcoming ≥ today), next_check_out (earliest > today), has_conflict (itertools.combinations pattern from Phase 128). Portfolio: total_active_bookings, total_canceled_bookings, properties_with_conflicts. Sorted alphabetically by property_id. limit 1–200 (default 100). JWT required.
New: src/api/properties_summary_router.py, tests/test_properties_summary_router_contract.py (37 tests)
Result: 3273 tests pass. No DB changes.

## Phase 131 — DLQ Inspector (Closed)

GET /admin/dlq?source=&status=&limit= — list ota_dead_letter entries with filters. Status derived in Python from replay_result: null→pending, APPLIED/ALREADY_APPLIED/ALREADY_EXISTS/ALREADY_EXISTS_BUSINESS→applied, other→error. payload_preview: first 200 chars. GET /admin/dlq/{envelope_id} — single entry with full raw_payload. JWT required. Global read (not tenant-scoped). Zero write-path changes.
New: src/api/dlq_router.py, tests/test_dlq_router_contract.py (44 tests)
Result: 3317 tests pass. No DB schema changes. 2 pre-existing SQLite guard failures (unrelated).

## Phase 139 — Real Outbound Adapters (Closed)

Replaced Phase 138 dry-run stub adapters with provider-specific implementations wired into outbound_executor.py via a new adapter registry.

Tier A — api_first adapters:
- AirbnbAdapter: POST /v2/calendar_operations, AIRBNB_API_KEY + AIRBNB_API_BASE
- BookingComAdapter: POST /v1/hotels/availability-blocks, BOOKINGCOM_API_KEY + BOOKINGCOM_API_BASE
- ExpediaVrboAdapter: POST /v1/properties/{id}/availability, shared EXPEDIA_API_KEY (Expedia + VRBO)

Tier B — ical_fallback adapters (ICalPushAdapter):
- hotelbeds: PUT {HOTELBEDS_ICAL_URL}/{external_id}.ics
- tripadvisor: PUT {TRIPADVISOR_ICAL_URL}/{external_id}.ics
- despegar: PUT {DESPEGAR_ICAL_URL}/{external_id}.ics

Dry-run contract (all adapters): absent credentials → dry_run; IHOUSE_DRY_RUN=true → dry_run; 2xx → ok; non-2xx → failed; network exc → failed (no re-raise).

Registry: build_adapter_registry() → {provider: adapter} map for 7 providers.

New: src/adapters/outbound/__init__.py, airbnb_adapter.py, bookingcom_adapter.py, expedia_vrbo_adapter.py, ical_push_adapter.py, registry.py
New: tests/test_outbound_adapters_contract.py (40 tests)
Modified: src/services/outbound_executor.py (real registry dispatch; Phase 138 stubs kept as fallback)
Commit: fb6de78
Result: 3573 tests pass. No DB schema changes. 2 pre-existing SQLite guard failures (unrelated).


## Phase 140 — iCal Date Injection (Closed)

Injected real check_in / check_out from booking_state into iCal VCALENDAR DTSTART/DTEND.
Phase 139 shipped placeholder dates (20260101/20260102). Phase 140 replaces them with booking-specific real dates.

Changes:
- booking_dates.py [NEW]: fetch_booking_dates() — read-only SELECT on booking_state; returns (check_in, check_out) as YYYYMMDD; fail-safe (returns None on missing row or error)
- ical_push_adapter.py: push() gains check_in/check_out kwargs; _ICAL_TEMPLATE uses {dtstart}/{dtend}; PRODID → Phase 140; _FALLBACK_DTSTART/_FALLBACK_DTEND constants (20260101/20260102) for backward compat
- outbound_executor.py: execute_sync_plan() gains check_in/check_out; forwarded to adapter.push() in ical_fallback registry branch
- outbound_executor_router.py: booking_state SELECT expanded to include check_in/check_out; _to_ical() converts ISO→YYYYMMDD; dates passed to execute_sync_plan()
- tests/test_ical_date_injection_contract.py [NEW]: 16 contract tests (Groups A-F)
Commit: 45fa03f
Result: 3589 tests pass. No DB schema changes. 2 pre-existing SQLite guard failures (unrelated).

## Phase 141 — Rate-Limit Enforcement (Closed)

Enforces `rate_limit` (calls/minute) from SyncAction in all 4 outbound adapters.
The `rate_limit` param was already on every `send()`/`push()` signature but silently ignored.
Phase 141 adds the throttle helper and wires it into the real HTTP path.

Changes:
- src/adapters/outbound/__init__.py: added `_throttle(rate_limit)` — `time.sleep(60.0 / rate_limit)`; `IHOUSE_THROTTLE_DISABLED=true` env opt-out; `rate_limit <= 0` logs WARNING + returns (best-effort); never raises
- src/adapters/outbound/airbnb_adapter.py: imports `_throttle`; called immediately before `httpx.post()` on real path
- src/adapters/outbound/bookingcom_adapter.py: same
- src/adapters/outbound/expedia_vrbo_adapter.py: same
- src/adapters/outbound/ical_push_adapter.py: `_throttle` called before `httpx.put()` on real path
- tests/test_rate_limit_enforcement_contract.py [NEW]: 22 contract tests across Groups A–E: arithmetic (60rpm→1s, 120rpm→0.5s), zero/negative rate_limit, IHOUSE_THROTTLE_DISABLED, dry-run bypass for all 4 adapters

Result: 3609 tests pass (3589 + 22 new). No DB schema changes. 2 pre-existing SQLite guard failures (unrelated, unchanged).

## Phase 142 — Retry + Exponential Backoff (Closed)

On 5xx or network error, adapters now retry the HTTP call up to 3 times with exponential backoff.
Before Phase 142, any transient 5xx immediately returned `failed` — requiring manual replay.

Changes:
- src/adapters/outbound/__init__.py: added `_retry_with_backoff(fn, max_retries=3)` — backoff: `4^(attempt-1)` s capped at 30s (1s→4s→16s); retries on 5xx (http_status>=500) and exceptions; no retry on 4xx or http_status=None; `IHOUSE_RETRY_DISABLED=true` opt-out
- src/adapters/outbound/airbnb_adapter.py: HTTP call moved to `_do_req()` closure; `_retry_with_backoff(_do_req)` called after `_throttle(rate_limit)`
- src/adapters/outbound/bookingcom_adapter.py: same
- src/adapters/outbound/expedia_vrbo_adapter.py: same
- src/adapters/outbound/ical_push_adapter.py: same (httpx.put path)
- tests/test_adapter_retry_contract.py [NEW]: 28 contract tests across Groups A–E: `_retry_with_backoff()` unit (10 tests), per-adapter wiring (18 tests)

Result: 3637 tests pass (3609 + 28 new). No DB schema changes. No migration. No router changes. 2 pre-existing SQLite guard failures (unrelated, unchanged).


## Phase 143 — Idempotency Key on Outbound Requests (Closed)

Attaches `X-Idempotency-Key: {booking_id}:{external_id}:{YYYYMMDD}` to every outbound
HTTP call, allowing OTAs to deduplicate repeated sync requests.

Changes:
- src/adapters/outbound/__init__.py: added `_build_idempotency_key(booking_id, external_id)` returning `{booking_id}:{external_id}:{YYYYMMDD}`; day-stable (UTC); empty inputs log WARNING + return best-effort key; `from datetime import date as _date`
- src/adapters/outbound/airbnb_adapter.py: `X-Idempotency-Key` added to headers in `_do_req()` closure
- src/adapters/outbound/bookingcom_adapter.py: same
- src/adapters/outbound/expedia_vrbo_adapter.py: same
- src/adapters/outbound/ical_push_adapter.py: `X-Idempotency-Key` added alongside `Content-Type`; `Authorization` remains optional
- tests/test_outbound_idempotency_key_contract.py [NEW]: 23 contract tests Groups A–E: key format/stability/rollover (9 unit tests), per-adapter header presence + format + retry-stability + dry-run (14 tests)

Result: 3660 tests pass (3637 + 23 new). No DB schema changes. No migrations. No router changes. 2 pre-existing SQLite guard failures (unrelated, unchanged).


## Phase 144 — Outbound Sync Result Persistence (Closed)

Append-only audit log of every ExecutionResult in `outbound_sync_log` table.

Changes:
- migrations/phase_144_outbound_sync_log.sql [NEW]: DDL — BIGSERIAL id, booking_id/tenant_id/provider/external_id/strategy TEXT, status TEXT CHECK(ok/failed/dry_run/skipped), http_status INT, message TEXT, synced_at TIMESTAMPTZ DEFAULT now(); 3 indexes; RLS; table comment
- src/services/sync_log_writer.py [NEW]: `write_sync_result(**kwargs, client=None)` — best-effort INSERT into outbound_sync_log; lazy SyncPostgrestClient via `_get_supabase_client()`; `client` param for tests; `IHOUSE_SYNC_LOG_DISABLED=true` opt-out; message truncated at 2000 chars; returns True/False; never raises
- src/services/outbound_executor.py [MODIFIED]: `_SYNC_LOG_AVAILABLE` try-import guard; `_persist(booking_id, tenant_id, result)` helper with try/except swallow; called after each `results.append(result)` including exception path; skipped actions NOT persisted (use `continue`)
- tests/test_sync_result_persistence_contract.py [NEW]: 13 contract tests Groups A-E

⚠️ DDL PENDING APPLY: `migrations/phase_144_outbound_sync_log.sql` must be applied to Supabase when MCP access is restored.

Result: 3673 tests pass (3660 + 13 new). 2 pre-existing SQLite failures (unrelated, unchanged).


## Phase 145 — Outbound Sync Log Inspector (Closed)

Read-only API to inspect `outbound_sync_log` rows written by Phase 144.

Changes:
- src/api/outbound_log_router.py [NEW]: `GET /admin/outbound-log` (filters: booking_id/provider/status/limit 1-200); `GET /admin/outbound-log/{booking_id}` (404 if no rows); tenant-scoped; optional client injection; `_query_log()` helper; VALIDATION_ERROR on invalid status; newest-first ordering
- src/main.py [MODIFIED]: Added "outbound" tag to _TAGS; registered outbound_log_router after outbound_executor_router
- tests/test_outbound_log_router_contract.py [NEW]: 30 contract tests Groups A-J

Result: 3703 tests pass (3673 + 30 new). No DB schema changes. 2 pre-existing SQLite failures (unrelated, unchanged).


## Phase 146 — Sync Health Dashboard (Closed)

Per-provider outbound sync reliability metrics. No new schema.

Changes:
- src/api/outbound_log_router.py [MODIFIED]: `_compute_health(db, tenant_id)` — in-memory aggregation of newest 2000 rows; per-provider ok/failed/dry_run/skipped + last_sync_at + failure_rate_7d (None if no ok+failed in window); malformed timestamps skipped; returns [] on DB error; alphabetical sort. `GET /admin/outbound-health` endpoint: tenant-scoped; `{tenant_id, provider_count, checked_at, providers[]}`.
- tests/test_outbound_health_contract.py [NEW]: 33 contract tests Groups A-N

Result: 3736 tests pass (3703 + 33 new). No DB schema changes. No main.py change. 2 pre-existing SQLite failures (unrelated, unchanged).


## Phase 147 — Failed Sync Replay (Closed)

Replay a failed outbound sync for a specific booking+provider, reusing all Phase 141-144 guarantees.

Changes:
- src/services/outbound_executor.py [MODIFIED]: `execute_single_provider()` — builds SyncAction from args, delegates to execute_sync_plan() (full path: throttle + retry + idempotency + persistence). tier=None on replay.
- src/api/outbound_log_router.py [MODIFIED]: `_fetch_last_log_row()` — tenant-isolated log row lookup. `POST /admin/outbound-replay` — 400 on missing fields, 404 on no log row, 200 with result envelope.
- tests/test_outbound_replay_contract.py [NEW]: 33 contract tests Groups A-L.

Result: 3769 tests pass (3736 + 33 new). No DB schema changes. 2 pre-existing SQLite failures (unrelated, unchanged).


## Phase 148 — Sync Result Webhook Callback (Closed)

Best-effort HTTP POST to IHOUSE_SYNC_CALLBACK_URL after ok syncs. No DB changes.

Changes:
- src/services/outbound_executor.py [MODIFIED]: `_CALLBACK_URL` + `_fire_callback()` — noop when unconfigured, ok only, JSON payload {event:sync.ok, ...}, urllib 5s timeout, all errors swallowed. Called in execute_sync_plan() after _persist().
- tests/test_sync_callback_contract.py [NEW]: 30 contract tests Groups A-J.

Result: 3799 tests pass (3769 + 30 new). No DB schema changes. No API changes. 2 pre-existing SQLite failures (unrelated, unchanged).


## Phase 149 — RFC 5545 VCALENDAR Compliance Audit (Closed)

Audit and update the iCal payload to include all RFC 5545 required fields.

Changes:
- src/adapters/outbound/ical_push_adapter.py [MODIFIED]: added `CALSCALE:GREGORIAN`, `METHOD:PUBLISH` to VCALENDAR header; `DTSTAMP:YYYYMMDDTHHMMSSZ` (UTC) and `SEQUENCE:0` to VEVENT; PRODID bumped to Phase 149; `datetime`/`timezone` import added.
- tests/test_rfc5545_compliance_contract.py [NEW]: 37 contract tests Groups A-J.
- tests/test_ical_date_injection_contract.py [MODIFIED]: PRODID assertion Phase 140 → Phase 149 (1 line).

Result: 3836 tests pass (3799 + 37 new). No DB schema changes. No API changes. 2 pre-existing SQLite failures (unrelated, unchanged).









