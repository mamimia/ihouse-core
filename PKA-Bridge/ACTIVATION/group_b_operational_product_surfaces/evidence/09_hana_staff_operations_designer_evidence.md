# Evidence File: Hana — Staff Operations Designer

**Paired memo:** `09_hana_staff_operations_designer.md`
**Evidence status:** Staff lifecycle well-evidenced; deactivation gap confirmed; performance system verified

---

## Claim 1: Invite system is complete with security guards

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/invite_router.py`: POST `/admin/invites` (create), GET `/invite/validate/{token}` (public), POST `/invite/accept/{token}` (accept + user creation)
- Lines 245-300: Permission bootstrapping — creates `tenant_permissions` with role from invite metadata
- Token security: SHA-256 hash stored, raw token returned once at creation
- INVITABLE_ROLES excludes 'admin' (Phase 867)

**What was observed:** Complete invite lifecycle: create → validate → accept → provision. Token hashing prevents raw token exposure even if DB is compromised. INVITABLE_ROLES guard prevents admin creation via invite — a critical privilege escalation prevention. Accept flow creates Supabase Auth user + provisions tenant_permissions in a single transaction.

**Confidence:** HIGH

**Uncertainty:** Whether the invite accept endpoint handles race conditions (two simultaneous accepts of the same token). The `used_at` field should prevent double-acceptance, but the exact check ordering was not traced.

---

## Claim 2: Two onboarding pipelines exist (invite + self-onboarding)

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/invite_router.py`: Lightweight invite flow — email + role + token
- File: `src/api/staff_onboarding_router.py`: Comprehensive self-onboarding — admin creates with preselected_roles → worker submits form (full_name, email, phone, emergency_contact, photo_url, comm_preference, selected worker_roles) → admin approves
- Migration: `supabase/migrations/20260319130000_phase844_staff_onboard.sql`: `staff_onboarding_requests` table
- Migration: `supabase/migrations/20260313190000_phase399_access_tokens.sql`: `access_tokens` table with token_type 'invite', 'onboard', 'staff_onboard'

**What was observed:** Two distinct paths:
1. **Invite** (Phase 401/767): Admin creates invite → worker visits link → accepts → provisioned. Captures: password + full_name only. Fast, lightweight.
2. **Self-onboarding** (Phase 844): Admin creates invite with preselected_roles → worker submits comprehensive form → admin reviews + approves. Captures: full PII including emergency contact, photo, comm preference, selected worker_roles.

The two paths coexist — different admin workflows for different contexts (quick addition vs. formal hiring).

**Confidence:** HIGH

**Uncertainty:** Whether both paths are actively used in production or if one has become the de facto standard.

---

## Claim 3: Property assignment with Primary/Backup priority and task backfill

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/permissions_router.py`, lines 1203-1340: Assignment endpoint with lane detection, priority calculation
- Lines 920-1068: `_backfill_tasks_on_assign()` — queries PENDING/unassigned/matching tasks → batch assigns
- Lines 1071-1132: `_clear_tasks_on_unassign()` — clears PENDING tasks for unassigned worker
- Migration: `supabase/migrations/20260318120000_phase842_staff_schema.sql`: `staff_property_assignments` with UNIQUE (tenant_id, user_id, property_id)
- Phase 1031: Primary-existence guard — backup workers skip backfill when primary exists

**What was observed:** Assignment determines worker lane from `worker_roles` via `_ROLE_TO_TASK_ROLES` mapping (cleaner → CLEANER, checkin → CHECKIN+PROPERTY_MANAGER, etc.). Primary = priority 1, Backup = MAX(existing) + 1. On assign: future PENDING tasks where assigned_to IS NULL and worker_role matches are batch-updated. On unassign: future PENDING tasks for that worker are cleared. Returns counts for admin visibility.

**Confidence:** HIGH

**Uncertainty:** The `_ROLE_TO_TASK_ROLES` mapping includes multi-role expansions (checkin → CHECKIN + PROPERTY_MANAGER, checkout → CHECKOUT + INSPECTOR). Whether these expanded roles are used consistently in the task system was not cross-verified.

---

## Claim 4: Deactivation does NOT automatically handle tasks

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/permissions_router.py`, line 808-852: PATCH endpoint for profile update
- Line 752: `is_active` is in `_PATCHABLE_PROFILE_FIELDS`
- Update: `tenant_permissions.update({is_active: false})`

**What was observed:** Deactivation is a simple field update — no downstream task logic triggered. Unlike unassignment (which calls `_clear_tasks_on_unassign()`), deactivation does not call any task clearing function. Admin must explicitly remove property assignments (separate action) to trigger task clearing.

The gap is:
1. Admin sets `is_active=false` → worker can't log in
2. Worker's tasks remain assigned → tasks stuck (no one can complete them)
3. No warning shown to admin about active assignments
4. SLA breaches accumulate silently

**Confidence:** HIGH

**Uncertainty:** None. The absence of task-handling logic in the deactivation path is confirmed.

---

## Claim 5: Performance metrics system exists with staffing capability gate

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/staff_performance_router.py`, line 152: `GET /admin/staff/performance` with `require_capability("staffing")`
- Line 230: `GET /admin/staff/performance/{worker_id}` with `require_capability("staffing")`
- Metrics: total_tasks_completed, total_tasks_assigned, completion_rate (%), avg_ack_minutes, sla_compliance_pct, tasks_per_day, preferred_channel

**What was observed:** Performance system computes 7 metrics from the tasks table. Both aggregate and individual endpoints require `require_capability("staffing")` — managers need explicit delegation. Metrics are derived at query time from tasks table fields (worker_id, state, created_at, acknowledged_at, completed_at).

**Confidence:** HIGH

**Uncertainty:** Query performance at scale — metrics are computed at query time, not materialized. For tenants with large task volumes, this could become slow. Indexes on the tasks table were not verified.

---

## Claim 6: Worker availability system exists

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/worker_availability_router.py`: POST (set availability), GET (own slots), GET overview (admin/manager)
- Statuses: AVAILABLE, UNAVAILABLE, ON_LEAVE
- Upsert on (tenant_id, worker_id, date)
- Max 90-day query window
- Migration: `supabase/migrations/20260311150000_phase234_worker_availability.sql`

**What was observed:** Date-level availability tracking. Workers set their own availability; admin/manager see an overview. Simple but functional for basic scheduling. No time-block/shift support — a worker is available or not for the entire day.

**Confidence:** HIGH

**Uncertainty:** Whether the availability data is actually consumed by the task assignment system (e.g., does task backfill check if the worker is available on the task's due date?). This integration was not traced.

**Follow-up check:** Verify whether `_backfill_tasks_on_assign()` or the task creation logic checks `worker_availability` before assigning tasks to a worker marked UNAVAILABLE.

---

## Claim 7: Notification channel management with 5 channels

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/permissions_router.py`, lines 112-130: `_sync_channels()` auto-syncs comm_preference to notification_channels
- File: `src/api/worker_router.py`: GET/POST/DELETE for worker notification channel management
- File: `src/api/line_webhook_router.py`: LINE task acknowledgment callback
- Channels: LINE, Telegram, WhatsApp, SMS, Email (stored in `comm_preference` JSONB)

**What was observed:** Workers configure their preferred channels via `comm_preference` JSONB on tenant_permissions. Profile updates auto-sync to the notification_channels table via `_sync_channels()`. LINE has a dedicated webhook for task acknowledgment (worker can acknowledge tasks via LINE). Other channels (Telegram, WhatsApp, SMS, Email) are configured but their webhook/dispatch mechanisms were not fully traced.

**Confidence:** HIGH on configuration. MEDIUM on actual dispatch for all channels.

**Uncertainty:** Whether all 5 channels actually dispatch notifications or if some are configured but not yet active. The notification_dispatcher.py was referenced but not fully read.

---

## Claim 8: Admin staff management UI has list, detail, new, and requests pages

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- Files: `ihouse-ui/app/(app)/admin/staff/page.tsx` (list), `admin/staff/[userId]/page.tsx` (detail), `admin/staff/new/page.tsx` (create), `admin/staff/requests/page.tsx` (pending approvals)
- Staff list: summary cards (Total, Admin, Manager, Worker, Owner, Pending), search by name/email, role filter
- Detail page: profile editing, role management, property assignment display, deactivation toggle (line 706: PATCH with is_active)

**What was observed:** Full CRUD surface for staff management. The list page shows aggregate counts by role type. Detail page allows profile editing, role assignment, and deactivation. Requests page handles pending onboarding approvals (self-onboarding flow). Legacy role normalization (line 74-79) handles historical data inconsistencies client-side.

**Confidence:** HIGH

**Uncertainty:** Whether the property assignment UI (within the detail page) provides a good admin experience or if it's a basic list. The assignment management UX was not deeply evaluated.

---

## Claim 9: Staffing capability properly gates management actions

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/capability_guard.py`: `require_capability("staffing")` dependency
- File: `src/api/worker_router.py`, line 969: POST `/worker/assignments` requires staffing
- File: `src/api/worker_router.py`, line 1018: DELETE `/worker/assignments/{assignment_id}` requires staffing
- File: `src/api/staff_performance_router.py`, lines 152, 230: Both performance endpoints require staffing
- Guard logic: admin → always allowed; manager → check permissions JSONB; ops → denied; other → denied

**What was observed:** Staffing capability is correctly enforced. Managers need explicit delegation from admin. The capability_guard checks the `permissions` JSONB in tenant_permissions for the "staffing" key. Admin bypasses the check entirely (all capabilities implied). The `_ROLE_CAPABILITY_ALLOWLIST` restricts which roles CAN receive which capabilities — ops role only gets "bookings", not "staffing."

**Confidence:** HIGH

**Uncertainty:** None on the guard mechanism. Whether all staffing-related endpoints consistently use this guard was not exhaustively verified (there may be staff management endpoints without the guard).

---

## Summary of Evidence

| Memo Claim | Evidence Status | Confidence |
|---|---|---|
| Invite system complete | DIRECTLY PROVEN | HIGH |
| Two onboarding pipelines | DIRECTLY PROVEN | HIGH |
| Property assignment with backfill | DIRECTLY PROVEN | HIGH |
| Deactivation doesn't handle tasks | DIRECTLY PROVEN (gap confirmed) | HIGH |
| Performance metrics exist | DIRECTLY PROVEN | HIGH |
| Worker availability system | DIRECTLY PROVEN | HIGH |
| Notification channels | PROVEN (config), PARTIAL (dispatch) | HIGH / MEDIUM |
| Admin staff UI | DIRECTLY PROVEN | HIGH |
| Staffing capability gate | DIRECTLY PROVEN | HIGH |
