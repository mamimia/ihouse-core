# Activation Memo: Claudia — Property Readiness Standards Architect

**Phase:** 972 (Group B Activation)
**Date:** 2026-04-03
**Grounded in:** Direct reading of ihouse-core repository (src/api/cleaning_task_router.py, src/api/problem_report_router.py, src/tasks/cleaning_template_seeder.py, src/api/property_config_router.py, src/services/self_checkin_service.py, ihouse-ui/app/(app)/ops/cleaner/page.tsx, supabase/migrations/phase_586_605*, problem_report_labels.py)

---

## 1. What in the Current Real System Belongs to This Domain

Claudia's domain is property readiness — the operational truth of what makes a property ready for the next guest. The real system has:

- **Cleaning templates**: `cleaning_checklist_templates` table with property-specific → tenant global → hardcoded default fallback chain. Default template: 20 items across 5 rooms (bedroom, bathroom, kitchen, living_room, exterior) + 7 supply check items.
- **Checklist progress tracking**: `cleaning_task_progress` table with JSONB `checklist_state` (per-item done/requires_photo) and `supply_state` (per-item ok/low/empty/unchecked). Three completion flags: `all_items_done`, `all_photos_taken`, `all_supplies_ok`.
- **Photo documentation**: `cleaning_photos` table with Supabase Storage uploads (JPEG, PNG, WebP, HEIC, ≤10MB). Reference photo comparison via `property_reference_photos` table.
- **Readiness gate (Phase E-7)**: Lines 816-857 of `cleaning_task_router.py` — on cleaning completion, transitions property `operational_status` to "ready" or "ready_with_issues" (if open problem_reports exist).
- **Problem reports**: `problem_reports` table with 14 categories, urgent/normal priority, and automatic MAINTENANCE task creation (Phase 648).
- **Issue classification**: `problem_report_labels.py` maps 14 categories to maintenance specialties with bilingual labels (EN/TH).
- **Supply checks**: Simple status verification (ok/low/empty), not inventory management. Blocks completion if any supply is "empty" (unless `force_complete=true`).

## 2. What Appears Built

- **Template system with 3-level fallback**: `get_cleaning_template(property_id)` queries property-specific first, then tenant global (property_id IS NULL), then imports hardcoded default from `cleaning_template_seeder.py`. Default template has 20 items (5 rooms × 4 items avg) with 5 requiring photos, plus 7 supply checks (sheets, towels, soap, shampoo, toilet_paper, trash_bags, cleaning_supplies).

- **Bilingual template items**: Each checklist item has `label` (EN) and `label_th` (TH). Supply checks also bilingual. Supports multilingual cleaners.

- **Per-item progress tracking**: `cleaning_task_progress` stores checklist_state as JSONB array of `{room, label, done, requires_photo}`. Items toggled individually. `all_items_done` recalculated on each update. Photo validation checks that all rooms with `requires_photo=true` have at least one photo in `cleaning_photos`.

- **Photo upload with fallback**: Two endpoints — FormData upload (actual file to Supabase Storage bucket `cleaning-photos`) and JSON endpoint (for pre-uploaded URLs or `pending-upload://` markers). File validation: JPEG/PNG/WebP/HEIC, ≤10MB. Storage path: `{tenant_id}/{task_id}/{room_label}_{uuid}.{ext}`. Fallback generates `storage-failed://` marker if upload fails.

- **Reference photo comparison**: `reference_vs_cleaning(task_id)` endpoint builds side-by-side pairs by room — comparing property reference photos to cleaning photos. Enables quality verification.

- **3-flag completion gate**: `complete_cleaning(task_id)` checks three flags:
  - `all_items_done = True` (all checklist items completed)
  - `all_photos_taken = True` (all required rooms have photos)
  - `all_supplies_ok = True` (all supply items status "ok")
  - Returns HTTP 409 with blocker details if any condition fails
  - `force_complete=true` parameter bypasses supply check only (not items or photos)

- **Property status transition (readiness gate)**: On successful completion:
  1. Queries `problem_reports` WHERE status IN ('open', 'in_progress') for the property
  2. If open issues exist → `operational_status = "ready_with_issues"`
  3. If no issues → `operational_status = "ready"`
  4. Writes `PROPERTY_OPERATIONAL_STATUS_CHANGE` audit event with from/to status, trigger source, open issues count

- **Full operational_status lifecycle**:
  ```
  ready → occupied (check-in) → needs_cleaning (checkout) → ready / ready_with_issues (cleaning)
  ```

- **14-category issue classification** with maintenance specialty mapping:
  - pool → pool, plumbing → plumbing, electrical → electrical, ac_heating → electrical
  - furniture → furniture, structure → general, tv_electronics → electrical
  - bathroom → plumbing, kitchen → general, garden_outdoor → gardening
  - pest → general, cleanliness → general, security → general, other → general
  - Priority levels: urgent (CRITICAL SLA, 5min) and normal (MEDIUM SLA)

- **Auto maintenance task creation (Phase 648)**: When a problem report is created, a MAINTENANCE task is automatically created with appropriate priority. The `maintenance_task_id` FK links the report to its task. Urgent reports trigger SSE alert to ops dashboards (Phase 651).

- **Cleaner inline issue reporting (Phase E-9)**: Cleaner surface has built-in form for reporting issues during cleaning. Category selector, severity selector, description textarea. Creates problem_report via API. Source tagged as "cleaner_flow". Critical issues show warning: "property will be blocked".

## 3. What Appears Partial

- **Template customization UI**: Templates are stored in DB and can be property-specific, but the admin UI for creating/editing custom templates was not found. `cleaning_checklist_templates` can be populated via API but there's no visible template editor in `/admin/templates/page.tsx`. Templates may currently be seeded or created via direct DB operations.
- **Supply check as gate**: Supply verification is binary (ok/low/empty) — there's no quantity tracking. A cleaner marks towels as "ok" or "low" but doesn't record "3 of 6 towels present." The `force_complete=true` bypass allows completion even with empty supplies, weakening the gate.
- **Property type differentiation**: Templates key off `property_id`, not property type. Each property can have its own template, but there's no way to say "all villas get this checklist." New properties must be individually configured or inherit the global template.

## 4. What Appears Missing

- **No par level definitions**: The system verifies supplies are present (ok/low/empty status) but doesn't define what "enough" means per property. No `par_level` column or configuration that specifies "2-bedroom unit for 4 guests needs: 8 towels, 4 sets of sheets, 6 soap bars." The cleaner makes a judgment call.
- **No restock/procurement workflow**: When supplies are "low" or "empty," there's no automatic restock request, no inventory deduction, no procurement trigger. The supply check is an observation, not a workflow trigger.
- **No readiness gate aggregation function**: The gate checks 3 flags + open problem_reports, but there's no standalone `property_readiness_check()` function that can be called independently. The gate only runs as part of `complete_cleaning()`. Other code paths (e.g., task scheduler, admin dashboard) cannot query "is this property ready?" without repeating the logic.
- **No checklist quality scoring**: All items are binary (done/not done). No quality rating per item, no severity-weighted completion score. A checklist where every item is checked but photos show poor quality still passes.
- **No room-level granularity in readiness**: The gate is property-level. If bedroom_1 passes but bathroom_1 has issues, the property is either "ready" or "ready_with_issues" as a whole. No room-by-room readiness state.

## 5. What Appears Risky

- **`force_complete` bypass**: Allowing completion with empty supplies weakens the readiness guarantee. A property marked "ready" may have no towels if the cleaner used `force_complete`. The audit trail records this, but no downstream system blocks check-in based on supply status.
- **Property status transition as direct write**: The readiness gate writes `operational_status` directly (not event-sourced). If the write fails (wrapped in try/except), the cleaning task is marked COMPLETED but the property remains `needs_cleaning`. No reconciliation sweep exists to catch this silent failure.
- **Problem report → readiness coupling**: The gate checks open/in_progress problem_reports. If a problem report is created AFTER cleaning completion (e.g., maintenance worker finds an issue during inspection), the property's status is already "ready" and won't automatically downgrade to "ready_with_issues." Status only updates during cleaning completion.

**Open Group A question — deposit duplication guard**: If the checkout-created CLEANING task and the BOOKING_CREATED CLEANING task produce different task_ids (due to booking amendment), duplicate cleaning tasks could exist. The cleaner would need to complete both for property readiness, but the system may only track one.

## 6. What Appears Correct and Worth Preserving

- **3-level template fallback**: Property-specific → global → hardcoded default. Correct hierarchy — specific properties override when needed, new properties get a reasonable default.
- **Bilingual labels**: EN/TH on every checklist and supply item. Supports the Thai worker population directly in the template data.
- **3-flag completion gate**: Enforces items + photos + supplies independently. Each can be verified separately. The photo requirement is per-room, not per-item — practical.
- **Cleaning-separate-from-readiness design**: Cleaner can complete their work even if issues exist. Property is flagged "ready_with_issues" rather than blocking the cleaner's workflow. Correct separation of responsibilities.
- **Auto maintenance escalation**: Problem report → auto MAINTENANCE task with priority mapping → SLA enforcement. The escalation path is automated and immediate.
- **Reference photo comparison**: Side-by-side pairs by room enable quality verification. Strong accountability mechanism.
- **Audit event on status transition**: Every operational_status change is recorded with from/to, trigger source, and open issues count. Full traceability.

## 7. What This Role Would Prioritize Next

1. **Define par levels per property type**: Create a par level definition system — towels, linens, toiletries per guest capacity. Integrate with supply checks so "ok" has a measurable standard.
2. **Build template editor UI**: Admin should be able to create, edit, and assign cleaning templates without direct DB manipulation.
3. **Extract readiness gate as standalone function**: Allow other code paths (scheduler, admin dashboard, API) to query "is this property ready?" without going through `complete_cleaning()`.
4. **Add post-completion status downgrade**: If a problem report is created after cleaning completion, the property should automatically downgrade from "ready" to "ready_with_issues."
5. **Define property-type template mapping**: Allow template assignment by property type, not just property_id. "All 2-bedroom apartments use this template."

## 8. Dependencies on Other Roles

- **Marco**: Claudia defines checklist content; Marco ensures it works on the cleaner's phone. The 20-item checklist with photo requirements needs validation for mobile scroll length, capture UX, and offline behavior.
- **Ravi (Group A)**: Claudia's readiness gate is a precondition in Ravi's service flow. The `operational_status` transition after cleaning is the signal that enables the next booking's check-in prep.
- **Hana**: Claudia's standards inform Hana's performance signals. A cleaner who uses `force_complete` frequently is a staffing concern.
- **Sonia**: Claudia defines the operational content of the cleaner surface. Sonia validates it fits the cleaner's structural purpose.
- **Victor (Group C)**: If deposit settlement depends on property readiness state (e.g., forfeiting deposit due to property damage), Victor's financial lifecycle intersects Claudia's readiness assessment.

## 9. What the Owner Most Urgently Needs to Understand

The property readiness system is more complete than the original SYSTEM_MAP captured. The readiness gate EXISTS and works — it checks items, photos, supplies, and open problem reports before transitioning property status. The auto-escalation from problem report to maintenance task is built and functional. Bilingual support is in the template data.

Two structural improvements would significantly strengthen readiness:

1. **Par levels don't exist**: Supply checks are subjective ("ok" vs "low"). There's no measurable standard for what a property needs. A cleaner's judgment of "ok towels" might mean 2 towels for a 6-guest unit. Defining par levels per property capacity would transform supply checks from subjective observations to measurable verifications.

2. **Readiness is a point-in-time snapshot**: The gate runs once (at cleaning completion). If conditions change after (new issue reported, supplies used), the "ready" status persists. A continuously-evaluated readiness function would provide real-time accuracy.
