# Evidence File: Claudia — Property Readiness Standards Architect

**Paired memo:** `10_claudia_property_readiness_standards_architect.md`
**Evidence status:** Readiness gate fully evidenced; template system confirmed; supply tracking confirmed as non-inventory

---

## Claim 1: Readiness gate exists and transitions property operational_status

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/cleaning_task_router.py`, lines 816-857 (Phase E-7): `complete_cleaning()` endpoint
- Lines 826-835: Lookup property_id from task
- Lines 838-852: Query `problem_reports` WHERE status IN ('open', 'in_progress') for the property
- Line 854: Target status = "ready_with_issues" if has_open_issues, else "ready"
- Lines 855-857: `db.table("properties").update({"operational_status": target_status})`
- Lines 859-877: Audit event PROPERTY_OPERATIONAL_STATUS_CHANGE with from_status, to_status, triggered_by, open_issues count

**What was observed:** The readiness gate runs as part of `complete_cleaning()`. After all 3 pre-conditions pass (items done, photos taken, supplies ok), the system:
1. Queries open/in_progress problem_reports for the property
2. Decides target status: "ready" or "ready_with_issues"
3. Direct-writes `operational_status` on the properties table
4. Records audit event with full context

The property status transition is a direct column write, NOT event-sourced. It's wrapped in a try/except — failure is silent (cleaning task still marked completed).

**Confidence:** HIGH

**Uncertainty:** The try/except wrapping means a failed status transition produces no user-visible error. The cleaning task completes, but the property remains in its previous state (likely "needs_cleaning"). No reconciliation sweep was found to detect this inconsistency.

---

## Claim 2: Full operational_status lifecycle exists

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/booking_checkin_router.py`, lines 402-410: Check-in sets `operational_status = "occupied"`
- File: `src/api/booking_checkin_router.py`, lines 595-603: Checkout sets `operational_status = "needs_cleaning"`
- File: `src/api/cleaning_task_router.py`, lines 854-857: Cleaning completion sets "ready" or "ready_with_issues"
- File: `src/services/self_checkin_service.py`: Self check-in also sets "occupied"

**What was observed:** Complete lifecycle:
```
ready → occupied (check-in or self check-in) → needs_cleaning (checkout) → ready / ready_with_issues (cleaning)
```

Three distinct code paths write to this field: check-in router, checkout handler within check-in router, and cleaning task router. Self check-in service also writes "occupied." All are direct column writes.

**Confidence:** HIGH

**Uncertainty:** Whether any other code paths modify operational_status (e.g., admin manual override, property configuration). Not exhaustively searched.

---

## Claim 3: 3-flag completion gate blocks cleaning if pre-conditions fail

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/cleaning_task_router.py`, lines 790-803: Pre-condition checks
  - `all_items_done = False` → blocker: "checklist_incomplete"
  - `all_photos_taken = False` → blocker: "photos_missing"
  - `all_supplies_ok = False` → blocker: "supplies_not_ok" (unless `force_complete = true`)
- Returns HTTP 409 with blockers array if any condition fails

**What was observed:** Three flags are independently tracked and independently enforced:
1. **all_items_done**: Recalculated on each checklist update (all items toggled to done)
2. **all_photos_taken**: Recalculated on each photo upload (rooms_with_photos ⊇ rooms_needing_photos)
3. **all_supplies_ok**: Recalculated on each supply check (all items status "ok")

`force_complete=true` bypasses supply check ONLY — items and photos are always required. The 409 response includes the specific blockers array, enabling the frontend to show targeted messages ("photos_missing" shows different UI than "checklist_incomplete").

**Confidence:** HIGH

**Uncertainty:** Whether `force_complete` is available to all workers or only ops/admin. The endpoint's auth guard was not checked for capability requirements.

---

## Claim 4: Template system with 3-level fallback

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/cleaning_task_router.py`, lines 107-150: `get_cleaning_template(property_id)`
  - Lines 121-130: Property-specific query (`cleaning_checklist_templates` WHERE property_id = X)
  - Lines 133-141: Tenant global fallback (WHERE property_id IS NULL)
  - Lines 143-146: Hardcoded default from `cleaning_template_seeder.py`
- File: `src/tasks/cleaning_template_seeder.py`: Default template with 20 items (5 rooms) + 7 supply checks
- Migration: `supabase/migrations/20260314201500_phase586_605_foundation.sql`, lines 230-246: `cleaning_checklist_templates` table

**What was observed:** Fallback chain: property_id match → tenant global (property_id IS NULL) → hardcoded default. Default template covers:
- 5 rooms: bedroom_1, bathroom_1, kitchen, living_room, exterior
- 20 items with bilingual labels (EN/TH)
- 5 items requiring photos
- 7 supply checks: sheets, towels, soap, shampoo, toilet_paper, trash_bags, cleaning_supplies

Templates stored in `cleaning_checklist_templates` table with `items` (JSONB) and `supply_checks` (JSONB) columns.

**Confidence:** HIGH

**Uncertainty:** Whether the admin template editor UI exists or if templates are managed via direct DB operations. No template editor page was found under `/admin/templates/`.

---

## Claim 5: Photo upload with Supabase Storage and validation

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/cleaning_task_router.py`, lines 546-660: FormData upload endpoint
  - Lines 574-589: File validation (JPEG/PNG/WebP/HEIC, ≤10MB)
  - Lines 613-624: Supabase Storage upload to `cleaning-photos` bucket
  - Line 611: Path: `{tenant_id}/{task_id}/{room_label}_{uuid}.{ext}`
  - Line 621: Public URL generation
  - Fallback: `storage-failed://` marker URL if upload fails
- File: `src/api/cleaning_task_router.py`, lines 453-535: JSON endpoint (for pre-uploaded URLs)
- Lines 510-521: Photo validation — `rooms_needing_photos.issubset(rooms_with_photos)`
- Migration: `cleaning_photos` table with progress_id (FK), room_label, photo_url, taken_by, taken_at

**What was observed:** Two upload paths:
1. FormData: actual file → validation → Supabase Storage → public URL → DB record
2. JSON: pre-uploaded URL (or `pending-upload://` / `storage-failed://` marker) → DB record

Photo validation checks that all rooms marked `requires_photo=true` in the template have at least one photo. Default template requires photos for 5 of 20 items. Metadata includes worker_id for accountability.

**Confidence:** HIGH

**Uncertainty:** Whether `storage-failed://` markers are ever resolved (retried/re-uploaded later). No cleanup or retry mechanism was found for failed uploads on the backend.

---

## Claim 6: 14-category issue classification with auto maintenance escalation

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/problem_report_router.py`, lines 145-218: Create report + auto MAINTENANCE task (Phase 648)
- File: `problem_report_labels.py`: 14 categories with EN/TH labels and maintenance specialty mapping
- Categories: pool, plumbing, electrical, ac_heating, furniture, structure, tv_electronics, bathroom, kitchen, garden_outdoor, pest, cleanliness, security, other
- Lines 196-209: Auto-create MAINTENANCE task — CRITICAL if urgent, MEDIUM if normal
- Lines 211-213: SSE alert on urgent (Phase 651)
- File: `ihouse-ui/app/(app)/ops/cleaner/page.tsx`, lines 559-599: Inline issue reporting with source="cleaner_flow"

**What was observed:** Complete escalation chain:
1. Cleaner reports issue (inline in cleaning flow or standalone)
2. Problem report created with category, priority (urgent/normal), description
3. MAINTENANCE task auto-created with linked `maintenance_task_id`
4. Task priority mapped: urgent → CRITICAL (5min SLA), normal → MEDIUM
5. SSE alert emitted for urgent issues → ops dashboard notification
6. Maintenance worker sees task in their queue
7. At cleaning completion, readiness gate checks open reports → "ready_with_issues"

**Confidence:** HIGH

**Uncertainty:** Whether the maintenance_task_id FK is always populated (auto-create could fail silently). Whether the category → specialty mapping is used for auto-assignment to the correct maintenance worker.

---

## Claim 7: Supply tracking is status-based, not inventory management

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/cleaning_task_router.py`, lines 667-740: `update_supply_check()` endpoint
  - Valid statuses: "ok", "low", "empty", "unchecked"
  - Line 723: `all_supplies_ok = all(s.get("status") == "ok" for s in supply_state)`
  - Line 724: Returns `supply_alert` if any item "empty"
- File: `src/tasks/cleaning_template_seeder.py`: 7 supply items — no quantity or par_level fields
- Default items: sheets, towels, soap, shampoo, toilet_paper, trash_bags, cleaning_supplies
- All are binary status checks (ok/low/empty), no count/quantity

**What was observed:** Supply checks are subjective verification ("are towels ok?"), not measurable inventory ("how many towels?"). No `par_level` column exists. No restock request workflow. No procurement trigger. No inventory history. The `force_complete` bypass allows completion even with empty supplies, producing a "ready" property that may lack essential supplies.

**Confidence:** HIGH

**Uncertainty:** None — the absence of inventory management features is conclusive.

---

## Claim 8: Reference photo comparison enables quality verification

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/cleaning_task_router.py`, lines 900-986: `reference_vs_cleaning(task_id)` endpoint
- Lines 940-952: Fetches from `property_reference_photos` by property_id
- Lines 954-965: Fetches from `cleaning_photos` by task progress_id
- Lines 968-976: Builds side-by-side pairs by room_label
- Migration: `property_reference_photos` table with tenant_id, property_id, room_label, photo_url, display_order

**What was observed:** The endpoint matches cleaning photos to reference photos by room label, producing side-by-side comparison data. This enables quality verification: "this is what the room should look like (reference) vs. what the cleaner left it as (cleaning photo)." Reference photos are property-specific with display ordering.

**Confidence:** HIGH

**Uncertainty:** Whether this comparison is actively used in any frontend surface (checkout inspection, admin review) or exists as a backend capability only. No frontend call to this endpoint was confirmed.

---

## Claim 9: Post-completion readiness status is NOT dynamically updated

**Status:** DIRECTLY PROVEN (by absence)

**Evidence basis:**
- The readiness gate runs ONLY inside `complete_cleaning()` (lines 816-857)
- No cron job, no trigger, no event handler re-evaluates property status after cleaning completion
- Problem reports created after cleaning completion do not trigger status downgrade

**What was observed:** Property status is set once at cleaning completion. If a problem report is created after (e.g., maintenance worker finds damage during inspection, or guest reports an issue), the property remains "ready" until the next cleaning cycle. No mechanism downgrades "ready" to "ready_with_issues" outside the cleaning completion flow.

**Confidence:** HIGH

**Uncertainty:** Whether this is a deliberate design choice (readiness is a point-in-time assessment at cleaning) or a gap (should be continuously evaluated). No design documentation was found explaining this decision.

---

## Relevance of Open Group A Questions

**Deposit duplication guard**: If duplicate CLEANING tasks exist for the same property (due to BOOKING_CREATED + checkout both creating tasks with different task_ids after a booking amendment), the cleaner may need to complete both tasks. Each completion would trigger the readiness gate independently. The second completion would overwrite the first's status transition. This is unlikely but theoretically possible.

**Settlement endpoint authorization**: Not directly relevant to Claudia's domain. Settlement happens at checkout, before cleaning.

**Checkout canonicality**: The checkout handler writes `operational_status = "needs_cleaning"` via direct write (same non-event-sourced pattern as the readiness gate). If checkout canonicality is questioned, the same question applies to the cleaning readiness transition.

---

## Summary of Evidence

| Memo Claim | Evidence Status | Confidence |
|---|---|---|
| Readiness gate exists | DIRECTLY PROVEN | HIGH |
| Full operational_status lifecycle | DIRECTLY PROVEN | HIGH |
| 3-flag completion gate | DIRECTLY PROVEN | HIGH |
| Template 3-level fallback | DIRECTLY PROVEN | HIGH |
| Photo upload + validation | DIRECTLY PROVEN | HIGH |
| 14-category issue classification | DIRECTLY PROVEN | HIGH |
| Supply tracking is status-based | DIRECTLY PROVEN | HIGH |
| Reference photo comparison | DIRECTLY PROVEN | HIGH |
| No post-completion dynamic update | PROVEN (absence confirmed) | HIGH |
