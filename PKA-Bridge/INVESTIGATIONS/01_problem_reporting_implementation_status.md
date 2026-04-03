# Title

Problem Reporting Backend Is Fully Built — But Documentation Claims It Is Not

# Why this matters

If a product decision is made based on the documented claim that problem reporting is "0% implemented," the team will build a system that already exists. The existing router (Phases 598–652) will be orphaned, overwritten, or duplicated. Real behavioral work — auto-task creation, SSE alerting, audit logging, i18n scaffolding — will be re-implemented from scratch at significant cost and likely with regressions. Conversely, if the backend is treated as complete without further verification, it will be shipped without knowing whether RLS policies protect the data, whether there is any admin-facing UI for managing reports, or whether photo uploads are actually wired to storage.

# Original claim

Problem reporting backend is fully built.

# Final verdict

PROVEN

# Executive summary

The problem reporting backend is real, complete, and mounted. A full CRUD router exists at `src/api/problem_report_router.py`, is mounted in `src/main.py`, is backed by a migrated database table, and has four operational behaviors beyond basic CRUD: automatic maintenance task creation, SSE alerting for urgent reports, audit logging on status change, and i18n label scaffolding. The maintenance worker frontend at `/ops/maintenance` makes live API calls to these endpoints. The documentation claim of "0% implemented" is wrong and predates the work by multiple phase cycles.

# Exact repository evidence

- `src/api/problem_report_router.py` — the router (Phases 598, 647–652)
- `src/main.py` lines 595–596 — router import and mount
- `supabase/migrations/20260314201500_phase586_605_foundation.sql` — `problem_reports` and `problem_report_photos` table definitions
- `src/tasks/task_model.py` — `TaskKind.MAINTENANCE`, `TaskPriority.CRITICAL`
- `src/channels/sse_broker.py` — `broker.publish_alert()` called by the router
- `src/i18n/problem_report_labels.py` — i18n labels file
- `ihouse-ui/app/(app)/ops/maintenance/page.tsx` — frontend calling `/problem-reports` and `/problem-reports/{id}/status`
- `docs/vision/system_vs_vision_audit.md` — source of the "0%" claim

# Detailed evidence

**The router exists and is mounted.**

`src/main.py` contains:
```python
from api.problem_report_router import router as problem_report_router  # Phase 598
app.include_router(problem_report_router)
```
This is a direct import and mount — not a conditional import, not a feature flag. The router is active in the application.

**The router has 6 endpoints:**
```
POST  /problem-reports               — create report
GET   /problem-reports               — list with filters (property_id, status, priority)
GET   /problem-reports/{id}          — single report
PATCH /problem-reports/{id}          — update status, assign, resolve
POST  /problem-reports/{id}/photos   — add photo URL
GET   /problem-reports/{id}/photos   — list photos
```

**14 valid categories are defined in code:**
pool, plumbing, electrical, ac_heating, furniture, structure, tv_electronics, bathroom, kitchen, garden_outdoor, pest, cleanliness, security, other.

**4 valid statuses are defined in code:**
open, in_progress, resolved, dismissed.

**Auto-task creation (Phase 648):**
On `POST /problem-reports`, after inserting the row, `_auto_create_maintenance_task()` is called. It uses `Task.build()` from `task_model.py`, inserts to the `tasks` table, and links the `task_id` back to the report via `problem_reports.maintenance_task_id`. Priority mapping is defined: `urgent → CRITICAL`, `normal → MEDIUM`. This means creating a problem report automatically creates a trackable maintenance task in the task system — a non-trivial integration.

**SSE alerting (Phase 651):**
```python
if priority == "urgent":
    _emit_urgent_sse_alert()  # calls sse_broker.broker.publish_alert(event_type=PROBLEM_URGENT)
```
Real-time escalation for urgent reports is wired to the live SSE broker.

**Audit event (Phase 650):**
The PATCH endpoint captures old status before updating, then calls `write_audit_event()` with `action="PROBLEM_REPORT_STATUS_CHANGED"`. Status changes are audit-logged.

**Category-to-specialty mapping (Phase 652):**
A `_CATEGORY_SPECIALTY` dict maps report categories to maintenance specialties (e.g., `"pool" → "pool"`, `"bathroom" → "plumbing"`, `"ac_heating" → "hvac"`). This is used to route the auto-created task to the correct specialist type.

**Database tables (migration confirmed):**
```sql
CREATE TABLE IF NOT EXISTS problem_reports (...)
CREATE INDEX IF NOT EXISTS idx_problem_reports_property ON problem_reports(tenant_id, property_id);
CREATE INDEX IF NOT EXISTS idx_problem_reports_status ON problem_reports(tenant_id, status);
```
The `problem_report_photos` table references `problem_reports(id)` via foreign key.

**Frontend integration confirmed:**
`ihouse-ui/app/(app)/ops/maintenance/page.tsx` contains live `fetch()` or `apiFetch()` calls to `/problem-reports` (list) and `/problem-reports/{id}/status` (status update). The maintenance worker UI is wired to this backend.

**Documentation claim:**
`docs/vision/system_vs_vision_audit.md` marks problem reporting as "0% implemented." This document was written before Phases 598–652 were completed. It has not been updated.

# Contradictions

- Documentation says 0% implemented. Code shows the router exists, is mounted, has 6 endpoints, a migrated DB table, and 4 operational behaviors beyond CRUD.
- The i18n labels file (`src/i18n/problem_report_labels.py`) exists — meaning multilingual reporting was scaffolded. This is inconsistent with a feature at 0%.
- The frontend maintenance page makes live API calls to these endpoints. A live frontend call to an endpoint that "doesn't exist" would produce consistent 404 or 500 errors. The fact that the frontend is wired without error handling for "endpoint missing" implies the endpoint was known to exist.

# What is confirmed

- The `problem_report_router.py` file exists with 6 endpoints.
- The router is imported and mounted in `main.py`.
- The `problem_reports` table and `problem_report_photos` table exist in a Supabase migration.
- Auto-task creation is wired (Phase 648): creates a MAINTENANCE task, links `maintenance_task_id`.
- SSE alerting is wired for urgent priority reports (Phase 651).
- Audit logging is wired for status changes (Phase 650).
- Category-to-specialty mapping exists (Phase 652).
- The maintenance worker frontend makes API calls to these endpoints.
- The i18n labels file exists.

# What is not confirmed

- Whether the `problem_reports` table has RLS policies. The migration creates the table and its indexes but RLS was not confirmed in the portion of the migration file read.
- Whether photo URLs in `problem_report_photos` are pre-signed Supabase Storage URLs or caller-supplied raw URLs. The API accepts a `photo_url` string — what generates that URL is not confirmed.
- Whether any admin-facing UI (beyond the maintenance worker page) displays or manages problem reports. The admin side was not confirmed as reading these endpoints.
- Whether `description_original_lang` triggers automatic translation. The field exists but the translation pipeline wiring was not traced.
- Whether the auto-created maintenance task correctly inherits tenant scoping — specifically, whether `Task.build()` correctly populates `tenant_id` when called from the problem report context.

# Practical interpretation

Problem reporting is a live backend feature, not a backlog item. Workers on the `/ops/maintenance` page can submit reports today, those reports create maintenance tasks automatically, and urgent reports fire SSE alerts in real time. Any roadmap that treats this as unbuilt is operating on stale information.

The feature is not complete in a product sense — there is no confirmed admin UI to view or manage all reports across properties, there is no confirmed photo storage pipeline, and RLS is unverified. But the core backend is functional.

# Risk if misunderstood

**If treated as unbuilt:** Duplicate implementation. Phase labels 598–652 orphaned. Existing auto-task linkage (`problem_reports.maintenance_task_id`) creates DB conflicts when a new table schema is introduced.

**If treated as complete:** RLS may be missing, meaning any authenticated user in the tenant can read all problem reports. Photo storage may be unimplemented, meaning photos referenced in the UI are not persisted. Admin visibility gap means managers have no dashboard surface for cross-property report review.

# Recommended follow-up check

1. Read the full `supabase/migrations/20260314201500_phase586_605_foundation.sql` migration to confirm whether `problem_reports` has RLS policies, and whether those policies correctly scope by `tenant_id`.
2. Search for any admin-side page that calls `/problem-reports` to determine whether there is an admin visibility surface.
3. Trace `photo_url` — search for Supabase Storage upload calls in the frontend related to problem report photo submission.
4. Verify `Task.build()` call in `_auto_create_maintenance_task()` includes `tenant_id` correctly.
