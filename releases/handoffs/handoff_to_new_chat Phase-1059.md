# Handoff to New Chat — Phase 1059
**Phase:** 1059 — Operational Resilience Hardening (Photo Upload + Wizard State Recovery)
**Status:** CLOSED
**Date:** 2026-04-04
**Commit:** `a6e8bdb` — Branch: `checkpoint/supabase-single-write-20260305-1747`

---

## What Was Done

Closed the two grouped deferred items:
1. **Offline / photo-upload failure chain**
2. **No saga / compensation / recovery model for multi-step operational wizards**

Both were treated as related: both concern operational resilience under interruption or failure.

---

## Changes Delivered

### 1. DB Migration — `phase_1059_upload_status_hardening`
Applied to Supabase project `reykggmlcehswrxjviup`:

- `cleaning_photos`: added `upload_status TEXT NOT NULL DEFAULT 'confirmed' CHECK (IN ('confirmed','failed','pending'))` and `storage_path TEXT`
- `booking_checkin_photos`: added `upload_status TEXT NOT NULL DEFAULT 'confirmed'`
- Indexes: `idx_cleaning_photos_upload_status`, `idx_booking_checkin_photos_upload_status` (partial, WHERE != 'confirmed')
- All existing rows default to 'confirmed' — backward compatible

### 2. Backend: `src/api/cleaning_task_router.py`
**Endpoint:** `POST /tasks/{task_id}/cleaning-photos/upload`

- **BEFORE:** Storage failure → silently writes `storage-failed://...` URL to DB. DB record exists, but bytes are permanently lost.
- **AFTER:** Storage failure → HTTP 502 `STORAGE_UPLOAD_FAILED` with structured error. No DB record created. Caller must retry.
- Successful upload now writes `upload_status='confirmed'` and `storage_path` explicitly.

### 3. Backend: `src/api/checkin_photos_router.py`
Two changes:

**POST /worker/bookings/{booking_id}/checkin-photos:**
- Now writes `upload_status='confirmed'` on every row inserted into `booking_checkin_photos`

**NEW: GET /worker/bookings/{booking_id}/checkin-resume** (Phase 1059):
- Returns durable wizard state for a booking: `booking_status`, saved photos (total / confirmed / failed / by purpose), settlement (deposit + meter), guest identity (saved/not + name), `resume_hint` (human-readable step suggestion)
- Each sub-query is individually try/except — endpoint degrades gracefully if any table is unavailable
- Auth: same roles as checkin-photos (worker, checkin, ops, admin, manager)

### 4. Frontend: `ihouse-ui/app/(app)/ops/checkin/page.tsx`
Four operational improvements:

**a) Explicit failed-upload tracking (state)**
- New: `failedPhotoUploads: Record<string, string>` — maps room_label → error message
- On upload success: clears the error for that room
- On upload failure: writes structured error (instead of a toast that disappears after 3 sec)

**b) Persistent failed-upload UI callout**
- When any `failedPhotoUploads` entries exist: red bordered callout with room name + truncated error message + "retake" instructions
- Continue button is **disabled** while any failed upload is present — worker must retake before proceeding
- Previous warning banner (optional) now only shows when no hard failures exist

**c) sessionStorage wizard persistence**
- `useEffect` on `[capturedPhotos, step, selected]`: writes `{ bookingId, capturedPhotos, step, savedAt }` to `sessionStorage.ihouse_checkin_wizard_{bookingId}`
- When `startCheckin(b)` is called: attempts to restore `capturedPhotos` from sessionStorage if `bookingId` matches
- Cleared on: `completeCheckin` success, `returnToList` explicit return
- Scope: tab/session only (not cross-device)

**d) 'In Progress' resume banner**
- `BookingCardList` now reads sessionStorage per booking_id on render
- Cards with a non-empty saved `capturedPhotos` array show an amber banner: "🔄 In Progress — tap Start to resume where you left off"

---

## What Is Still Deferred (Documented Residual Risks)

| Risk | Status | Reason |
|------|--------|---------|
| Service Worker + IndexedDB offline queuing | Deferred | Requires infra change — no SW setup |
| Multi-device wizard resume across devices | Deferred | sessionStorage is tab-scoped by design |
| Guest token issuance failure (non-blocking) | Known gap | Intentionally best-effort |
| Session invalidation (existing JWT after deactivation) | Known gap | Intentional deferred |
| `booking_checkin_photos` + `cleaning_photos` missing RLS | Pre-existing | Both accessed only via service_role_key backend |

---

## Test Results
- **0 new failures** introduced
- Pre-existing 52 failures (wave7/wave5/task model/router/system) unchanged
- `test_booking_checkin_checkout.py` + `test_checkin_role_guard.py`: ✅ 45 passing
- TypeScript: `tsc --noEmit` clean

---

## System State After This Phase

- **Backend on Railway:** auto-deployed via `git push` (`a6e8bdb`)
- **Frontend:** NOT yet deployed to Vercel (no `/vercel-staging-deploy` invoked — no frontend-only visible change requiring staging review)
- **DB migration:** applied to production Supabase project `reykggmlcehswrxjviup`

---

## For the Next Chat

1. Read `docs/core/BOOT.md` and `docs/core/work-context.md` as always
2. Check `docs/core/current-snapshot.md` for system state
3. The deferred items registry now has these two items closed: `offline_photo_upload_failure` + `wizard_no_saga`
4. Candidate next items: wizard state recovery for checkout flow (same pattern), or next in deferred registry
