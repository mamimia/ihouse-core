# Title

Checkout Completion Writes Booking Status Directly to the Database, Bypassing the Event Log

# Why this matters

The system's architecture document names `apply_envelope` as the only write gate for booking state mutations. All booking lifecycle changes are supposed to produce an event log entry — the event log is the system of record, and `booking_state` is a derived projection from it. The checkout completion endpoint (`POST /bookings/{booking_id}/checkout`) writes `status: "checked_out"` directly to the `bookings` table using a raw `UPDATE`. The module invariant in the same file explicitly declares it never writes to `event_log`. This means the checkout transition: (1) has no event log entry, (2) cannot be replayed or audited through the event system, and (3) may diverge from the event-sourced `booking_state` projection. A frontend comment in the checkout page ("Booking status is stale/disconnected in staging") may be the observed symptom of this architectural mismatch.

# Original claim

`POST /bookings/{booking_id}/checkout` writes `status: "checked_out"` directly to the `bookings` table without going through the event log (`apply_envelope`), contradicting the system's event-sourced architecture invariant.

# Final verdict

PROVEN

# Executive summary

`deposit_settlement_router.py` lines 392–396 show a direct `db.table("bookings").update({"status": "checked_out", ...})` call. The module header explicitly states the router "NEVER writes to event_log." The system's canonical write architecture requires all booking mutations to go through `apply_envelope`, which creates an event log entry and projects into `booking_state`. The checkout endpoint bypasses this entirely. An audit of the event log after a checkout will show no `BOOKING_CHECKED_OUT` event. The checkout page itself documents the consequence: "Booking status is stale/disconnected in staging" — Phase 883 rebuilt the checkout workflow around `CHECKOUT_VERIFY` tasks precisely because booking status is not reliable.

# Exact repository evidence

- `src/api/deposit_settlement_router.py` lines 17–20 — module invariant: "NEVER writes to event_log"
- `src/api/deposit_settlement_router.py` lines 390–396 — direct `bookings.update(status: "checked_out")`
- `ihouse-ui/app/(app)/ops/checkout/page.tsx` lines 188–190 — "Booking status is stale/disconnected in staging"
- `docs/core/canonical-event-architecture.md` (read in Pass 2) — `apply_envelope` is the only write gate
- `src/api/booking_lifecycle_router.py` (Phase 242) — reads from `booking_state` and `event_log` for lifecycle visualization

# Detailed evidence

**The direct write (lines 390–396):**
```python
now = _now_iso()
# Update booking status
db.table("bookings").update({
    "status": "checked_out",
    "checked_out_by": worker_id,
    "checked_out_at": now,
}).eq("booking_id", booking_id).execute()
```
This is a raw SQL UPDATE via the Supabase client. No `apply_envelope`. No event created. The operation is not recoverable from the event log.

**The module invariant:**
```python
"""
Phases 687–690 — Deposit Settlement & Checkout Completion
...
Invariant:
    This router NEVER writes to event_log or booking_financial_facts.
    Deposit records are independent — financial integration is deferred.
"""
```
The scope of this invariant was intended for deposit records but is stated at the router level — it applies to all writes in this router, including the checkout completion. Whether the checkout write was intended to bypass the event log, or whether this was an oversight, cannot be determined from reading alone. The practical effect is the same either way.

**The frontend evidence of the consequence:**
```typescript
// Phase 883: Checkout world is built on CHECKOUT_VERIFY tasks,
// NOT booking status. Booking status is stale/disconnected in staging.
```
This comment at line 188–190 of `ops/checkout/page.tsx` is the most direct evidence of the downstream consequence. The checkout page was rebuilt (Phase 883) to avoid relying on booking status. The reason given is that "Booking status is stale/disconnected in staging." The staleness is consistent with a write path that does not flow through the event projection system.

**The auto-task creation at checkout — a different path:**
```python
# Auto-create CLEANING task (best-effort)
try:
    from tasks.task_model import Task
    from tasks.task_automator import create_task_if_needed
    cleaning_task = Task.build(task_kind="CLEANING", ...)
    create_task_if_needed(db, cleaning_task, tenant_id=tenant_id)
except Exception:
    logger.warning("Failed to auto-create cleaning task for %s", booking_id)
```
The task creation after checkout goes through `create_task_if_needed` — a different write path from the booking status update. Tasks are not part of the event-sourced booking state system. This part of the checkout endpoint follows its own mechanism and is not subject to the same event log concern.

**The audit trail:**
The checkout endpoint writes an audit event:
```python
write_audit_event(db, tenant_id=tenant_id, entity_type="booking",
                  entity_id=booking_id, action="checked_out", ...)
```
This writes to `admin_audit_log` — a separate append-only audit log. This is NOT the same as the booking `event_log` used by the event-sourced architecture. The audit event provides operational accountability. But the booking lifecycle router (Phase 242) reads from `event_log` and `booking_state` for lifecycle visualization — it would not see the checkout transition.

**The `booking_lifecycle_router.py` gap:**
The booking lifecycle visualization endpoint (`GET /admin/bookings/lifecycle-states`) tracks:
```python
_TRACKED_EVENTS = frozenset(["BOOKING_CREATED", "BOOKING_AMENDED", "BOOKING_CANCELED"])
```
`BOOKING_CHECKED_OUT` is not tracked — and could not be, since no such event is written. The lifecycle visualizer shows bookings as `active` or `canceled`. A checked-out booking remains `active` in the lifecycle visualization.

**What `booking_state` likely shows:**
If `booking_state` is a projection of the event log, and no checkout event is written to `event_log`, then `booking_state.status` would not update on checkout. The direct write goes to `bookings.status` (presumably a different table or the same table but bypassing the projection). This would explain why `booking_state` and the direct `bookings` write diverge — the event projection doesn't know about the checkout, but the raw `bookings` table does. The frontend comment "stale/disconnected in staging" is consistent with this explanation.

**Why Phase 883 rebuilt the checkout around tasks:**
If booking status is unreliable as a signal for "this booking needs checkout processing," the checkout workflow cannot use it as a trigger. Tasks (`CHECKOUT_VERIFY`) are more reliable because: (1) they are created by the pre-arrival automation based on checkout dates, (2) they are independent of the booking status projection, and (3) their lifecycle (PENDING → ACK → DONE) is managed by the task system, which has its own write path. The pivot to task-based checkout is a pragmatic workaround for the booking status unreliability.

# Contradictions

- The architectural documentation (`apply_envelope` is the only write gate) is directly contradicted by this endpoint.
- The module invariant's scope ("deposit records are independent") was written for deposit records but extends to all writes in the router due to its placement at the router level. The checkout completion write may have been intended to use `apply_envelope` but was placed in a router that explicitly prohibits it.
- The `booking_lifecycle_router.py` reads `event_log` and `booking_state` for lifecycle data. It would never see checkout transitions. This means the "lifecycle state machine visualization" does not include the checkout terminal state — a significant gap in the operational monitoring surface.
- A `BOOKING_CHECKED_OUT` event type may be defined in the event schema but never emitted. This cannot be confirmed without reading the event type registry.

# What is confirmed

- `POST /bookings/{booking_id}/checkout` writes directly to `bookings` table with `status: "checked_out"`.
- The router's invariant declares it never writes to `event_log`.
- No `BOOKING_CHECKED_OUT` event is emitted anywhere in this code path.
- An audit event is written to `admin_audit_log` (separate from `event_log`).
- The checkout frontend comment explicitly acknowledges booking status is unreliable.
- Phase 883 rebuilt checkout around tasks to avoid relying on booking status.

# What is not confirmed

- Whether `bookings` and `booking_state` are the same table. If they are the same table, the direct write would be visible to the event projection queries. If they are separate, divergence is certain.
- Whether the "stale/disconnected in staging" comment refers to this specific issue or to a different staging environment artifact.
- Whether a `BOOKING_CHECKED_OUT` event type exists in the event schema or event log that was intended to be emitted here.
- Whether the checkin flow has the same bypass (direct write to booking status without event log).
- Whether any OTA webhook or booking cancellation path has similar direct writes.

# Practical interpretation

For operators and auditors, the practical consequences are:
1. **Event log is incomplete**: The booking lifecycle as shown by `event_log` does not include checkout. A booking shows as active until cancellation — checkout is invisible to the event-sourced view.
2. **Booking status is unreliable as a data source**: Any query that uses `booking.status = "checked_in"` to find bookings ready for checkout will not work reliably. Phase 883 discovered this and worked around it.
3. **Audit trail gap**: While `admin_audit_log` records the checkout action, the main event log does not. Event-sourced replay would miss the checkout transition entirely.
4. **Lifecycle visualization gap**: The booking lifecycle router shows active/canceled — not checked_out — because it reads from `event_log`, which has no checkout event.

# Risk if misunderstood

**If event log is assumed complete:** Any feature built on event log queries (analytics, replay, audit) will miss checkout transitions. A bookings pipeline that reconstructs booking history from events will show indefinitely active bookings.

**If booking status is trusted as a reliable filter:** Queries like `WHERE status = 'checked_in' AND check_out <= today` will either return stale results or return nothing, depending on which table they query. Phase 883 solved this for the checkout workflow — but other surfaces may still rely on booking status.

**If the module invariant scope is taken literally for deposits only:** The "NEVER writes to event_log" constraint was intended for deposit independence. It may not have been intended to apply to the checkout completion added to the same router. But the effect is the same regardless of intent.

# Recommended follow-up check

1. Determine whether `bookings` and `booking_state` are the same table or different tables. If they are different, quantify the current divergence between them in staging.
2. Check `booking_checkin_router.py` for the same pattern — if check-in also writes directly to `bookings.status`, the event log gap covers the full guest lifecycle.
3. Search for `BOOKING_CHECKED_OUT` in the event type registry or event log schema to determine whether a checkout event type exists and whether it is ever emitted.
4. Evaluate whether the checkout endpoint should be moved to a router that does write to `event_log`, or whether the checkout should emit `apply_envelope(BOOKING_CHECKED_OUT)` before the direct status write.
