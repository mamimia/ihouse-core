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
