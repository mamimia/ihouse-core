# Phase 646 — PII Document Security Hardening

**Status:** Closed
**Prerequisite:** Phase 645 (Wave 3: Task System Enhancement — Tests & Edge Cases)
**Date Closed:** 2026-03-14

## Goal

Harden PII handling for passport photos, signatures, and cash deposit photos in the check-in flow. Enforce ephemeral preview for workers during capture, post-submit lockout (no PII URLs returned after form submission), admin-only document retrieval through dedicated audit-logged endpoint, and explicit retention policy.

## Invariant

- `GET /checkin-form` NEVER returns raw PII URLs — always redacted to `***` with boolean indicators
- PII document access exclusively through `GET /admin/pii-documents/{form_id}` — requires JWT role=admin
- Every PII access writes `PII_DOCUMENT_ACCESS` to `audit_log` (actor, IP, documents accessed)
- PII documents retained minimum 1 year from check-out, no auto-deletion

## Design / Files

| File | Change |
|------|--------|
| `src/api/guest_checkin_form_router.py` | MODIFIED — `_redact_guest_pii()`, `_redact_deposit_pii()` helpers; GET redacts, submit returns status-only |
| `src/api/pii_document_router.py` | NEW — admin-only `GET /admin/pii-documents/{form_id}`, signed URLs (5-min expiry), audit log |
| `src/main.py` | MODIFIED — registered pii_document_router |
| `docs/core/work-context.md` | MODIFIED — PII retention invariant added to locked invariants |
| `tests/test_pii_document_security.py` | NEW — 17 contract tests |

## Result

**7,512 tests pass, 22 skipped.**
17 new PII security tests cover: redaction helpers, form GET redaction, submit status-only response, role enforcement (403 for worker/manager/no-role, 200 for admin), audit logging (action + IP), and no-role denial.
