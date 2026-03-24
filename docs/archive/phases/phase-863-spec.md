# Phase 863 — Media Storage Remediation + Canonical Retention Architecture

**Status:** Closed
**Prerequisite:** Phase 862 — Staff Onboarding Data Mapping Correction + Email Delivery UX
**Date Closed:** 2026-03-25

## Goal

A full, coordinated remediation pass on four live media/storage findings that were identified in the preceding architectural audit session. The system had accumulated structural violations of the canonical storage model — staff PII files in a public bucket, misplaced onboarding photos, orphaned files from deleted properties, and staging temp file accumulation. This phase also formalized the canonical storage/retention architecture, anchored permanent invariants in the blast-constitution and gemini.md, and fixed the upload routing code so these violations cannot recur.

In addition, this phase corrected the BOOKING_AMENDED noise loop in the iCal sync engine (which was writing identical events on every sync cycle when no booking field had changed), and executed a live before/after proof on KPG-500.

## Invariants Enforced

- **INV-MEDIA-01** — No binary data in Postgres. All files in Supabase Storage only.
- **INV-MEDIA-02** — Strict bucket routing: `staff_onboarding_router.py` must never write to `property-photos` (public). Staff files go to `staff-documents` (private).
- **INV-STORAGE-01** — Guest identity docs: 90-day auto-delete after checkout. Staff identity/employment docs: retained while employed + 12 months, never auto-deleted.
- **INV-STORAGE-02** — `cleaning-photos` bucket is private (signed URLs only). Enforced in this phase.
- **INV-STORAGE-03** — Archive verification before live event_log deletion.

## What Was Done

### A. Live Storage Remediation (one-time migration script `media_remediation.py`)

| Category | Files | Action | Result |
|----------|-------|--------|--------|
| Staff PII in public bucket | 2 | Moved `property-photos/staff-pii/` → `staff-documents/staff-pii/` | ✅ |
| Staff onboarding photos misplaced | 21 | Moved `property-photos/staff_onboarding/` → `staff-documents/staff_onboarding/` | ✅ |
| Staff avatar photos misplaced | 8 | Moved `property-photos/staff-avatars/reference/` → `staff-documents/staff-avatars/` | ✅ |
| Orphaned files (deleted properties) | 12 | Deleted from `property-photos/test-property-1/` and `property-photos/18/` | ✅ |
| Staging temp pile-up | 32 | Deleted from `property-photos/staging/` | ✅ |
| DB references updated | 5 users | `tenant_permissions.photo_url` / `id_photo_url` → new signed URLs on `staff-documents` | ✅ |
| `cleaning-photos` bucket | — | Changed from `public=true` → `public=false` | ✅ |

### B. Routing Fix — `staff_onboarding_router.py`

- **Before:** uploaded to `property-photos` (public bucket), returned public CDN URL.
- **After:** uploads to `staff-documents` (private bucket), returns signed URL valid 7 days + `storage_path` for future regeneration.
- Comment added: `INV-MEDIA-02: Staff files go to staff-documents (private), never property-photos (public)`

### C. Storage Cascade on Property Deletion — `properties_router.py`

- `DELETE /properties/{property_id}` now runs step 5: lists and deletes all objects under `property-photos/{property_id}/` (including subfolders `reference/`, `gallery/`) after the DB record is removed.
- Soft failure: logs a warning and sets `storage_files: -1` if Storage cleanup fails — never blocks the deletion itself.

### D. BOOKING_AMENDED Noise Fix — `ical_sync_router.py`

- Before writing `BOOKING_AMENDED`, the system now computes a hash of meaningful business fields: `check_in`, `check_out`, `guest_name`, `status`.
- If the hash matches the current `booking_state`, no event is written.
- KPG-500 proof: 0 new `BOOKING_AMENDED` events in 10 minutes post-fix vs. multiple per sync cycle pre-fix.

### E. Canonical Architecture Documents

- `.agent/architecture/storage-retention.md` — authoritative storage/retention reference. Defines 6 buckets, 6 `INV-MEDIA` invariants, 3 `INV-STORAGE` invariants, retention rules per category, and New Media Category Onboarding Checklist.
- `.agent/system/blast-constitution.md` — INV-STORAGE-01 updated to explicitly carve out staff documents from the 90-day guest PII rule.
- `.agent/gemini.md` — Section 13 (Media Rules) updated with mandatory canonical pointer and guest-vs-staff distinction.

## Design / Files

| File | Change |
|------|--------|
| `src/api/staff_onboarding_router.py` | MODIFIED — upload target changed from `property-photos` to `staff-documents`; returns signed URL |
| `src/api/properties_router.py` | MODIFIED — property permanent-delete now cascades to Storage cleanup under `property-photos/{property_id}/` |
| `.agent/architecture/storage-retention.md` | MODIFIED — INV-STORAGE-01 corrected (staff docs excluded from 90-day rule) |
| `.agent/system/blast-constitution.md` | MODIFIED — INV-STORAGE-01 updated |
| `.agent/gemini.md` | MODIFIED — Section 13 updated with canonical pointer + media category distinction |
| `/tmp/media_remediation.py` | NEW (temp) — one-time migration script; not committed to repo |

## Final Storage State (Post-Remediation)

| Bucket | Public | Files | Size |
|--------|--------|-------|------|
| `property-photos` | ✅ Public | 15 | 821 KB |
| `staff-documents` | 🔒 Private | 31 | 8 MB |
| `cleaning-photos` | 🔒 Private | 0 | — |
| `guest-uploads` | 🔒 Private | 0 | — |
| `pii-documents` | 🔒 Private | 0 | — |
| `exports` | 🔒 Private | 0 | — |

## Result

**0 TypeScript errors. Backend tests unaffected. All 4 media findings resolved. Storage cascade implemented. Routing fixed for future uploads. Deployed to Railway (auto) + Vercel staging (`900dff3`).**

Git commit: `900dff3` on branch `checkpoint/supabase-single-write-20260305-1747`.

Next Phase: **Phase 864** — TBD (next product feature wave).
