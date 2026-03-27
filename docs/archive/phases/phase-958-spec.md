# Phase 958 — Worker Check-in Audit & Root-Cause Isolation

**Status:** Closed
**Prerequisite:** Phase 957 (Global Theme Consistency)
**Date Closed:** 2026-03-28

## Goal

Conduct a rigorous, evidence-based audit of the worker-side check-in flow on staging to isolate the exact root causes of three critical failures: task completion lifecycle, guest name data duplication, and QR image generation 503 error. No speculation — only proven root causes with exact DB rows, API responses, and code paths.

## Invariant (if applicable)

- Backend `PATCH /worker/tasks/{task_id}/complete` MUST accept ACKNOWLEDGED→COMPLETED (verified — no regression)
- `POST /worker/checkin/save-guest-identity` writes exactly what the frontend sends — no server-side name mutation

## Design / Files

| File | Change |
|------|--------|
| `src/api/worker_router.py` | INVESTIGATED — verified complete_task route + _transition_task logic |
| `src/api/checkin_identity_router.py` | INVESTIGATED — verified save-guest-identity write path |
| `src/api/guest_checkin_form_router.py` | INVESTIGATED — verified QR image endpoint, qrcode ImportError |
| `src/tasks/task_model.py` | INVESTIGATED — verified VALID_TASK_TRANSITIONS includes ACKNOWLEDGED→COMPLETED |
| `ihouse-ui/app/(app)/ops/checkin/page.tsx` | INVESTIGATED — identified task_id degradation during booking merge |
| `ihouse-ui/lib/staffApi.ts` | INVESTIGATED — verified apiFetch JWT + auth token handling |

## Result

**No code changes.** This is an audit-only phase.

Three root causes isolated with exact evidence:

1. **Task completion:** Backend works. Frontend silently skips PATCH because `task_id` is undefined after booking data merge.
2. **Guest name duplication:** Storage-level. Frontend sent doubled string. No backend duplication mechanism.
3. **QR 503:** `qrcode` library missing in staging container. `ImportError` caught, 503 returned.

### DB Evidence

| Table | Key | Value |
|-------|-----|-------|
| `booking_state` | `booking_id = "MAN-KPG-502-20260326-f360"` | `guest_name = "Sam LongieSam Longie"`, `status = "checked_in"` |
| `guests` | `id = "fbe72e04-103c-4d1e-8587-5c8327cafbfe"` | `full_name = "Sam LongieSam Longie"`, `identity_source = "document_scan"` |
| `tasks` | `task_id = "6688f6ee75ae38f6"` | Backend accepts ACKNOWLEDGED→COMPLETED (200 OK verified) |

### Open Remediation Items (for next phase)

| # | Item | Severity |
|---|------|----------|
| 1 | Frontend `task_id` persistence through booking merge | 🔴 Critical |
| 2 | `qrcode[pil]` dependency in staging | 🟡 Medium |
| 3 | Guest name input validation / duplicate-string guard | 🟡 Medium |
| 4 | Success screen QR vs raw URL hierarchy | 🟡 Medium |
