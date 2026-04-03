# Maintenance — System Reality (Read Before Design)

**Read from:** ihouse-core real codebase
**Date:** 2026-04-03

---

## What Already Exists

### Screens (Frontend: `/ops/maintenance/page.tsx`, ~470 lines)
3-view flow: LIST → DETAIL → WORK

1. **LIST** — Open issues + linked tasks, summary strip (Open Issues / Critical / Active Tasks)
2. **DETAIL** — Issue context: category, severity, description, property, associated task, action buttons
3. **WORK** — Active execution: issue summary, work notes textarea, after photo upload, "Complete & Resolve" button

### Issue Categories (14 in backend)
pool, plumbing, electrical, ac_heating, furniture, structure, tv_electronics, bathroom, kitchen, garden_outdoor, pest, cleanliness, security, other

Each maps to a specialty: pool, plumbing, electrical, furniture, gardening, general.

### Severity / Priority System
- **Backend:** urgent → CRITICAL task (5-min ACK SLA), normal → MEDIUM task (1-hour ACK SLA)
- **Display colors:** CRITICAL (red), HIGH (amber), MEDIUM (blue), LOW (gray)
- **SLA enforcement:** CRITICAL tasks bypass ACK and start gates (always actionable immediately)

### Issue Age & SLA Display (IssueAgeChip)
- CRITICAL + SLA exceeded: "⚠ CRITICAL — SLA exceeded {elapsed}" (red, bold)
- CRITICAL + SLA active: "⚠ CRITICAL — SLA: {countdown}" (amber, live countdown)
- Other severity: "🔧 Reported {elapsed}" (gray)

### Auto-Task Creation
Problem report → auto-creates MAINTENANCE task:
- Title: "Maintenance: {category.title()}"
- Description: "Auto-created from problem report. {first 200 chars}"
- Priority: matches report severity

### Property Access
- Access code available via Worker Copilot API endpoint
- GPS navigation via Waze/Google Maps
- "📞 Call Manager" button (tel: link)

### Photo Evidence
- Before photos: from problem report (if attached by reporter)
- After photos: uploaded during WORK view via `POST /problem-reports/{id}/photos` (FormData, photo_type="after")

### Navigation (BottomNav)
- 🏠 Home → `/worker`
- 🔧 Maintenance → `/ops/maintenance`
- ✓ Tasks → `/tasks`

### MaintenanceWizard Export
Exported for Manager execution drawer embedding.

---

## What Is Missing

1. **No "Cannot Complete" workflow** — worker either completes or calls manager. No formal "blocked" state capture.
2. **No before/after photo comparison view** — before photos exist separately, not shown alongside after capture
3. **No parts/materials tracking** — no inventory or parts-used recording
4. **No estimated time or effort tracking** — no time recording per job
5. **No explicit escalation button in work view** — must exit to detail view to call manager
6. **No SLA countdown in work view** — SLA chip only on list view
7. **No access code display on work screen** — available via copilot but not prominently shown
8. **No multi-step execution flow** — single work screen with notes + photo, unlike cleaning's room-by-room

---

## What Is Unclear

1. Whether after photos are required or optional for completion (code requires notes only)
2. Whether the Worker Copilot actually delivers access codes reliably
3. Whether problem_report status transitions are validated (open → resolved only, or can go open → in_progress → resolved?)
