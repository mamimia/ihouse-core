# Check-In & Check-Out (Combined) — System Reality (Read Before Design)

**Read from:** ihouse-core real codebase
**Date:** 2026-04-03

---

## What Already Exists

### Role Synthesis (Not a Canonical Role)
`checkin_checkout` is NOT stored in the database. It is computed at JWT login time:
- Backend reads `worker_roles` array from tenant info
- If both `checkin` AND `checkout` are present → synthesizes `effective_worker_role = "checkin_checkout"`
- JWT includes: `role: "worker"`, `worker_roles: ["checkin", "checkout"]`, `worker_role: "checkin_checkout"`
- Same synthesis works in Act As / Preview As modes

### Hub Page (`/ops/checkin-checkout/page.tsx`)
A navigation hub — NOT a re-implementation of either check-in or check-out flows.

**Purpose:** Unified home for staff who handle both arrivals and departures.

**Content:** Two summary cards:
1. **Arrivals Card** — count of pending CHECKIN_PREP tasks (next 7 days), next arrival time with countdown (deadline: 14:00), CTA linking to `/ops/checkin`
2. **Departures Card** — count of active + overdue CHECKOUT_VERIFY tasks, next checkout time with countdown (deadline: 11:00), overdue count highlighted in red, CTA linking to `/ops/checkout`
3. **Profile & Settings** — link to `/worker`

### Navigation (4-Tab BottomNav)
```
CHECKIN_CHECKOUT_BOTTOM_NAV:
  📅 Today       → /ops/checkin-checkout  (hub home)
  📋 Arrivals    → /ops/checkin           (full check-in flow)
  🚪 Departures  → /ops/checkout          (full check-out flow)
  ✓  Tasks       → /tasks                 (merged task list)
```

The hub IS the home layer — no separate `/worker` page in the nav. Combined role workers see Today/Arrivals/Departures/Tasks instead of the single-role pattern of Home/Work/Tasks.

### Route Access Control (Middleware)
`checkin_checkout` role allowed paths: `/ops/checkin-checkout`, `/worker`

Workers navigate to `/ops/checkin` and `/ops/checkout` via hub cards — not directly via middleware role check.

### Task Merging (Tasks Tab)
Special handling for combined role:
- Fetches CHECKIN tasks and CHECKOUT tasks in parallel (two API calls)
- Merges and deduplicates by `task_id`
- Shows combined view with both arrival and departure tasks

### Data Sources
- **Arrivals:** `/tasks?kind=CHECKIN_PREP` — filtered to approved properties only (Phase 887c)
- **Departures:** `/tasks?kind=CHECKOUT_VERIFY` — split into overdue (before today) and active (today or later)
- **Countdown hooks:** `useCountdown(nextArrivalIso, '14:00')` and `useCountdown(nextCheckoutIso, '11:00')`

### Actual Workflows
When the worker taps into Arrivals or Departures, they enter the full single-role pages:
- **Arrivals:** 7-step conditional wizard (same as CHECK_IN_STAFF)
- **Departures:** 5-step flow (same as CHECK_OUT_STAFF)

These flows are NOT duplicated — the hub links to the existing pages.

---

## What Is Missing

1. **No same-day turn visualization** — if a property has a departure at 11:00 and an arrival at 14:00, the hub shows them as separate cards in separate tabs with no visual linkage
2. **No combined timeline view** — arrivals and departures are in separate tabs, no interleaved chronological view
3. **No priority ordering across types** — an overdue checkout and an imminent arrival can't be compared in one ranked list
4. **No "turnaround chain" awareness** — no indication that a departure feeds into a cleaning feeds into an arrival for the same property
5. **No quick-switch between tabs** — worker navigating check-in flow must use bottom nav to access departures, no horizontal swipe or cross-link

---

## What Is Unclear

1. Whether the combined role worker can access `/ops/checkin` and `/ops/checkout` pages directly (middleware only lists `/ops/checkin-checkout` and `/worker` for this role — but the bottom nav links there)
2. Whether the hub page is responsive or mobile-only (currently appears mobile-focused)
3. How property filtering works when the same property appears in both arrival and departure contexts on the same day
