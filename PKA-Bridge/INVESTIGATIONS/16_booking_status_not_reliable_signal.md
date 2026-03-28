# Title

Booking Status Is Documented as Stale in Staging — The Checkout Workflow Was Rebuilt to Avoid Relying on It

# Why this matters

Booking status is a foundational field. Dozens of queries, filters, and workflows could reasonably rely on `booking.status` to determine the current state of a booking. If booking status is unreliable, any feature that filters on `status = "checked_in"` to find ready-for-checkout bookings, or `status = "active"` to list current guests, is returning stale data. This is not a theoretical concern — the development team explicitly acknowledged the problem in Phase 883, documented it in production source code, and rebuilt the checkout workflow to avoid the status field entirely. The problem is in staging today and may be structural enough to affect any production deployment.

# Original claim

The checkout frontend explicitly documents that booking status is "stale/disconnected" in staging, and the checkout workflow was rebuilt to avoid depending on it.

# Final verdict

PROVEN

# Executive summary

`ihouse-ui/app/(app)/ops/checkout/page.tsx` contains a production source comment at line 188: "Phase 883: Checkout world is built on CHECKOUT_VERIFY tasks, NOT booking status. Booking status is stale/disconnected in staging." This is not a test comment or a TODO. It is the architectural rationale for how the checkout page fetches its data — via task queries (`/worker/tasks?worker_role=CHECKOUT`) rather than booking status queries. The comment is consistent with the direct database write pattern identified in Investigation 15, where `POST /bookings/{booking_id}/checkout` writes `status: "checked_out"` directly without going through the event log, potentially leaving `booking_state` (the event-sourced projection) out of sync with the raw `bookings` table. The staleness affects the checkout workflow's ability to find "ready for checkout" bookings by status.

# Exact repository evidence

- `ihouse-ui/app/(app)/ops/checkout/page.tsx` lines 188–190 — architectural comment
- `ihouse-ui/app/(app)/ops/checkout/page.tsx` line 216 — `apiFetch('/worker/tasks?worker_role=CHECKOUT&limit=100')`
- `src/api/deposit_settlement_router.py` lines 390–396 — direct `bookings.update(status: "checked_out")` (root cause candidate)
- `src/api/deposit_settlement_router.py` lines 17–20 — "NEVER writes to event_log"
- `src/api/booking_lifecycle_router.py` lines 75–78 — lifecycle visualization reads only `booking_state` and `event_log`

# Detailed evidence

**The comment — production source, active architectural rationale:**
```typescript
export default function MobileCheckoutPage() {
    // Phase 883: Checkout world is built on CHECKOUT_VERIFY tasks,
    // NOT booking status. Booking status is stale/disconnected in staging.
    const [checkoutTasks, setCheckoutTasks] = useState<CheckoutTask[]>([]);
    const [bookings, setBookings] = useState<Booking[]>([]);  // kept for the checkout flow steps
```
Two signals here:
1. "Booking status is stale/disconnected in staging" — a direct statement of the observed problem.
2. `bookings` state is kept "for the checkout flow steps" but is NOT used for the checkout list — the list uses `checkoutTasks` (CHECKOUT_VERIFY tasks).

**The data fetch that replaced the booking status query:**
```typescript
// Phase 883/886: CHECKOUT_VERIFY tasks are the truth for the checkout world.
const taskRes = await apiFetch<any>('/worker/tasks?worker_role=CHECKOUT&limit=100');
const taskList = taskRes.tasks || taskRes.data?.tasks || taskRes.data || [];
const rawTasks: CheckoutTask[] = Array.isArray(taskList) ? taskList : [];
```
The checkout page does not call `GET /bookings?status=checked_in` or any booking-status-based query to build its list. It calls the worker task endpoint. This is a complete replacement of the intended data source.

**Why tasks are more reliable than booking status:**
Tasks are written through the task system — `create_task_if_needed` which uses `tasks.task_automator`. The pre-arrival scan (running daily at 06:00 UTC) generates `CHECKOUT_VERIFY` tasks for upcoming checkouts. These tasks are independent of booking status. Their lifecycle is managed by the task SLA system. They remain visible even if booking status is stale.

**The booking state is still fetched — but only for the flow steps:**
```typescript
const [bookings, setBookings] = useState<Booking[]>([]);  // kept for the checkout flow steps
```
Once a checkout worker selects a task and enters the 4-step checkout flow, they need booking data (guest name, dates, deposit amounts). The bookings state is populated for this purpose — not for the list. The list is task-based; the details view is booking-based.

**What "stale/disconnected" likely means technically:**
The checkout transition writes directly to the `bookings` table (see Investigation 15). If `booking_state` is a separate table projected from `event_log`, and the checkout write bypasses `event_log`, then:
- `bookings.status` = "checked_out" (written directly)
- `booking_state.status` = still "checked_in" or "active" (event projection not updated)

Any query that reads from `booking_state` to find "checked_in" bookings would still see the booking. The checkout page would show it in the list even after checkout. This matches "stale/disconnected."

**Similarly for check-in status:**
If the check-in transition also writes directly (not confirmed — requires reading `booking_checkin_router.py`), then `booking_state` would also not update on check-in. The booking would appear as "upcoming" when guests have already arrived.

**The lifecycle router confirms the gap:**
`booking_lifecycle_router.py` (Phase 242) tracks only `BOOKING_CREATED`, `BOOKING_AMENDED`, `BOOKING_CANCELED` from the event log. There is no `BOOKING_CHECKED_IN` or `BOOKING_CHECKED_OUT` event tracked. The lifecycle visualization is accurate only for the OTA-sourced booking state machine — it does not reflect operational check-in/checkout transitions.

**Why "in staging" specifically:**
The comment says "in staging" — not "in production." This may mean:
1. The problem was observed in staging and was not yet confirmed in production (production may not have real checkouts).
2. Production may have a different data configuration where the issue doesn't manifest.
3. The staging environment has data that has been through many test checkout cycles, accumulating stale status values.

The comment cannot tell us whether production is also affected. But the code path is the same — the direct write to `bookings` without event log entry exists in both environments.

# Contradictions

- The system documentation describes `booking_state` as the canonical source for booking status. The checkout workflow explicitly doesn't use `booking_state` for its list — it uses tasks.
- The booking lifecycle router claims to visualize the booking state machine. It cannot show the checked-out state because no checkout event exists in `event_log`.
- The system is described as event-sourced and deterministic, with the event log as the single source of truth. The checkout transition is not in the event log.
- The check-in flow (separate from checkout) is claimed to save guest identity and booking state — but whether the check-in status transition goes through `apply_envelope` is unknown. If it does, check-in is event-sourced and checkout is not. If it doesn't, the entire in-property lifecycle is outside the event log.

# What is confirmed

- The checkout page explicitly says booking status is stale in staging.
- The checkout page was rebuilt (Phase 883) to use tasks instead of booking status for the checkout list.
- The `CHECKOUT_VERIFY` task approach is the current production-path architecture.
- The direct write at checkout (bypassing event log) is consistent with the staleness.
- The lifecycle router does not track check-in/checkout events — confirmed by the `_TRACKED_EVENTS` frozenset.

# What is not confirmed

- Whether the stale booking status problem exists in production as well, or only in staging.
- Whether the check-in transition also bypasses `apply_envelope` — if it does, both in and out transitions are event log gaps.
- Whether `bookings` and `booking_state` are the same table or different. If they are the same table, the direct write should be immediately visible to any query on that table. If they are different, the staleness is structural.
- Whether any other frontend page (bookings list, dashboard, calendar) relies on booking status and exhibits the same staleness.

# Practical interpretation

For an operator trying to see which guests are currently in the property (status = "checked_in") or who has departed (status = "checked_out"), the operational status fields are unreliable in at least staging and potentially production. The checkout workflow has a working workaround (CHECKOUT_VERIFY tasks), but:
- The check-in list may have the same problem (no confirmed task-based pivot for check-in)
- The admin bookings view may still show stale statuses
- Any automated trigger that fires on booking status changes (e.g., "booking became checked_out → trigger cleaning task") is unreliable as a status-change detector

The task system is reliable. The booking status field is not. Building new features on booking status as a trigger or filter will reproduce the Phase 883 problem.

# Risk if misunderstood

**If booking status assumed reliable:** New features (calendar displays, auto-trigger workflows, guest count reports) built on booking status will return stale data. The Phase 883 lesson — pivot to tasks — will need to be learned again.

**If "in staging" assumed to mean not in production:** The code path producing the stale status (direct write bypassing event log) exists in both environments. The comment says "in staging" because that's where it was observed. It does not say production is clean.

**If the task-based workaround assumed general:** The CHECKOUT_VERIFY task workaround is specific to the checkout workflow. Check-in, mid-stay status, and other booking lifecycle queries may not have equivalent task-based workarounds. Those surfaces may exhibit the same staleness.

# Recommended follow-up check

1. Read `src/api/booking_checkin_router.py` — check whether the check-in status transition (e.g., `status: "checked_in"`) uses `apply_envelope` or a direct write. This determines whether the staleness affects check-in as well.
2. Read the admin bookings page (`ihouse-ui/app/(app)/bookings/` if it exists) — determine whether it uses booking status for filtering and whether there is a similar Phase 883-style note.
3. Determine whether `bookings` and `booking_state` are the same table by checking migration files for both table definitions.
4. Assess whether `BOOKING_CHECKED_IN` and `BOOKING_CHECKED_OUT` event types should be added to the event log — and whether `apply_envelope` should be called during the check-in and checkout operations.
