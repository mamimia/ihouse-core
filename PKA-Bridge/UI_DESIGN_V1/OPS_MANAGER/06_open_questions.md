# OPS Manager — Open Questions (V1)

---

## Design Questions (Need Decision)

### Q1: Hub Activity Feed — Mobile Placement
The activity feed (live audit stream) is prominent on desktop (right column). On mobile, it's not shown on the hub — it would be buried below the fold.
**Options:**
- A) Keep it off mobile hub entirely — it's a desktop value-add
- B) Add it as a collapsible section below streams on mobile
- C) Make it accessible via a separate "Activity" tab in the "More" menu
**Recommendation:** Option A for V1. Mobile hub should be action-focused (alerts + streams), not monitoring-focused.

### Q2: Execution Drawer — Mobile State Preservation
When a manager takes over a task on mobile and then navigates to an alert, the wizard state is lost. On desktop, the drawer stays open alongside navigation.
**Decision needed:** Accept this V1 limitation, or invest in mobile wizard state preservation (background tab)?
**Recommendation:** Accept the limitation. Document it. Add a "you have an active takeover" banner on hub if one exists.

### Q3: Alert Auto-Refresh vs. Push
Currently alerts poll every 30 seconds. For a command center, this introduces up to 30s latency.
**Options:**
- A) Keep 30s polling (current implementation, simpler)
- B) Add SSE/WebSocket for real-time alert push
**Recommendation:** Keep 30s polling for V1. Note that real-time push is a V2 improvement.

### Q4: Manager Notification Channels
The profile has LINE ID and phone fields, but the backend notification dispatch system wasn't fully traced.
**Question:** Does the system actually send notifications to LINE/SMS, or are these stored but not used yet?
**Impact:** If not wired, the profile notification section is a promise not yet delivered.

### Q5: Calendar — Depth vs. Simplicity
The calendar shows booking counts and task dots, but tapping a day shows a simple list.
**Question:** Should the calendar day view show the turnover chain (checkout → clean → checkin) for that day's properties, or keep it as a flat list?
**Recommendation:** Flat list for V1. Turnover chain visualization belongs in the Stream view.

---

## Technical Questions (Need Verification)

### T1: Manager Task Endpoint Scoping
The code uses `GET /manager/tasks` (property-scoped) not `GET /tasks` (unscoped). Need to verify that the scoping correctly includes all properties assigned to this manager and nothing else.

### T2: Audit Stream Actions
The hub activity feed reads from `/manager/audit`. The exact set of actions included (TASK_ACKNOWLEDGED, TASK_COMPLETED, BOOKING_FLAGS_UPDATED, MANAGER_TAKEOVER_INITIATED, etc.) needs to be documented so the UI can correctly categorize and color-code each action type.

### T3: Booking Operational Notes
The bookings page supports adding operational notes and approving early checkout. These endpoints need to be verified as implemented and accessible to the manager role.

### T4: Coverage Matrix Data
The team page shows a 3-lane coverage matrix (Cleaning | Maintenance | Checkin/Checkout). The data structure from `GET /manager/team` needs to be verified to ensure it returns per-property, per-lane worker assignments with Primary/Backup designation.

---

## Missing Pieces (Known Gaps)

### M1: No Guest Communication from Manager
The manager can see booking details but cannot directly message a guest from the manager UI. Guest messaging routes through the ops/check-in worker.
**Question:** Should V1 add a "Message Guest" action on booking detail, or keep communication routed through workers?

### M2: No Financial Visibility
The manager has no financial screens — no revenue view, no deposit status view, no payout information. Financial capability is separate from operational management.
**Question:** Is this intentional separation, or should the manager have read-only financial visibility?

### M3: No Maintenance Vendor Management
Maintenance jobs show worker assignment but no external vendor/contractor management.
**Question:** Are maintenance tasks always handled by internal workers, or does the system need contractor dispatch?

### M4: No Shift / Schedule View
The team page shows current assignments and coverage but no shift planning or schedule management.
**Question:** Is scheduling handled outside the system (manual/external), or is it a planned feature?
