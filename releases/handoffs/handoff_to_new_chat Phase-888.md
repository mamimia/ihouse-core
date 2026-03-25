> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 888 → Phase 889

**Date:** 2026-03-26
**Branch:** `checkpoint/supabase-single-write-20260305-1747`
**Last commit:** `a222706` (+ closure commit pending)

---

## What was done in this session

### 1. Property Booking Guards (3-Layer Enforcement)
Non-approved properties are now blocked from booking creation at three levels:

| Layer | Where | How |
|-------|-------|-----|
| **UI** | Property Detail page | "Add Booking" button hidden for non-approved properties |
| **Intake** | Booking intake PropertySelect | Filter only shows `approved` properties |
| **Backend** | `POST /bookings/manual` | Hard 422 rejection if property status ≠ approved |

**Files:** `manual_booking_router.py`, `properties/[id]/page.tsx`, `bookings/intake/page.tsx`

### 2. Context-Aware Booking Intake Flow
When "Add Booking" is initiated from a Property Detail page:
- Intake flow shows the property context in the header
- "Back" button returns to the source property (not the generic intake selector)
- Property is pre-selected and locked

### 3. Staffing-to-Task Assignment Backfill (Phase 888 — LOCKED)
**Canonical rule** — formally approved and recorded in `docs/core/RULE_staffing_task_backfill.md`:

| Scenario | PENDING | ACKNOWLEDGED+ |
|----------|---------|---------------|
| Assign worker | ✅ Backfill NULL → worker | ❌ Never touched |
| Remove worker | ✅ Clear → NULL | ❌ Never touched |
| Replace A→B | ✅ Move to B | ❌ Never touched |

- **Role-agnostic**: applies to Cleaner, Check-in, Check-out, Combined, Maintenance
- **"Combined" is NOT a separate role** — it's a worker with both `checkin` and `checkout` in `worker_roles[]`
- **Staging-proven**: 3 cases, 9/9 tasks in each case behaved correctly

**Files:** `permissions_router.py` (`_backfill_tasks_on_assign`, `_clear_tasks_on_unassign`, `_ROLE_TO_TASK_ROLES`)

### 4. Acknowledge Button Audit (Discovery — Open)
- Traced the Acknowledge button in the Cleaner task card UI
- Identified that it was designed as an explicit "I have seen this task" signal (distinct from "I am starting work")
- Found a suspected wrong-endpoint bug: UI calls `/tasks/{id}/status` instead of `/worker/tasks/{id}/acknowledge`
- **Not yet runtime-verified** — needs staging network trace proof

### 5. Add Staff Screen Normalization
- Updated Add Staff flow to match the new 4-tab staff-member model (Profile, Role & Assignment, Access & Comms, Documents & Compliance)
- Parity with existing staff-member edit view

---

## Current System State

| Component | Status |
|-----------|--------|
| **Current Phase** | 889 (Next Phase) |
| **Last Closed Phase** | 888 (Staffing-to-Task Backfill) |
| **Backend** | Railway (auto-deployed from `a222706`) |
| **Frontend** | Vercel (manually deployed) |
| **Branch** | `checkpoint/supabase-single-write-20260305-1747` |
| **Tests** | ~7,700+ passing, ~20 pre-existing failures (not introduced in this session) |

---

## Open Items / What Comes Next

### Immediate follow-ups (from this session):

1. **Acknowledge button staging proof** — click Acknowledge on a cleaner card, capture the network request, confirm which endpoint handles it, confirm the task state transition in persistence. This was started but not completed.

2. **Worker-UI audit continuation** — the Acknowledge audit was step 1 of a button-by-button, flow-by-flow worker-UI audit across Cleaning, Check-in, Check-out, and Maintenance.

### Pre-existing open items (from prior sessions):

3. **Add Staff: Email/User ID field clarity** — the required `Email / User ID *` field in Add Staff is blocking creation and its product meaning is unclear. Needs a decision on whether staff creation should require a pre-existing Supabase Auth identity or should auto-provision one.

4. **Pre-existing test failures** — approximately 20 test failures across older contract test files (`test_audit_events_contract.py`, `test_wave6_*`, `test_wave7_*`, `test_whatsapp_escalation_contract.py`, `test_notification_dispatcher_contract.py`, `test_integration_management.py`). These are all pre-existing and not introduced in this session.

---

## Key Files Modified in This Session

| File | What Changed |
|------|-------------|
| `src/api/permissions_router.py` | Task backfill logic on staff-property assignment changes |
| `src/api/manual_booking_router.py` | Backend 422 guard for non-approved property bookings |
| `ihouse-ui/app/(app)/admin/properties/[id]/page.tsx` | Hidden Add Booking for non-approved properties |
| `ihouse-ui/app/(app)/admin/bookings/intake/page.tsx` | Property-scoped booking flow + approved-only filter |
| `docs/core/RULE_staffing_task_backfill.md` | Canonical locked rule |
| `docs/archive/phases/phase-888-spec.md` | Phase spec |

---

## Deployment Rules (Reminder)

| Target | Method |
|--------|--------|
| **GitHub** | `git push origin HEAD:checkpoint/supabase-single-write-20260305-1747` |
| **Railway (Backend)** | Auto-deploys on git push |
| **Vercel (Frontend)** | Manual: `cd ihouse-ui && npx vercel --prod --yes` |
