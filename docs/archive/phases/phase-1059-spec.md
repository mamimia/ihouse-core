# Phase 1059 — Operational Resilience Hardening

**Status:** Closed (partial delivery — Items 1 and 5 partially addressed)
**Prerequisite:** Phase 1058 — Operational Audit Closure: PKA-Bridge + Backend Auth Hardening
**Date Closed:** 2026-04-04

## Goal

Address operational resilience gaps surfaced during the PKA-Bridge audit. Two items
were targeted: (1) photo upload failure chain transparency, and (5) saga/compensation
model for multi-step wizard flows.

## What was delivered

### Item 1 — Photo upload failure chain (substantially hardened)
- Storage failure now returns `502` to caller instead of silent broken DB record
- `upload_status` column added to relevant table
- Failed upload UI: persistent error state + retry gated (no silent re-submit)
- **Residual risk:** `/worker/documents/upload` failure contract unchanged; no offline queuing

### Item 5 — Saga/compensation model (partially mitigated, not fully closed)
- Check-in browser-refresh recovery: `sessionStorage` draft + `GET /checkin-resume` endpoint
- **Not closed:** checkout wizard cross-step rollback, `backend wizard_draft`, multi-device
  resume, broader compensation model remain open for a dedicated saga phase

## Invariant

No new invariants. Existing PII and storage invariants (INV-MEDIA-01/02, INV-STORAGE-01/02/03)
unchanged and active.

## Design / Files

| File | Change |
|------|--------|
| `src/api/checkin_router.py` | NEW: `GET /checkin-resume` endpoint + sessionStorage resume |
| `src/api/` (upload paths) | MODIFIED: storage failure → 502, `upload_status` written |

## Result

Phase partially delivered. Items 1 and 5 substantially reduced in risk. Full saga
compensation model deferred to dedicated future phase. Phase closed to unblock the
guest checkout stream.
