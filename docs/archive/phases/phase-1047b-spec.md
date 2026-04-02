# Phase 1047B — Guest Portal Host Identity Block

**Status:** Closed
**Prerequisite:** Phase 1047A-name
**Date Closed:** 2026-04-03

## Goal

Add a curated guest-facing host identity block to the `/guest/[token]` portal. This is a presentation layer only — display name, optional avatar, optional welcome note — set by the operator per property. It does not represent routing truth, owner truth, or system identity. It exists to give the guest a human-facing sense of who is hosting them.

## Invariant

`portal_host_*` fields are guest-facing display layer only, not routing truth or system identity.
The host identity block renders only when `portal_host_name` is set.
No internal ID, system username, or submitter name may appear in this block.
Field names are prefixed `portal_host_` to make the layer boundary explicit at code level.
The admin UI section is labeled "GUEST PORTAL — HOST IDENTITY" (not "Host Identity"), with a framing note that these are presentation fields, not contact routing.

## Design / Files

| File | Change |
|------|--------|
| `supabase/migrations` (applied via MCP) | NEW — `ALTER TABLE properties ADD COLUMN portal_host_name TEXT, ADD COLUMN portal_host_photo_url TEXT, ADD COLUMN portal_host_intro TEXT` with SQL comments stating display-layer-only semantics |
| `src/api/guest_portal_router.py` | MODIFIED — `portal_host_name`, `portal_host_photo_url`, `portal_host_intro` added to properties SELECT and portal JSON response |
| `ihouse-ui/app/(public)/guest/[token]/page.tsx` | MODIFIED — `GuestPortalData` type extended; `PortalHostBlock` component added (null-guard, initials fallback, compact mode); inserted between `WelcomeHeader` and Home Essentials |
| `ihouse-ui/app/(app)/admin/properties/[propertyId]/page.tsx` | MODIFIED — 3 state vars; load(); handleEditSave body; "GUEST PORTAL — HOST IDENTITY" section in General tab with framing note, photo preview, 200-char welcome note counter |

## Result

**BUILT:** yes — DB migration applied, backend updated, admin UI updated, frontend component built
**SURFACED:** yes — deployed to staging `domaniqo-staging.vercel.app` (Vercel + Railway)
**PROVEN:** pending — requires staging portal screenshot with `portal_host_name` set to confirm render path

Commit: `215e9f8`
Branch: `checkpoint/supabase-single-write-20260305-1747`

**Proof required before reclassifying as fully proven:**
- Portal screenshot with `portal_host_name` set → block visible with name (and photo if set)
- Portal screenshot with `portal_host_name` null → block entirely absent
- Admin settings screenshot showing the three fields under the labeled section
