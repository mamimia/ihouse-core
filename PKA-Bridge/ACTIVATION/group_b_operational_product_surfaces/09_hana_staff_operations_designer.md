# Activation Memo: Hana — Staff Operations Designer

**Phase:** 972 (Group B Activation)
**Date:** 2026-04-03
**Grounded in:** Direct reading of ihouse-core repository (src/api/invite_router.py, permissions_router.py, staff_onboarding_router.py, staff_performance_router.py, worker_availability_router.py, worker_router.py, capability_guard.py, ihouse-ui/app/(app)/admin/staff/*, supabase/migrations/phase_842*, phase_844*, phase_399*, phase_856b*)

---

## 1. What in the Current Real System Belongs to This Domain

Hana's domain is the staff lifecycle — everything around the worker, not inside their daily task flow. The real system has:

- **Intake pipeline**: `intake_requests` table with status flow (pending_review → reviewed → converted/declined). Admin review at `/admin/intake` via Next.js API route. Intake can convert to 'invite' or 'staff_onboard'.
- **Two onboarding pipelines**: (1) Admin invite via `invite_router.py` — token generation → link → acceptance → permission bootstrap. (2) Staff self-onboarding via `staff_onboarding_router.py` — admin creates invite with preselected_roles → worker submits form → admin approves.
- **Property assignment**: `staff_property_assignments` table with UNIQUE (tenant_id, user_id, property_id). Primary/Backup worker priority system. Admin manages via `/admin/staff`.
- **Task backfill (Phase 888)**: On assignment, future PENDING unassigned tasks matching worker's roles are auto-assigned. On unassignment, future PENDING tasks are cleared from that worker.
- **Performance tracking (Phase 253)**: `staff_performance_router.py` computes total_tasks_completed, completion_rate, avg_ack_minutes, sla_compliance_pct, tasks_per_day.
- **Worker availability (Phase 234)**: `worker_availability_router.py` with AVAILABLE/UNAVAILABLE/ON_LEAVE statuses per date. Manager overview endpoint.
- **Notification channels**: LINE, Telegram, WhatsApp, SMS, Email per worker. `comm_preference` JSONB on tenant_permissions, synced to notification_channels table.
- **Admin staff management**: `/admin/staff` (list with search/filter), `/admin/staff/new` (create), `/admin/staff/[userId]` (detail/edit), `/admin/staff/requests` (pending onboarding approval queue).

## 2. What Appears Built

- **Invite system (Phase 401/767)**: Complete lifecycle — `POST /admin/invites` creates token (SHA-256 hashed, never stored raw). `GET /invite/validate/{token}` for public validation. `POST /invite/accept/{token}` creates Supabase Auth user + provisions tenant_permissions with invited role. INVITABLE_ROLES excludes 'admin' (Phase 867 safety guard — cannot create admin via invite).

- **Staff self-onboarding (Phase 844)**: `staff_onboarding_requests` table with full PII capture (full_name, email, phone, emergency_contact, photo_url, comm_preference). Three-step flow: admin creates invite with preselected_roles → worker submits form at token URL → admin approves (creates tenant_permissions + worker_roles). Separate from the invite flow — self-onboarding captures more data upfront.

- **Property assignment with priority system**: `staff_property_assignments` table. Assignment determines worker lane from `worker_roles` array. Primary worker = priority 1, Backup = priority 2+. `_backfill_tasks_on_assign()` auto-assigns future PENDING tasks. `_clear_tasks_on_unassign()` clears future PENDING tasks. Phase 1031: primary-existence guard prevents backup workers from receiving tasks when a primary already covers the lane.

- **Task backfill (Phase 888)**: On assignment: queries tasks WHERE status=PENDING, assigned_to=NULL, worker_role IN matched roles, due_date ≥ today. Batch updates assigned_to. On unassignment: queries tasks WHERE status=PENDING, assigned_to=user_id, due_date ≥ today. Batch clears assigned_to. Returns counts for admin visibility.

- **Performance metrics (Phase 253)**: Computes from tasks table: total_tasks_completed, total_tasks_assigned, completion_rate (%), avg_ack_minutes, sla_compliance_pct (% within SLA), tasks_per_day, preferred_channel. Two endpoints: aggregate (all workers) and individual drill-down. Both require `require_capability("staffing")`.

- **Worker availability (Phase 234)**: Upsert on (tenant_id, worker_id, date). Statuses: AVAILABLE, UNAVAILABLE, ON_LEAVE. Time windows optional (start_time, end_time). Admin overview: all workers grouped by status per date. Max 90-day query window.

- **Admin staff management UI**: `/admin/staff/page.tsx` — staff list with summary cards (Total, Admin, Manager, Worker, Owner counts, Pending Approval). Search by name/email, filter by role. `/admin/staff/[userId]/page.tsx` — detail page with profile editing, role management, property assignment, deactivation toggle. `/admin/staff/requests/page.tsx` — pending onboarding approval queue.

- **Notification channel management**: Worker endpoints for channel CRUD. `_sync_channels()` function auto-syncs comm_preference to notification_channels table on profile update. LINE webhook router for task acknowledgment callback.

- **Staffing capability guard**: `require_capability("staffing")` protects: property assignment (POST/DELETE), performance endpoints, worker management. Managers need explicit staffing delegation from admin.

## 3. What Appears Partial

- **Deactivation flow**: Setting `is_active=false` via PATCH works, but **no automatic task reassignment** occurs. Admin must manually remove property assignments (which triggers task clearing) before deactivating. If admin deactivates without removing assignments, the worker's tasks remain assigned to a deactivated user — tasks stuck.
- **Worker_roles assignment during invite onboarding**: The basic invite flow (`invite_router.py`) provisions the canonical role but the `worker_roles` array population during invite acceptance was not fully traced. Self-onboarding (Phase 844) clearly captures worker_roles from the form. Whether the invite path also sets worker_roles or leaves them empty needs verification.
- **Legacy role normalization**: The staff detail page (line 74-79) normalizes legacy roles: `cleaner → role=worker, worker_roles=[cleaner]`. This suggests historical data may have inconsistent role formats that the UI must handle. The normalization is client-side.

## 4. What Appears Missing

- **No automatic task reassignment on deactivation**: When a worker is deactivated, their PENDING tasks are not automatically reassigned. Unlike unassignment (which clears tasks), deactivation is a status change that doesn't trigger the backfill/clear logic. This is a gap — a deactivated worker's tasks go into limbo.
- **No shift scheduling**: Worker availability is date-level (AVAILABLE/UNAVAILABLE per day). No shift system, no time-block scheduling, no rotation calendar. For operations with morning/evening shifts or rotating weekday/weekend coverage, this is insufficient.
- **No probationary period or training tracking**: The onboarding pipeline creates a worker with full permissions immediately on approval. No staged onboarding (e.g., "observe-only for first week") or training completion gates.
- **No worker-initiated role change requests**: If a cleaner wants to also do maintenance, there's no self-service path. Admin must manually add the role.
- **No offboarding checklist**: Deactivation is a single toggle. No structured offboarding: revoke access tokens, clear notification channels, archive assignments, generate final performance report.

## 5. What Appears Risky

- **Deactivate-without-unassign gap**: The most operationally dangerous gap. Admin deactivates a worker → worker can't act on tasks → tasks remain assigned → SLA breaches accumulate → no automatic escalation. The system doesn't warn the admin about active assignments when deactivating.
- **Primary/Backup priority race**: If two workers are assigned to the same property for the same lane at the same time, both get priority computed independently. The priority calculation is MAX(existing priorities) + 1, which could produce duplicates under concurrent requests.
- **Performance metrics query scalability**: `staff_performance_router.py` appears to compute metrics by querying the full tasks table. For tenants with thousands of historical tasks, this could become slow without proper indexes or materialized views.

## 6. What Appears Correct and Worth Preserving

- **Token security**: Invite tokens are SHA-256 hashed before storage. Raw token is returned once at creation and never stored. Validation uses hash comparison. This is correct security practice.
- **INVITABLE_ROLES guard**: Cannot create admin via invite. This prevents privilege escalation through the invitation system.
- **Primary/Backup assignment model**: Simple but effective — Primary workers (priority 1) get tasks first, Backups fill gaps. The Phase 1031 guard prevents Backups from receiving tasks when a Primary exists. This handles the common case well.
- **Task backfill on assignment**: Automatic — admin assigns worker, worker immediately gets matching tasks. No manual task assignment needed. Clean integration between HR and task systems.
- **Staffing capability delegation**: Performance data and assignment management are gated by `require_capability("staffing")`. Not all managers can manage staff — only those explicitly delegated.
- **Two onboarding paths**: Invite (lightweight, role-only) and self-onboarding (comprehensive, with PII capture). Appropriate for different contexts — quick staff addition vs. formal hiring.

## 7. What This Role Would Prioritize Next

1. **Fix deactivation flow**: On deactivation, auto-remove property assignments (triggering task clearing) or at minimum warn admin about active assignments before allowing deactivation.
2. **Verify invite → worker_roles population**: Confirm the basic invite path sets worker_roles correctly. If it doesn't, invited workers may have canonical role but empty worker_roles (no sub-role routing, no task matching).
3. **Add deactivation warning**: Before setting `is_active=false`, show the admin: "This worker has N active property assignments and M pending tasks. Deactivating without removing assignments will leave tasks unassigned."
4. **Define offboarding checklist**: Structured deactivation: revoke tokens → clear notification channels → remove assignments (triggers task clear) → archive → generate report.

## 8. Dependencies on Other Roles

- **Daniel**: Hana needs Daniel to confirm that deactivation correctly blocks auth at middleware level (not just UI). If `is_active=false` doesn't block JWT validation, a deactivated worker could still access the system.
- **Marco**: Hana manages how workers get assigned; Marco owns what they see. The "new worker, zero tasks" empty state and the multi-role routing question are shared boundaries.
- **Ravi (Group A)**: Task backfill logic sits at the boundary of Hana's assignment system and Ravi's service flow. The PENDING-only scope of backfill means ACKNOWLEDGED+ tasks are never redistributed.
- **Sonia**: The admin staff management surface (`/admin/staff`) is within Sonia's surface differentiation scope. Hana defines what features it needs; Sonia validates it fits the admin surface's structural purpose.

## 9. What the Owner Most Urgently Needs to Understand

The staff lifecycle system is more complete than expected — two onboarding paths, property assignment with automatic task backfill, performance metrics, availability tracking, and capability-gated management. The primary/backup priority system is a meaningful operational feature.

One critical operational gap needs immediate attention:

**Deactivating a worker does not automatically handle their tasks.** If an admin deactivates a worker who has assigned tasks, those tasks remain assigned to a user who can no longer act on them. No warning is shown, no automatic reassignment occurs, and SLA breaches will accumulate silently. This is the #1 staff operations risk — a single admin action (deactivation) can cascade into multiple operational failures without any system-level safeguard.
