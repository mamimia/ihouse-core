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
