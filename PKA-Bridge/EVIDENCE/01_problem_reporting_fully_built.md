# Claim

Problem reporting backend is fully built.

# Verdict

PROVEN

# Why this verdict

The router exists, is mounted in the application, has a complete set of CRUD endpoints, and the database table is provisioned in a migration. The behavior extends beyond basic CRUD: auto-task creation, SSE alerting, audit events, and i18n fields are all wired in the same router.

# Direct repository evidence

- `src/api/problem_report_router.py` — the router itself
- `src/main.py` line 595–596 — router imported and mounted
- `supabase/migrations/20260314201500_phase586_605_foundation.sql` — `problem_reports` table and `problem_report_photos` table defined
- `src/tasks/task_model.py` — `TaskKind.MAINTENANCE` and `TaskPriority.CRITICAL` used by auto-task logic
- `src/channels/sse_broker.py` — called by the router on urgent problem creation
- `src/i18n/problem_report_labels.py` — i18n support file exists
- `ihouse-ui/app/(app)/ops/maintenance/page.tsx` — frontend calls `/problem-reports` and `/problem-reports/{id}/status`

# Evidence details

**Router endpoints (confirmed by reading `problem_report_router.py`):**

```
POST  /problem-reports           — create report (property_id, reported_by, category, description, priority)
GET   /problem-reports           — list with filters (property_id, status, priority)
GET   /problem-reports/{id}      — single report
PATCH /problem-reports/{id}      — update status, assign, resolve
POST  /problem-reports/{id}/photos — add photo URL
GET   /problem-reports/{id}/photos — list photos
```

**14 valid categories defined in code:**
pool, plumbing, electrical, ac_heating, furniture, structure, tv_electronics, bathroom, kitchen, garden_outdoor, pest, cleanliness, security, other.

**4 valid statuses:** open, in_progress, resolved, dismissed.

**Phase 648 — auto-task creation is wired:**
On `POST /problem-reports`, after inserting the row, `_auto_create_maintenance_task()` is called. It creates a MAINTENANCE task using `Task.build()` from `task_model.py`, inserts it to the `tasks` table, and links the task_id back to the report via `problem_reports.maintenance_task_id`. Priority mapping: `urgent → CRITICAL`, `normal → MEDIUM`.

**Phase 651 — SSE alert:**
If `priority == "urgent"`, `_emit_urgent_sse_alert()` calls `sse_broker.broker.publish_alert()` with event_type `PROBLEM_URGENT`.

**Phase 650 — audit event on status change:**
PATCH endpoint captures old status before updating, then calls `write_audit_event()` with `action="PROBLEM_REPORT_STATUS_CHANGED"`.

**Phase 652 — category→specialty mapping:**
Dict `_CATEGORY_SPECIALTY` maps report categories to maintenance specialties (e.g., `"pool": "pool"`, `"bathroom": "plumbing"`).

**Database table (from migration `20260314201500`):**
```sql
CREATE TABLE IF NOT EXISTS problem_reports (...)
CREATE INDEX IF NOT EXISTS idx_problem_reports_property ON problem_reports(tenant_id, property_id);
CREATE INDEX IF NOT EXISTS idx_problem_reports_status ON problem_reports(tenant_id, status);
```
Photos table references `problem_reports(id)` via foreign key.

**Main.py mount:**
```python
from api.problem_report_router import router as problem_report_router  # Phase 598
app.include_router(problem_report_router)
```

# Conflicts or contradictions

The documentation (seen in an earlier pass of `docs/vision/system_vs_vision_audit.md`) marks problem reporting as "0% implemented." This is directly contradicted by the code. The router was built across Phases 598, 647–652, which predate the current branch. The documentation appears to have been written before this work was completed and not updated.

The i18n labels file (`src/i18n/problem_report_labels.py`) exists, confirming multilingual reporting was intended and partially scaffolded. The frontend maintenance page (`/ops/maintenance`) makes live API calls to these endpoints. Both signals support implementation being real.

# What is still missing

- Whether the `problem_reports` Supabase table has RLS policies defined (the migration file creates the table but I did not read the full migration to confirm RLS).
- Whether photo uploads go through a real Supabase Storage path, or whether `photo_url` is expected to be a pre-uploaded URL that the caller supplies.
- Whether any admin UI surface (beyond the maintenance worker page) displays or manages problem reports — the admin side was not confirmed read.
- Whether `description_original_lang` triggers any automatic translation — the field exists but translation wiring was not traced.

# Risk if misunderstood

If a product decision is made to build problem reporting from scratch because documentation says 0%, significant duplicate work will be created and the existing router (Phases 598–652) will be orphaned or overwritten. Conversely, if the existing backend is assumed complete without checking RLS and UI coverage, problem reports may exist in the database with no access controls or no admin visibility.
