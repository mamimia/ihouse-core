# Phase 42 — Reservation Amendment Discovery

## Status

Closed

## Type

Discovery only. No implementation. No new code. No schema changes.

## Objective

Investigate what it would take to safely introduce `BOOKING_AMENDED` as a canonical OTA event kind.

Determine whether the current system architecture can support amendment events and what preconditions must be satisfied before implementation begins.

---

## Discovery Findings

### Q1: How do OTA providers (Booking.com, Expedia) represent amendment events?

**Finding:**

Both adapters currently map amendment signals to `MODIFY` semantic kind:

```python
# semantics.py
elif event_type in {"reservation_modified", "modified", "amended"}:
    semantic = BookingSemanticKind.MODIFY
```

**Booking.com** emits:
- `reservation_modified` — represents date/guest/rate changes on an existing booking

**Expedia** emits:
- `modified` — same semantics

Both are already recognized and classified — but both adapters throw `ValueError("MODIFY events are not supported")` in `to_canonical_envelope()` before they reach the canonical layer.

The payload field that carries amendment data is `provider_payload` in both adapters — a pass-through blob with no normalized structure. Any amendment data (check_in, check_out, guest count, rate) exists only inside that blob.

**Gap:** There is no normalized amendment payload structure. The amendment data is unextracted, provider-specific, and variable across providers.

---

### Q2: Can amendment intent be classified deterministically at the adapter layer?

**Finding:**

**Partially yes — for MODIFY recognition. No — for safe amendment fields.**

The semantic classification (`semantics.py`) already identifies `MODIFY` deterministically based on the `event_type` field. This classification is stateless and does not read `booking_state`.

However, "amendment intent" involves two layers:
1. **Event kind identification** (`MODIFY`) — ✅ already deterministic
2. **Field-level amendment extraction** (what changed: dates, guests, rate) — ❌ not deterministic

The second layer requires:
- Knowing which fields are authoritative in each provider's payload
- Normalizing fields like `check_in`, `check_out` across providers
- Deciding whether partial payloads represent full amendments or incremental diffs

Different providers use different payload shapes for the same amendment. Booking.com sends `new_reservation_info`, Expedia sends `changes.dates`. There is no shared structure.

**Conclusion:** Amendment intent can be _identified_ deterministically. Amendment _content_ cannot yet be extracted deterministically in a provider-agnostic way.

---

### Q3: What does apply_envelope need to do differently for an amendment vs a creation?

**Finding:**

Current `apply_envelope` handles two event kinds in its `event_kind` enum:

```sql
CREATE TYPE "public"."event_kind" AS ENUM (
    'BOOKING_CREATED',
    'BOOKING_CANCELED',
    ...
);
```

For `BOOKING_CREATED`:
- Validates that no booking with that `booking_id` exists
- Inserts initial `booking_state`
- Appends `BOOKING_CREATED` to `event_log`

For `BOOKING_CANCELED`:
- Validates that a booking with that `booking_id` exists
- Updates `booking_state` to canceled
- Appends `BOOKING_CANCELED` to event_log

For a hypothetical `BOOKING_AMENDED`:
- Validates that a booking exists AND is in `ACTIVE` state (not already canceled)
- Updates `booking_state` with the amended fields (check_in, check_out, guests, rate)
- Appends `BOOKING_AMENDED` to `event_log`
- Must merge amendment fields onto existing state — **not replace**

**Required changes to apply_envelope:**
1. Add `BOOKING_AMENDED` to the `event_kind` enum — **DDL change**
2. Add a new branch in the `BOOKING_AMENDED` case that performs state merge
3. Define which fields are amendable and which are immutable (booking_id, source, reservation_ref must be immutable)
4. Define the expected payload shape for the emitted `BOOKING_AMENDED` event

**This is a significant schema migration and stored procedure change. It requires careful invariant analysis before implementation.**

---

### Q4: What ordering guarantees are required before amendment is safe?

**Finding:**

Amendment requires `ACTIVE` booking state to exist before the amendment arrives. This creates a strict ordering dependency:

```
BOOKING_CREATED → (ACTIVE state)
       ↓
BOOKING_AMENDED → (UPDATED state)
       ↓
BOOKING_CANCELED → (CANCELED state)  [optional]
```

If `BOOKING_AMENDED` arrives before `BOOKING_CREATED`:
- `apply_envelope` must raise `BOOKING_NOT_FOUND` (same as CANCELED before CREATED)
- The amendment must land in the DLQ (Phase 38)
- Replay must become possible once CREATED arrives (Phase 39)

The DLQ layer (Phases 38-39) already provides the **infrastructure** for out-of-order amendment handling. However, the **replay ordering logic** does not yet know that an amendment should wait for its CREATED event. Replay is currently manual and unordered.

**Conclusion:** Ordering guarantees for BOOKING_AMENDED depend on:
1. The DLQ + replay infrastructure (exists ✅)
2. A booking-level replay ordering rule (not yet implemented ❌)
3. The `apply_envelope` guard that rejects amendment on non-ACTIVE state (not yet implemented ❌)

---

### Q5: What state must exist in booking_state before amendment is safe?

**Finding:**

Based on the current `apply_envelope` behavior and `booking_state` schema, an amendment is safe only when:

| Precondition | Source of truth |
|-------------|----------------|
| booking_id exists in booking_state | apply_envelope check |
| booking lifecycle state is ACTIVE (not CANCELED) | booking_state.status field |
| Amendment fields are not in conflict with existing check_in/check_out | apply_envelope overlap check |

The current `booking_state` table contains:
- `booking_id`
- `tenant_id`, `source`, `reservation_ref`, `property_id`
- `check_in`, `check_out`
- `status` (implied from events)

The `status` field (ACTIVE, CANCELED) is not explicitly tracked as a column in the current schema — it is derived from the event log. This means `apply_envelope` must derive status from event history at apply time, or a `status` column must be added to `booking_state`.

**Gap:** No explicit `status` column in `booking_state`. Apply_envelope would need to read the last event for a `booking_id` to determine lifecycle state.

---

### Q6: What invariants could an amendment violate if applied out-of-order?

**Finding:**

| Invariant | Risk if amendment out-of-order |
|-----------|-------------------------------|
| booking_id uniqueness | Low — booking_id is stable |
| ACTIVE state precondition | High — amendment on a CANCELED booking would break lifecycle |
| Date overlap dedup | Medium — amendment may introduce dates that overlap another booking |
| event_log append-only | None — BOOKING_AMENDED appends normally |
| Idempotency | High — replaying an amendment twice must be safe (idempotency key required) |

The most dangerous invariant violation is: **applying an amendment to a booking that was canceled between when the amendment was emitted and when it was applied**. This can happen in distributed OTA webhook delivery where events arrive out-of-order.

The existing `apply_envelope` overlap detection would partially protect against date collision, but there is no explicit lifecycle guard for "canceled booking must not be amended."

---

### Q7: Is booking_id stable across amendment events from the same provider?

**Finding:**

**Yes** — `booking_id` is always derived from `{source}_{reservation_ref}`. Both fields are present in `BOOKING_CREATED` and expected to remain identical in subsequent events for the same booking.

`reservation_id` (the OTA-side identifier) maps 1:1 to `reservation_ref`. Amendment events from Booking.com and Expedia both carry the same `reservation_id` as the original creation event.

The only risk is a provider that reuses `reservation_id` across different bookings — which would be a provider data quality violation, not a system bug.

**Conclusion:** booking_id is stable across amendment events. ✅

---

## Summary: Prerequisites Before BOOKING_AMENDED Implementation

| Prerequisite | Status | Notes |
|-------------|--------|-------|
| DLQ infrastructure | ✅ Done | Phases 38-39 |
| booking_id stability | ✅ Verified | Phase 36 + Q7 |
| Amendment intent classification | ✅ Done | semantics.py already classifies MODIFY |
| Normalized amendment payload schema | ❌ Missing | Q2: provider fields not extracted |
| apply_envelope BOOKING_AMENDED branch | ❌ Missing | Q3: DDL + stored procedure |
| booking_state.status explicit column | ❌ Missing | Q5: lifecycle guard |
| ACTIVE-state amendment guard in apply_envelope | ❌ Missing | Q4 + Q5 |
| Amendment replay ordering rule | ❌ Missing | Q4: manual replay exists, ordering doesn't |
| Idempotency key structure for amendments | ❌ Not defined | Q6 |
| Amendable vs immutable fields specification | ❌ Not defined | Q3 |

**3 of 10 prerequisites are satisfied. 7 remain.**

---

## Recommendation for Phase 43+

Do not begin BOOKING_AMENDED implementation until:

1. A normalized `AmendmentPayload` schema is defined (provider-agnostic, covers dates + guest count)
2. `booking_state` has an explicit `status` column (ACTIVE, CANCELED)
3. apply_envelope includes lifecycle guard for amendment
4. Idempotency key structure for amendment events is defined and agreed

The next concrete step is:

**Phase 43 — booking_state Status Column** — add explicit `status` tracking to enable lifecycle guards.

---

## What Remains Unchanged

- `MODIFY → deterministic reject-by-default` remains in place
- No skills were modified
- No database schemas were changed
- No new code was written in this phase
