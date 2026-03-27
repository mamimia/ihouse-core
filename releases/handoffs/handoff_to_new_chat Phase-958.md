> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 958 (Worker Check-in Audit & Root-Cause Isolation)

**Date:** 2026-03-28
**Current Phase:** 959 — Next Phase
**Last Closed Phase:** 958 — Worker Check-in Audit & Root-Cause Isolation

---

## What Was Done Today (Phases 953–958)

### Phase 953 — Check-in Task Completion, Booking State Guard, Guest Dedup
- Fixed task completion endpoint allowing ACKNOWLEDGED→COMPLETED
- Fixed booking state guard rejecting `confirmed` status
- Fixed guest dedup creating orphan records

### Phase 954 — Check-in Authorization & Task Transition Fix
- **403 Fix:** `_assert_checkin_role` in `booking_checkin_router.py` now accepts `role="worker"` with `CHECKIN` capability
- **422 Fix:** `VALID_TASK_TRANSITIONS` in `task_model.py` updated: ACKNOWLEDGED can now directly transition to COMPLETED

### Phase 955 — Admin Manage Staff: Invite Button + Pending Approval Stat Box
- Renamed "Pending Requests" → "Invite Staff"
- Added "Pending Approval" stat box wired to real `/admin/staff-onboarding` count

### Phase 956 — Manage Staff Stat Box Visual Alignment
- Shared flexbox card system with `minHeight: 94px`

### Phase 957 — Global Theme Consistency
- Eliminated 3-way theme split-brain. Default = Light globally, Dark only via explicit toggle.

### Phase 958 — Worker Check-in Audit & Root-Cause Isolation (THIS SESSION)
**No code changes.** Evidence-based audit isolating 3 exact root causes:

| # | Failure | Root Cause |
|---|---------|-----------|
| 1 | Task stays ACKNOWLEDGED | Frontend `task_id` undefined after booking merge — PATCH silently skipped |
| 2 | Guest name doubled | Frontend sent `"Sam LongieSam Longie"` — backend stored as-is |
| 3 | QR returns 503 | `qrcode` library missing in staging container |

---

## 🔴 Open Remediation Items (Next Session)

| Priority | Item | File |
|----------|------|------|
| 🔴 Critical | `task_id` lost during booking merge | `ihouse-ui/app/(app)/ops/checkin/page.tsx` |
| 🟡 Medium | `qrcode` missing in staging | `requirements.txt` or `pyproject.toml` |
| 🟡 Medium | Guest name validation | `src/api/checkin_identity_router.py` |
| 🟡 Medium | Success screen QR display | `checkin/page.tsx` success step |
| 🟡 Medium | Deposit chain 500 | `POST /deposits` |

---

## Key Files

| File | Role |
|------|------|
| `src/api/worker_router.py` | Task transition endpoint (PATCH /worker/tasks/{id}/complete) — works correctly |
| `src/api/booking_checkin_router.py` | Check-in state transitions — patched in Phase 953-954 |
| `src/api/checkin_identity_router.py` | Guest identity save — writes exactly what frontend sends |
| `src/api/guest_checkin_form_router.py` | QR image generation — requires `qrcode` library |
| `src/tasks/task_model.py` | Task lifecycle model — ACKNOWLEDGED→COMPLETED now allowed |
| `ihouse-ui/app/(app)/ops/checkin/page.tsx` | Main check-in wizard UI — task_id regression here |
| `ihouse-ui/lib/staffApi.ts` | Worker API fetch helper |

---

## Deployment State

| Target | Status |
|--------|--------|
| GitHub | ✅ Pushed to `checkpoint/supabase-single-write-20260305-1747` |
| Railway (Backend) | ✅ Auto-deployed on push |
| Vercel (Frontend) | ✅ Deployed via `npx vercel --prod --yes` |
