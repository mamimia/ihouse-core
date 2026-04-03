# Claim

`POST /bookings/{booking_id}/checkout` writes `status: "checked_out"` directly to the `bookings` table without going through the event log (`apply_envelope`), contradicting the system's event-sourced architecture invariant.

# Verdict

PROVEN

# Why this verdict

`src/api/deposit_settlement_router.py` lines 392–396 show a direct `db.table("bookings").update({...})` call setting `status = "checked_out"`. The system's canonical write path for booking state is `apply_envelope` — all booking mutations must go through the event log, which projects into `booking_state`. This checkout endpoint writes directly to `bookings` (or `booking_state`), not through `apply_envelope`. This is confirmed by the module invariant: "This router NEVER writes to event_log" — which means the checkout status change has no corresponding event log entry.

# Direct repository evidence

- `src/api/deposit_settlement_router.py` lines 390–396 — direct `bookings` table update
- `src/api/deposit_settlement_router.py` lines 17–20 — module invariant: "NEVER writes to event_log"
- `docs/core/canonical-event-architecture.md` (read in Pass 2) — `apply_envelope` is the only write gate
- `ihouse-ui/app/(app)/ops/checkout/page.tsx` line 188–190 — comment: "Booking status is stale/disconnected in staging"

# Evidence details

**The direct write (lines 390–396):**
```python
now = _now_iso()
db.table("bookings").update({
    "status": "checked_out",
    "checked_out_by": worker_id,
    "checked_out_at": now,
}).eq("booking_id", booking_id).execute()
```
This is a direct UPDATE on the `bookings` table. No `apply_envelope`. No event inserted into `event_log`. The change is not auditable through the event system.

**Module invariant explicitly declares no event log writes:**
```python
Invariant:
    This router NEVER writes to event_log or booking_financial_facts.
    Deposit records are independent — financial integration is deferred.
```
The "never writes to event_log" clause was originally scoped to deposit records, but it applies to all writes in this router — including the checkout completion.

**Frontend comment confirms the inconsistency:**
```typescript
// Phase 883: Checkout world is built on CHECKOUT_VERIFY tasks,
// NOT booking status. Booking status is stale/disconnected in staging.
```
This comment in `ops/checkout/page.tsx` confirms that the checkout frontend team is aware that booking status is unreliable. The checkout flow was rebuilt around `CHECKOUT_VERIFY` tasks precisely because booking status is not a trustworthy signal — which may be a downstream consequence of status being written via direct DB updates rather than through the event system.

**Auto-task creation at checkout (lines 399–411):**
The checkout endpoint also auto-creates a `CLEANING` task after marking the booking as checked out. This task creation goes through `create_task_if_needed` — a different write path than the booking status update.

# Conflicts or contradictions

- The core architectural document states `apply_envelope` is the only write gate for booking mutations. This endpoint directly mutates booking status.
- The `booking_state` table is described as a "derived read-only projection" of the event log. If `bookings.status` is written directly, `booking_state` may diverge from the event log projection.
- The checkout page explicitly notes "Booking status is stale/disconnected in staging" — this may be the observed symptom of direct writes not propagating to the event-sourced projection.

# What is still missing

- Whether `bookings` and `booking_state` are the same table or separate. If the checkout writes to `bookings` and the event system projects to `booking_state`, these could diverge silently.
- Whether any other router has a similar direct-write pattern for booking status changes (e.g., check-in status).

# Risk if misunderstood

If the event log is treated as a complete audit trail for all booking state changes, the checkout transition will be missing from that trail. Any reconciliation, replay, or audit query against the event log will show bookings that were checked out as still in their pre-checkout state.
