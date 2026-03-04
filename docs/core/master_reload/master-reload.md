# iHouse Core — Master Reload Document

This document is used to reload architectural context when a new chat session begins.

It prevents architectural drift and guarantees deterministic continuation.

This document is NOT chronological history.
It is a canonical reload snapshot.

--------------------------------------------------
SECTION 1 — AUTHORITY
--------------------------------------------------

1. Repository state is canonical.
2. Chat memory is not authoritative.
3. If repo state contradicts conversation context, repo wins.
4. Supabase is canonical persistence.
5. SQLite must never be used as production write path.

--------------------------------------------------
SECTION 2 — SYSTEM TYPE
--------------------------------------------------

iHouse Core is a deterministic domain execution kernel.

External interface:
business events only.

Internal mechanics:
hidden behind canonical execution.

State is derived.
Events are canonical.
Truth must be replayable.

--------------------------------------------------
SECTION 3 — CANONICAL STORAGE
--------------------------------------------------

Supabase tables:

public.event_log
public.booking_state

event_log is the immutable event source.

booking_state is derived state.

--------------------------------------------------
SECTION 4 — CANONICAL WRITE PATH
--------------------------------------------------

External request
→ IngestAPI
→ CoreExecutor
→ apply_envelope RPC
→ event_log append
→ STATE_UPSERT (DB internal event)
→ booking_state materialization

apply_envelope is the ONLY write gate.

--------------------------------------------------
SECTION 5 — IDEMPOTENCY GUARANTEE
--------------------------------------------------

Each envelope contains:

idempotency.request_id

Derived:

envelope_id

Duplicate envelope must return:

ALREADY_APPLIED

Duplicate envelopes must NOT:

insert events
mutate booking_state

--------------------------------------------------
SECTION 6 — BOOKING IDENTITY
--------------------------------------------------

Stable business identity:

tenant_id
+
source
+
reservation_ref
+
property_id

This prevents duplicate bookings.

--------------------------------------------------
SECTION 7 — AVAILABILITY CANON
--------------------------------------------------

Availability scope:

tenant_id + property_id

Booking range:

[check_in, check_out)

Half-open interval.

Overlap rule:

existing.check_in < new_check_out
AND
new_check_in < existing.check_out

--------------------------------------------------
SECTION 8 — ACTIVE BOOKING PREDICATE
--------------------------------------------------

Active bookings for availability are defined as:

status IS DISTINCT FROM 'canceled'

Meaning:

NULL → treated as active
active → active
canceled → inactive

--------------------------------------------------
SECTION 9 — FORWARD WRITE RULES
--------------------------------------------------

BOOKING_CREATED

status = 'active'

BOOKING_CANCELED

status = 'canceled'

Under row lock.

Also update:

last_event_id
last_envelope_id

Version must increment deterministically.

--------------------------------------------------
SECTION 10 — INTERNAL EVENTS
--------------------------------------------------

STATE_UPSERT

is a DB-generated internal event.

External producers must never send STATE_UPSERT.

--------------------------------------------------
SECTION 11 — PHASE BOUNDARY
--------------------------------------------------

Last closed phases:

Phase 17C
Overlap Rules, Business Dedup, Read Model Inquiry

Phase 18
Cancellation-aware availability

System state:

Deterministic
Forward-only
Replay safe
Financial-grade idempotency

--------------------------------------------------
SECTION 12 — WHEN TO USE THIS DOCUMENT
--------------------------------------------------

When opening a new chat session.

When architectural drift is suspected.

When context must be reloaded.

--------------------------------------------------
SECTION 13 — SPINE RELOAD PROCEDURE
--------------------------------------------------

Run:

sed -n '1,260p' docs/core/current-snapshot.md
sed -n '1,260p' docs/core/system-identity.md
sed -n '1,260p' docs/core/canonical-event-architecture.md
sed -n '1,260p' docs/core/construction-log.md

Paste output into chat.

Assistant must identify latest locked phase and resume execution from that boundary.

--------------------------------------------------
END OF MASTER RELOAD DOCUMENT
--------------------------------------------------
