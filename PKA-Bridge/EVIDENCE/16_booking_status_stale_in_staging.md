# Claim

The checkout frontend explicitly documents that booking status is "stale/disconnected" in staging, and the checkout workflow was rebuilt to avoid depending on it.

# Verdict

PROVEN

# Why this verdict

`ihouse-ui/app/(app)/ops/checkout/page.tsx` line 188–190 contains a direct comment in the production source code: "Phase 883: Checkout world is built on CHECKOUT_VERIFY tasks, NOT booking status. Booking status is stale/disconnected in staging." This is not a historical note or a TODO — it is the active architectural comment for the page. The checkout page explicitly fetches `CHECKOUT_VERIFY` tasks (not bookings by status) and uses task state as the source of truth for the checkout workflow.

# Direct repository evidence

- `ihouse-ui/app/(app)/ops/checkout/page.tsx` lines 188–190 — architectural comment
- `ihouse-ui/app/(app)/ops/checkout/page.tsx` line 216 — fetches `/worker/tasks?worker_role=CHECKOUT&limit=100`
- `src/api/deposit_settlement_router.py` lines 390–396 — direct booking status write (confirmed root cause candidate)
- `src/api/deposit_settlement_router.py` lines 17–20 — "NEVER writes to event_log"

# Evidence details

**The comment (lines 188–190):**
```typescript
// Phase 883: Checkout world is built on CHECKOUT_VERIFY tasks,
// NOT booking status. Booking status is stale/disconnected in staging.
```

**The data fetch confirms the architectural pivot (line 216):**
```typescript
const taskRes = await apiFetch<any>('/worker/tasks?worker_role=CHECKOUT&limit=100');
```
The checkout page loads `CHECKOUT_VERIFY` tasks, not `GET /bookings?status=checked_in`. Task state is the live signal; booking status is not trusted.

**Root cause candidate:**
The direct DB write in `deposit_settlement_router.py` (investigation 15) does not go through the event system. If `booking_state` (the event projection) and `bookings` (the directly-written table) are not the same table, the checkout status change may not propagate to wherever the checkout page previously looked for "checked_in" bookings.

# Conflicts or contradictions

- The comment says the problem exists "in staging" specifically — not in production. This implies production may differ. The cause is unknown from reading alone.
- The booking status is still set to `"checked_out"` by the checkout endpoint — it is written somewhere. Whether that write is visible to queries that read booking status is unclear.

# What is still missing

- Whether `bookings.status` and `booking_state.status` are the same field or two separate fields that can diverge.
- Whether the "stale/disconnected in staging" observation was a temporary staging artifact or a persistent symptom of the direct-write pattern.
- Whether any API endpoint correctly reads `status = "checked_in"` bookings for the checkout list — and if not, whether the task-based approach is the only reliable path.

# Risk if misunderstood

If a developer builds a new workflow that relies on `booking.status` to determine checkout readiness, it will exhibit the same staleness that drove the Phase 883 architectural pivot. The task-based approach is the system's own documented workaround — bypassing it will reintroduce the original problem.
