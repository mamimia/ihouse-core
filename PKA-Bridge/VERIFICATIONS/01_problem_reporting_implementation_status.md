# Title

Problem Reporting Backend Is Fully Built — Documentation Staleness Verified and Fixed

# Related files

- Investigation: `INVESTIGATIONS/01_problem_reporting_implementation_status.md`
- Evidence: `EVIDENCE/01_problem_reporting_fully_built.md`

# Original claim

Problem reporting backend is fully built.

# Original verdict

PROVEN

# Response from implementation layer

The implementation layer confirmed the finding and took corrective action on the stale documentation. The following was performed:

**Files read during verification:**
- `docs/core/BOOT.md`
- `PKA-Bridge/INVESTIGATIONS/01_problem_reporting_implementation_status.md`
- `PKA-Bridge/EVIDENCE/01_problem_reporting_fully_built.md`
- `docs/vision/system_vs_vision_audit.md` (full file, multiple passes)
- `docs/core/roadmap.md`
- `src/api/problem_report_router.py` (confirmed: 382 lines, full router)
- `docs/core/phase-timeline.md` (Phases 6993–7792 range read)

**Findings confirmed by implementation layer:**
- `problem_report_router.py` exists at 382 lines with 6 endpoints — confirmed.
- The router is mounted in `main.py` — confirmed.
- `system_vs_vision_audit.md` contained four stale claims about Problem Reporting:
  1. Summary table row: `Problem Reporting | ❌ | Everything | 🔴 0%`
  2. Section 8: described the feature as "חסר לגמרי" ("completely missing") and listed all sub-items as needing to be built from scratch
  3. Task gap row: `Problem Reporting (from task) | חסר | 🔴 Critical`
  4. Action item A5: `Problem Reporting ... Module חדש לגמרי` ("completely new module")

**Fixes applied:**

`docs/vision/system_vs_vision_audit.md` — four stale claims corrected:
- Summary table row changed from `❌ | Everything | 🔴 0%` to `Backend ✅ (6 endpoints, auto-task, SSE, audit, i18n) | Admin UI, photo storage pipeline | 🟡 60%`
- Section 8 rewritten to reflect the actual inventory: router exists, endpoints listed, auto-task/SSE/audit/i18n confirmed, remaining gaps identified as Admin UI and photo storage
- Task gap row updated
- Action item A5 scoped to remaining work only (frontend UI, not a new module from scratch)

`docs/core/roadmap.md` — Row F updated:
- Was: `Problem Reporting | ... | ⬜ Next`
- Now: `Problem Reporting UI _(backend built: Phases 598, 647–652)_ | ... | ⬜ Next`

The `⬜ Next` status was retained because it correctly describes the frontend UI work still outstanding. The backend-built annotation was added to prevent future misreading.

**`problem_reporting_verdict.md` was created** by the implementation layer as a verdict artifact (not found in repository — likely created and not committed, or created in a separate workspace).

# Verification reading

Post-fix state confirmed by reading `docs/vision/system_vs_vision_audit.md` line 19:
```
| Problem Reporting | Backend ✅ (6 endpoints, auto-task, SSE, audit, i18n) | Admin UI, photo storage pipeline | 🟡 60% |
```

Post-fix state confirmed by reading `docs/core/roadmap.md` line 123:
```
| F | Problem Reporting UI _(backend built: Phases 598, 647–652)_ | `.agent/architecture/mobile-maintenance.md` | ⬜ Next |
```

Both edits are live in the repository. The documentation no longer contradicts the code.

# Verification verdict

RESOLVED

# What changed

The investigation correctly identified a real documentation-code contradiction. The documentation has been corrected. The code evidence remains unchanged — `problem_report_router.py` at 382 lines with full implementation confirmed.

One clarification introduced by the implementation layer: the roadmap row F was always intended to track the **frontend UI phase** (mobile maintenance flow), not the overall feature. The `⬜ Next` status on the roadmap row is correct for that specific scope — the admin UI and mobile maintenance UI surface are genuinely not yet built. The backend being complete does not close the roadmap row; the UI work does.

# What now appears true

- The problem reporting backend is fully implemented (Phases 598, 647–652): 6 endpoints, auto-task creation, SSE alerting, audit logging, i18n scaffolding, mounted and live.
- `system_vs_vision_audit.md` previously marked this as 0% — that was a stale planning snapshot. It now correctly shows 60%.
- `roadmap.md` row F correctly reflects the outstanding work as the frontend UI layer, with an explicit annotation that the backend is built.
- The remaining genuine gaps are: admin UI dashboard for report management, photo storage pipeline (photo upload to Supabase Storage for `problem_report_photos`), RLS policy confirmation on `problem_reports`, and auto-translate wiring for `description_original_lang`.

# What is still unclear

- Whether RLS policies exist on the `problem_reports` table. The migration creates the table but RLS was not confirmed during the investigation or the verification pass. This remains an open gap.
- Whether the `problem_report_photos` endpoint stores photos to Supabase Storage or accepts caller-supplied URLs. The distinction affects whether photo upload is truly functional.
- Whether any admin-facing UI surface (beyond the maintenance worker page) exists for cross-property report management. Not confirmed in either the investigation or the verification.
- Whether the `description_original_lang` field triggers any automatic translation in the current implementation.

# Recommended next step

**Close the main documentation staleness finding.** The contradiction between documentation and code is resolved. The documentation now accurately reflects the implementation state.

**Keep open as secondary investigations:**
- RLS policy status on `problem_reports` — recommend reading the full migration file.
- Photo storage pipeline — recommend tracing what generates photo URLs before they reach `POST /problem-reports/{id}/photos`.
- Admin visibility surface — recommend searching for any admin-facing pages that call `/problem-reports`.
