# iHouse Core Phase 5
## 01 Event Versioning Model

Status: Draft
Scope: Core backend only. No UI.

### Goals
1. Events remain replayable forever.
2. Old events never break rebuild after schema upgrades.
3. Event meaning is stable. Only representation may evolve.
4. Migrations are disciplined and provably replay safe.

### Definitions
Event Type:
A stable domain name like BOOKING_SYNC_INGEST.

Event Version:
An integer that describes the payload contract for a given event type.
Example: BOOKING_SYNC_INGEST v1, v2.

Schema Version:
The database schema version (migration number) at the time of processing.
Used for diagnostics and migration gating, not for interpreting event meaning.

Canonical Event:
The latest version of the payload contract for an event type, as the engine expects internally.

Upcaster:
A pure function that transforms an older event payload into the canonical version.

### Event Envelope
Every stored event row must contain, at minimum:

event_id: string UUID
request_id: string
event_type: string
event_version: int
ts_ms: int
actor_user_id: string|null
actor_role: string|null
property_id: string|null
payload_json: json
meta_json: json

meta_json must include:
schema_version_at_write: int
producer: string
trace_id: string|null

### Versioning Policy
1. event_type is immutable and never renamed.
2. event_version is immutable once written.
3. Only payload contract changes require a new event_version.
4. Never reuse a version number.
5. Canonical version per event_type is defined in code as LATEST[event_type].

### Compatibility Rules
Backward compatibility on replay means:
Rebuild can process any historical event and produce a correct canonical interpretation.

Allowed change types without bumping event_version:
A. Additive metadata in meta_json.
B. Non semantic additions that are not read by projections or skills.

Changes that require bumping event_version:
A. Adding a required payload field.
B. Renaming a payload field.
C. Changing type or meaning of an existing field.
D. Changing default behavior implied by payload.

Forbidden changes:
A. Reinterpreting a historical field to mean something else.
B. Making rebuild depend on current wall clock time.
C. Making rebuild depend on external services.

### Canonicalization Pipeline
During replay and ingest, the engine must do:

1. Parse envelope.
2. Lookup canonical version: v_latest = LATEST[event_type].
3. If event_version == v_latest:
   canonical_payload = payload_json
4. If event_version < v_latest:
   canonical_payload = upcast(event_type, event_version, payload_json) producing v_latest
5. If event_version > v_latest:
   Reject as unknown future version.

Upcasters must be:
Pure and deterministic
No DB reads
No network
No randomness
No "now"
Only structural transforms and safe defaults

### Upcaster Registry Contract
Code must provide:

LATEST: Map[event_type] -> int
UPCASTERS: Map[(event_type, from_version)] -> function(payload) -> payload

Upcasting composes:
If latest is v3 and event is v1:
apply v1_to_v2, then v2_to_v3.

### Defaults and Nullability
When upcasting introduces new fields:
1. Use deterministic defaults derived from existing payload when possible.
2. Otherwise use explicit constants.
3. Never infer from current schema or current time.

### Validation Gates
The following must be testable and required:

1. For every event_type, replay of all versions produces identical projections as replay of already upcasted canonical events.
2. validate_rebuild must pass across schema upgrades.
3. A migration that changes projections must ship with:
   a. Upcaster updates if needed
   b. Replay test that covers at least one old version event fixture

### Stored Versus Derived
Stored events are never rewritten.
If we need a new representation, we add a new event version and upcasters.

### Notes
This model is intentionally strict.
It optimizes for permanent replayability and production safety in a SaaS engine.
