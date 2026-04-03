# Cleaner — System Reality (Read Before Design)

**Read from:** ihouse-core real codebase
**Date:** 2026-04-03

---

## What Already Exists

### Screens (Frontend: `/ops/cleaner/page.tsx`, ~1078 lines)
5-screen wizard: LIST → DETAIL → CHECKLIST → COMPLETE → SUCCESS

1. **LIST** — Today + 7 days cleaning tasks, 3-card summary (active/completed/next deadline), Today/Upcoming/Completed sections
2. **DETAIL** — Task overview: property, due date, description, "Start Cleaning" or "Resume Cleaning" buttons
3. **CHECKLIST** — The core cleaning screen: room-grouped checklist items, photo capture per room, supply checks, inline issue reporting, completion gate
4. **COMPLETE** — Confirmation: summary of checklist/photos/supplies progress, "Mark as Ready" button
5. **SUCCESS** — "Cleaning Complete" + "{Property} is now Ready" confirmation

### Checklist System (Template-Based)
- Default template: 21 items across 5 rooms (Bedroom, Bathroom, Kitchen, Living Room, Exterior)
- Items: checkbox per task (e.g., "Change bed sheets", "Clean toilet", "Sweep entrance")
- Each item has `room`, `label`, `label_th` (Thai), `requires_photo` flag
- Template loaded from `/properties/{id}/cleaning-checklist` → fallback to defaults

### Photo System
- Photos required per room (6 rooms need coverage in default template)
- FormData upload to Supabase Storage: `{tenant_id}/{task_id}/{room_label}_{uuid}.{ext}`
- JPEG, PNG, WebP, HEIC/HEIF; max 10MB
- Capture via `capture="environment"` (rear camera on mobile)
- Fallback: JSON endpoint if FormData fails; local-only if both fail

### Supply Check System (7 items)
- Sheets, Towels, Soap, Shampoo, Toilet Paper, Trash Bags, Cleaning Supplies
- 4-state cycle: unchecked → ok → low → empty (cycling button)
- `all_supplies_ok` = true only if ALL items are "ok"
- Supply alerts trigger if any item is "empty"

### Issue Reporting (Inline on Checklist Screen)
- Collapsible form: "🚨 Report Issue"
- Categories: general, plumbing, electrical, damage, pest, appliance, safety
- Severity: Normal or Critical
- Critical: "immediately blocks property + triggers 5-minute SLA"
- Creates MAINTENANCE task via problem_report_router

### Property Ready Gate (3-Flag)
Completion blocked unless:
1. `all_items_done` — every checklist item checked
2. `all_photos_taken` — every `requires_photo` room has a photo
3. `all_supplies_ok` — all supplies are "ok" (can be force-overridden)

Backend returns 409 with specific `blockers` array if gate not met.

### Property Status Transition (Post-Completion)
- If open issues exist → `operational_status = "ready_with_issues"`
- If no open issues → `operational_status = "ready"`
- Audit event: PROPERTY_OPERATIONAL_STATUS_CHANGE

### State Persistence
- Progress saves to DB: checklist state, supply state, photos uploaded
- Worker can refresh page and resume exactly where they left off
- `loadProgress()` restores from DB; fallback to fresh template

### Navigation (BottomNav)
- 🏠 Home → `/worker`
- 🧹 Cleaning → `/ops/cleaner`
- ✓ Tasks → `/tasks`

### CleanerWizard Export
Exported for embedding in Manager's execution drawer (Phase 1022-H).

---

## What Is Missing

1. **No room-by-room spatial navigation** — rooms are checklist groupings, not distinct screens
2. **No photo preview/zoom** — photos captured but no full-screen review
3. **No supply auto-reorder** — low/empty status logged but no ordering action
4. **No cleaning time tracking** — no start/end timestamps per room or overall
5. **No "pause and resume later" UI** — state persists but no explicit pause action

---

## What Is Unclear

1. Whether the supply "empty" alert actually notifies anyone (SSE? manager alert?)
2. Whether `force_complete` (bypassing supplies gate) is accessible from worker UI or admin-only
3. How custom templates (non-default) affect the checklist length and photo requirements
