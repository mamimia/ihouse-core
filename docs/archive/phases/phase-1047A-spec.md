# Phase 1047A — Guest Portal Foundation Repair

**Status:** Closed (Effectively — see 1047A-name sub-phase for open items)
**Prerequisite:** Phase 1036 (OM-1: Stream Hardening)
**Date Closed:** 2026-04-02

## Goal

Repair five broken behaviors in the guest-facing `/guest/[token]` portal that had been identified through audit. These were functional regressions preventing the portal from working as a real hospitality product. No redesign — foundation repair only.

## Invariant

The guest portal must never show internal operational identifiers of any kind (property codes, booking refs, unit IDs). This rule was established during this phase and is now a locked product rule enforced at both backend and frontend layers.

## Design / Files

| File | Change |
|------|--------|
| `src/api/guest_portal_router.py` | MODIFIED — added `cover_photo_url` to SELECT; fixed `house_info` JSON unwrapping; fixed guest message POST key (`content` not `message`) |
| `ihouse-ui/app/(public)/guest/[token]/page.tsx` | MODIFIED — fixed `cover_photo_url` rendering; fixed `house_info` unwrap; fixed `booking_status` chip; fixed message send key; added guest-safe status chip fallback |
| `ihouse-ui/app/(app)/guests/[id]/page.tsx` | MODIFIED — wired `onGeneratePortalFull` prop to PortalBlock; fixed Generate QR API call |

## Result

Five regressions fixed. Cover photo renders. House info renders from corrected schema. Status chip is guest-safe. Guest message send uses correct key. Generate QR button functional.

Tests: not independently numbered — part of the guest portal hardening workstream.

---

# Phase 1047A-name — Guest Portal No-Leak Enforcement + Schema Alignment

**Status:** Effectively closed
**Prerequisite:** Phase 1047A
**Date Closed:** 2026-04-03

## Goal

Eliminate all internal identifier leakage from the guest portal surface, and fix real DB schema drift (backend was reading non-existent column names from the `properties` table).

## Invariant (locked product rule)

**No internal operational identifier may appear on any guest-facing surface.**
This includes: property codes, booking refs, unit IDs, internal status strings, OTA placeholder names.
If a human property name is missing, fallback must be `"Your Villa"` or equivalent guest-safe text — never an internal code.
Enforced at both backend (fallback chain) and frontend (final render guard).

## Design / Files

| File | Change |
|------|--------|
| `src/api/guest_portal_router.py` | MODIFIED — removed `property_id`/`booking_ref` from `property_name` fallback; `name` column → `display_name` (root fix: column does not exist); `check_in_time`/`check_out_time` → `checkin_time`/`checkout_time`; `welcome_message` → `description`; `checkout_notes` → `extra_notes`; `manager_*` → `owner_phone`/`owner_email`; sanitized OTA placeholder guest names; WhatsApp pre-fill now uses `display_name` |
| `ihouse-ui/app/(public)/guest/[token]/page.tsx` | MODIFIED — frontend guard: `{data.property_name \|\| 'Your Villa'}`; status chip returns guest-safe fallback for unknown strings |

## Result

- Real property name (`display_name`) renders correctly — staging proven: "Emuna Villa TEST" visible
- No internal code visible on tested portal path
- Guest-safe fallback ("Your Villa") proven on null-name path
- Cover photo, status chip, house info, check-in/out times all render from correct DB columns

**BUILT:** yes | **SURFACED:** yes | **PROVEN:** on the tested guest portal path and the audited fallback/source chain
**OPEN:** WhatsApp/contact end-to-end proof; any untested guest-facing variants

Commits: `940fecd` → `1ec8122` → `54ef82c`
