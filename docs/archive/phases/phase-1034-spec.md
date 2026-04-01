# Phase 1034 — OM-1: Manager Task Intervention Model

**Status:** Open
**Prerequisite:** Phase 1033 — Canonical Task Timing Hardening
**Date opened:** 2026-04-01
**Branch:** `checkpoint/supabase-single-write-20260305-1747`

---

## Goal

Build the manager-level task intervention model approved in Phase 1033. The manager layer
(Monitor / Takeover / Reassign / Note) is strictly separate from the worker layer
(Acknowledge / Start / Complete). `ManagerTaskCard` provides a drill-down intervention
component — it does not replace Hub / Stream / Alerts / Team as primary OM surfaces.

The stream-first, alert-first OM design established in Phase 1033 remains intact.

---

## Non-Negotiable Constraints (locked in Phase 1033)

1. **Takeover bypass via dedicated route ONLY** — `POST /tasks/{id}/takeover-start` is the sole timing-bypass path. The existing `/acknowledge` and `/start` endpoints must never be globally bypassed by role.
2. **Reassign scoping:** Tier 1 = property-scoped only. Tier 2 = explicit "show all eligible" opt-in. No silent tenant-wide reassignment.
3. **Notes are persistent and attributable** — every note write includes `author_id`, `author_name`, `created_at`, `source`. Notes are never ephemeral.
4. **`ManagerTaskCard` is drill-down only** — Hub / Stream / Alerts / Team remain primary OM surfaces. `ManagerTaskCard` is the intervention layer reached from a Stream or Alerts expand action.

**Not in this phase:** Force Advance.

---

## Backend Deliverables

### 1. `POST /worker/tasks/{id}/takeover-start`

New endpoint. Manager/admin only. Bypasses timing gates.

**Semantics:**
- Walks task from current status → `ACKNOWLEDGED` → `IN_PROGRESS` atomically
- Works on `PENDING`, `ACKNOWLEDGED`, or `IN_PROGRESS` tasks
- Sets `assigned_to` = caller (manager/admin user_id)
- Records audit event: `TASK_TAKEOVER_STARTED`
- Manager scope: property-scoped (task's `property_id` must be in caller's assigned properties)
- Admin scope: global (no property scope check)
- Returns updated task row

**Error tokens:**
- `TASK_NOT_FOUND`
- `TASK_ALREADY_COMPLETE` (if status = COMPLETED or CANCELED)
- `MANAGER_NOT_ASSIGNED_TO_PROPERTY` (permission gate for manager role)

### 2. `PATCH /worker/tasks/{id}/reassign`

Existing endpoint in `task_takeover_router.py` — verify and harden for OM-1 use.

**Semantics:**
- Updates `assigned_to` to new worker_id (or null = open pool)
- Works on any in-flight status (PENDING, ACKNOWLEDGED, IN_PROGRESS, MANAGER_EXECUTING)
- Resets status to `PENDING`
- Records audit event: `TASK_REASSIGNED`
- Tier 1: validates new assignee is a `staff_property_assignment` for the task's property in the correct lane
- Tier 2: `?scope=tenant` query param; only valid when caller explicitly sets it; validates new assignee is in the tenancy

### 3. `PATCH /worker/tasks/{id}/notes`

Existing endpoint in `task_takeover_router.py` — verify and harden for OM-1 use.

**Semantics:**
- Appends a note object: `{text, author_id, author_name, created_at, source}`
- `tasks.notes` is a `jsonb` array (append-only — no note is ever deleted or overwritten)
- `source` = `"manager"` for this flow
- Returns updated `notes[]` array

---

## Frontend Deliverables

### 4. `ManagerTaskCard.tsx`

New component in `ihouse-ui/components/`.

**Layout:**
- Task header: property name, kind badge, status badge
- Timing strip (read-only): shows `ack_allowed_at` and `start_allowed_at` in human-readable form; current status relative to windows. Purely informational — no action buttons tied to worker gates.
- Worker info row: current `assigned_to` name, role, and whether ack/start windows are open
- Action row: `[🔄 Takeover]` `[👤 Reassign]` `[✎ Note]`
- Notes section (if notes present): chronological list of attributed notes

**Rules:**
- No Acknowledge button
- No Start button
- No Complete button
- No Force Advance button (explicitly excluded this phase)
- Read-only access to worker timing strip is for operational visibility only

### 5. Reassign Panel

Inline sheet/drawer triggered from `[👤 Reassign]` on `ManagerTaskCard`.

**Tier 1 (default):**
- Fetches workers assigned to the task's property in the matching lane
- Shows name, role, current task load indicator
- Confirm → calls `PATCH /worker/tasks/{id}/reassign`

**Tier 2 (explicit opt-in):**
- "Show all eligible workers" toggle — sends `?scope=tenant`
- Only shown when Tier 1 returns no eligible options, or manager explicitly expands

### 6. Note Inline Input

Inline text input triggered from `[✎ Note]` on `ManagerTaskCard`.

- Single-line text input with character limit
- Confirm button: calls `PATCH /worker/tasks/{id}/notes`
- On success: note appended to notes section in-place
- Cancel: dismisses without write

### 7. Stream Page Integration

On `/manager/stream` (and `/manager/streams`):
- Task event items: clicking/expanding → opens `ManagerTaskCard` in a slide-out or in-page drawer
- `ManagerTaskCard` renders in drill-down mode (full panel)

### 8. ManagerExecutionDrawer Update

Existing `ManagerExecutionDrawer` (if present from Phase 1022):
- Replace any `forceCompleteTask` calls with `POST /tasks/{id}/takeover-start`
- Ensure the takeover state machine (PENDING→ACK→IN_PROGRESS) completes before task wizard is shown

---

## Implementation Order

```
Step 1: Backend — takeover-start route (new, most complex)
Step 2: Backend — verify/harden reassign (Tier 1 property scope)
Step 3: Backend — verify/harden notes (attributable append)
Step 4: Frontend — ManagerTaskCard.tsx (core component)
Step 5: Frontend — Reassign panel (Tier 1)
Step 6: Frontend — Note inline input
Step 7: Frontend — Stream page integration
Step 8: Frontend — ManagerExecutionDrawer wiring
Step 9: Backend — Git push → Railway auto-deploy
Step 10: Frontend — Vercel deploy (npx vercel --prod --yes)
Step 11: Staging proof pass
Step 12: Docs closure
```

---

## Files Expected

### Backend (new/modified)
- `src/api/task_takeover_router.py` — `takeover-start` endpoint added; reassign + notes hardened

### Frontend (new/modified)
- `ihouse-ui/components/ManagerTaskCard.tsx` — NEW
- `ihouse-ui/components/ManagerTaskCard.module.css` — NEW (or inline styles)
- `ihouse-ui/app/(app)/manager/stream/page.tsx` — MODIFIED (expand → ManagerTaskCard)
- `ihouse-ui/components/ManagerExecutionDrawer.tsx` — MODIFIED (if exists)

---

## Staging Proof Targets

| Proof | Method |
|-------|--------|
| `POST /tasks/{id}/takeover-start` — timing gate bypassed | HTTP request from manager JWT; task in PENDING with `start_is_open=false`; verify → IN_PROGRESS |
| `PATCH /tasks/{id}/reassign` — Tier 1 property scope | Reassign task on KPG-500 to valid property worker |
| `PATCH /tasks/{id}/notes` — attributable note | Append note; verify `author_id` + `created_at` in DB |
| `ManagerTaskCard` — timing strip visible, no worker buttons | Screenshot |
| Stream page → `ManagerTaskCard` expand | Screenshot |

---

## Open Items After This Phase (planned)

- Tier 2 (tenant-wide) reassign scope
- Promotion notice acknowledgement PATCH (worker dismiss → `acknowledged: true`) — deferred Phase 1032
- Maintenance timing gate staging proof — deferred Phase 1033
- Force Advance (separate proposal, not in OM-1)
