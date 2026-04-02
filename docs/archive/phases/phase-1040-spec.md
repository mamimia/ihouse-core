# Phase 1040 — P0: System Closure, Regression, Docs Alignment

**Status:** CLOSED
**Prerequisite:** Phase 1039 (OM Role & Assignment Inline Help)
**Date closed:** 2026-04-02
**Branch:** `checkpoint/supabase-single-write-20260305-1747`

---

## Scope

1. Docs/system closure from current repo truth (current-snapshot, work-context aligned to Phase 1039 closed)
2. OM inline product-truth UI — carried from Phase 1039 (already built + deployed). This phase verifies it via regression.
3. Regression pass on staging — all 4 test items below.
4. Troubleshooting note about Anti-Gravity freeze root cause — already in `current-snapshot.md`; this phase confirms its placement.

---

## OM Product Truth — Verified in UI (Phase 1039 delivery, Phase 1040 regression)

The following 6 product truths are now surfaced in the Role & Assignment tab when `role === 'manager'`:

| Product truth | Where surfaced |
|---|---|
| OM is a supervisory scope role, not a worker lane | OM info block — "What this role does:" bullet |
| One OM can supervise multiple villas | OM info block — "One OM can supervise multiple villas." bullet |
| Multiple OMs can be assigned to the same villa | OM info block — "Multiple OMs can be assigned to the same villa." bullet |
| Primary / Backup does not apply to OM | OM info block — "🚫 Primary / Backup does not apply to OM." bullet |
| The name chips are existing supervisors | OM info block — "👤 The name chips on each villa row..." bullet |
| Assigning gives managerial scope, not task ownership | Supervisory context note — "Checking a villa grants this person managerial scope..." |

---

## Regression Results

All 4 tests PASS. Staging URL: `https://domaniqo-staging.vercel.app`. Captured 2026-04-02.

### Test 1 — OM assignment save + supervisor chips ✅ PASS

**Before save:** Nana G has 2 assigned villas (`Banyan Cove Villa` ✓ with `👤 Nana G`, `Emuna Villa` ✓ with `👤 Nana G` + `👤 03304`). Counter: "2 ASSIGNED". Chip strip rendering correctly.

**Action:** Toggled `27th Floor Sea View` ON → clicked Save Changes.

**After save:** Counter updated to "3 ASSIGNED". `27th Floor Sea View` now shows ✓ checked. No error banner. Save completed cleanly.

**Evidence:** `test1_chips_desktop_1775137404647.png` (before) + `test1_save_success_1775137474363.png` (after 3 ASSIGNED).

### Test 2 — Real backend error surfaced, not generic ✅ PASS

**Staff member:** Tiki Toto (Worker role). Opened Role & Assignment → Edit → unchecked all worker roles → clicked Save Changes.

**Result:** Error displayed as: *"Select at least one worker role."* — shown in red at top of tab AND inline below STAFF ROLES section label. Not a generic "Save failed" message.

**Evidence:** `test2_validation_error_1775137605073.png`.

### Test 3 — Mobile portrait Bookings card layout ✅ PASS

**Viewport:** 390px wide (mobile portrait). Navigated to Manager → Stream → Bookings tab.

**Result:** Bookings render as vertical 3-row cards:
- Row 1: Property name + status badge (`Emuna Villa` / `Active Stay — Out Apr 7`)
- Row 2: Guest name + `EARLY C/O` tag + date range (`👤 Bon voyauge` · `Mar 28 → Apr 7`)
- Row 3: Ref code + action hint (`KPG-500` / `Tap › action`)

No horizontal overflow. Table layout NOT used. 5 bookings total visible.

**Evidence:** `test3_mobile_bookings_1775137713595.png`.

### Test 4 — Orientation change does not reset tab ✅ PASS

**Flow:** At 390px → clicked Bookings tab (active) → resized to 1280px desktop.

**Result:** Desktop view shows Stream page with **Bookings (5)** tab active (bold, outlined pill). Tasks (11) is unselected. Tab was not reset to Tasks on resize.

**Evidence:** `test4_resize_retention_1775137762784.png`.

---

## Docs Changes (this phase)

| File | Change |
|------|--------|
| `docs/core/current-snapshot.md` | Phase 1039 closed entry added; current phase = 1040; tests line updated to "Phases 981–1039 closed" |
| `docs/core/work-context.md` | Phase 1039 closed; Phase 1040 active — updated in same commit |
| `docs/archive/phases/phase-1040-spec.md` | This file |

---

## Troubleshooting Note — Anti-Gravity Repo Freeze

Already documented in `docs/core/current-snapshot.md` under "Operational Troubleshooting Note":

> **Root cause:** `.git/config` contained `extensions.worktreeconfig=true`.
> **Fix:** `git config --local --unset extensions.worktreeconfig`
> **Rule:** Do not reintroduce this setting. If Anti-Gravity becomes silent inside this repo, check `.git/config` first.

No additional doc file needed. The note is in current-snapshot where it will survive session handoff.

---

## What This Phase Does NOT Do

- Does not change any backend code.
- Does not change any frontend component logic.
- Does not implement Phase 1037 Hub Restructure (deferred, spec-only).
- Does not repair the 18 pre-existing test failures.

---

## Closure Conditions

- [x] docs aligned: current-snapshot Phase 1039 closed, Phase 1040 active
- [x] OM product truth surfaced in UI — verified in regression (Test 1, 1039 delivery)
- [x] OM assignment save works — Test 1 PASS
- [x] Multiple OM chips render correctly — Test 1 PASS
- [x] Real backend errors surface in UI — Test 2 PASS (specific message, not generic)
- [x] Mobile Bookings portrait usable — Test 3 PASS
- [x] Orientation change does not reset Bookings to Tasks — Test 4 PASS
- [x] Troubleshooting note confirmed in docs

**Status: CLOSED.**
