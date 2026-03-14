> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 646

**Date:** 2026-03-14
**Current Phase:** 646 — PII Document Security Hardening (closed)
**Last Closed Phase:** 646
**Test Suite:** 7,512 passed, 0 failed, 22 skipped

---

## What Was Done in This Session

### Phase 646 — PII Document Security Hardening

1. **PII URL Redaction** — `guest_checkin_form_router.py` now redacts `passport_photo_url`, `signature_url`, and `cash_photo_url` to `***` in `GET /checkin-form`. Boolean indicators (`passport_photo_captured`, `signature_recorded`, `cash_photo_captured`) added.

2. **Submit Lockout** — `POST /checkin-forms/{id}/submit` returns status indicators only: `passport_photo_count`, `passport_photos_captured`, `guest_count` — never raw URLs.

3. **Admin-Only Retrieval** — NEW `pii_document_router.py`:
   - `GET /admin/pii-documents/{form_id}` — JWT `role=admin` enforced
   - Returns Supabase Storage signed URLs (5-minute expiry)
   - Writes `PII_DOCUMENT_ACCESS` to `audit_log` per access (actor, IP, documents)

4. **Retention Policy** — Added to `work-context.md` locked invariants: minimum 1 year from check-out, no auto-deletion.

5. **Tests** — 17 new in `test_pii_document_security.py` covering redaction, role enforcement (403 for worker/manager, 200 for admin), audit logging, and edge cases.

### Deferred Items Audit

Audited Phases 586–625 deferred items. Added "Deferred Items — Open Items Registry" to `current-snapshot.md` and `work-context.md`:

| Phase | Title | Status |
|-------|-------|--------|
| 614 | Pre-Arrival Email (SMTP) | 🟡 Deferred |
| 617 | Wire Form → Checkin Router | 🟡 Deferred |
| 618 | Wire QR → Checkin Response | 🟡 Deferred |
| — | Supabase Storage Buckets (5) | 🔴 Pending Decision |

### Storage Bucket Mapping

Created detailed mapping for 5 Supabase Storage buckets:
- `reference-photos`, `marketing-photos`, `passport-photos`, `signatures`, `cleaning-photos`
- Security analysis: `passport-photos` and `signatures` must be PRIVATE with RLS
- Bucket creation not yet executed — pending user decision

---

## Key Files for Next Session

| File | Role |
|------|------|
| `src/api/guest_checkin_form_router.py` | Check-in form CRUD, PII redaction |
| `src/api/pii_document_router.py` | Admin-only PII retrieval + audit |
| `tests/test_pii_document_security.py` | 17 PII security tests |
| `docs/core/current-snapshot.md` | Deferred items registry |
| `docs/core/work-context.md` | PII invariants + deferred items |

---

## Next Objective

Supabase Storage Buckets — create the 5 required buckets (decision pending from user: via MCP or manual). After that, continue with next wave of the roadmap.

---

## Deferred Items (Carried Forward)

| Phase | Title | Unblock Condition |
|-------|-------|-------------------|
| 614 | Pre-Arrival Email | SMTP env vars configured |
| 617 | Wire Form → Checkin Router | Live booking flow active |
| 618 | Wire QR → Checkin Response | Same as 617 |
| — | Storage Buckets (5) | User decision on creation strategy |
