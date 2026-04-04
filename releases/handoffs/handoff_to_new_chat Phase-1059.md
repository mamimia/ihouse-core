# Handoff to New Chat — Phase 1059
**Phase:** 1059 — Operational Resilience Hardening (Photo Upload + Wizard State Recovery)
**Status:** CLOSED (see classification notes below — not all items were fully closed)
**Date:** 2026-04-04
**Commits:** `a6e8bdb`, `989cf78` — Branch: `checkpoint/supabase-single-write-20260305-1747`

---

## Context

This phase attacked two grouped deferred items:

1. **Offline / photo-upload failure chain**
2. **No saga / compensation / recovery model for multi-step operational wizards**

Both concern operational resilience under interruption or failure.

> ⚠️ **Classification notice:** Both items were worked on in this phase. Neither is fully closed.
> The work delivered is real and valuable. The labels below reflect actual delivery state honestly.

---

## Item 1 — Photo Upload Failure Chain

**Classification: SUBSTANTIALLY HARDENED. Residual risk reduced. Not fully closed.**

### What was fixed

**Backend: `cleaning_task_router.py`**
- The root silent-failure bug is fixed: Storage upload failure now returns HTTP 502 `STORAGE_UPLOAD_FAILED` instead of silently writing a broken `storage-failed://…` pseudo-URL to the DB.
- A DB photo record is only created when bytes are confirmed in Supabase Storage.
- `upload_status='confirmed'` and `storage_path` written explicitly on success.

**DB migration: `phase_1059_upload_status_hardening`**
- `cleaning_photos`: added `upload_status` (`confirmed`/`failed`/`pending`), `storage_path`
- `booking_checkin_photos`: added `upload_status`
- Indexes for fast "find failed uploads" queries
- All existing rows default to `confirmed` (backward-compatible)

**Backend: `checkin_photos_router.py`**
- `POST /worker/bookings/{id}/checkin-photos`: now writes `upload_status='confirmed'` per row

**Frontend: `checkin/page.tsx`**
- `failedPhotoUploads` state: per-room explicit failure tracking (not a disappearing toast)
- Persistent red callout with exact error message and retry instructions
- Continue button disabled while any upload failure is present
- Photo upload handler clears failure state on retry before attempting

### What remains open (residual risk)

- **`/worker/documents/upload` upstream byte loss is not addressed.** If that endpoint's internal Supabase Storage write fails, the current code returns a `storage_path` but no `upload_status` field. The checkin wizard trusts that path blindly.
- **No Service Worker / IndexedDB offline queuing.** If the device goes fully offline mid-upload, the bytes are lost. No background retry, no offline queue.
- **Cleaning photo path only fully hardened.** The check-in wizard upload path (`/worker/documents/upload`) does not yet return `upload_status` — it is not under the same explicit failure contract.
- **No server-side retry / idempotent re-upload endpoint.** A worker who gets a 502 must re-capture the photo from scratch; there is no "re-submit bytes for a known failed record" flow.

---

## Item 5 — No Saga / Compensation / Recovery Model for Multi-Step Wizards

**Classification: NOT CLOSED. Partially mitigated for one narrow failure mode (check-in browser refresh). Broader saga / compensation gap still open.**

### What was actually delivered (the mitigation, not a close)

**Backend: `GET /worker/bookings/{id}/checkin-resume`** (new endpoint)
- Returns durable state for a check-in wizard session: `booking_status`, saved photos (confirmed vs failed by purpose), settlement (deposit + meter), guest identity (boolean + name), `resume_hint` (human-readable step suggestion)
- Allows a worker to know what durable steps have been committed to the backend
- Auth: same roles as checkin-photos

**Frontend: sessionStorage wizard persistence**
- `capturedPhotos` + current `step` saved to `sessionStorage` per `booking_id` on every change
- On re-entering the same booking's wizard: `capturedPhotos` restores from sessionStorage
- "🔄 In Progress — tap Start to resume where you left off" amber badge on cards with a saved checkpoint
- sessionStorage cleared on successful completion and explicit `returnToList`

### What this does NOT provide

This is a narrow mitigation for one specific failure mode: **browser refresh or tab close mid-wizard**. It is not a saga or compensation model.

**What a real saga / compensation model would require:**
- A backend-owned, durable "wizard_state" or "wizard_draft" table that persists the entire wizard context (not just photos) — deposit amount, identity fields, contact info, step — independent of browser
- Explicit step atomicity: each wizard step either fully succeeds (backend state updated) or is cleanly rolled back (no partial record leakage)
- Compensation logic: if step N fails after step N-1 succeeded, a defined rollback or idempotent-overwrite path exists
- Resume from the exact failed step, not from the beginning
- Multi-device aware: worker can pick up on a different device

**Specific gaps that remain open:**
- If the backend `POST /checkin` call fails after identity was already saved, deposit saved, and photos indexed — there is no compensation. The booking state is inconsistent. Worker must manually recover.
- The checkout wizard has none of these mitigations at all. Same underlying exposure.
- `capturedPhotos` in sessionStorage is tab-scoped — a different browser, device, or app restart loses it.
- The `checkin-resume` endpoint is a read-only diagnostic. It does not drive the wizard forward, does not restore step number, and does not restore non-photo fields (deposit method, identity form values, meter reading text).
- There is no transactional wrapper across the multiple `apiFetch` calls in `completeCheckin`. Any one of them failing produces an inconsistent partial state with no rollback.

---

## What Was Actually Fixed in This Phase (Summary)

| Item | What Changed | Honest State |
|------|-------------|--------------|
| Cleaning photo Storage failure | HTTP 502 instead of silent broken DB record | ✅ Fixed |
| Cleaning photo DB record integrity | Only written when bytes confirmed | ✅ Fixed |
| `upload_status` column on photo tables | Both tables — default 'confirmed', indexed | ✅ Added |
| Check-in upload failure UI | Persistent callout, Continue disabled, retry clears | ✅ Fixed |
| Check-in wizard tab-close recovery | sessionStorage per-booking, capturedPhotos restored | ✅ Mitigated (tab-scoped) |
| Resume diagnostic endpoint | `GET /checkin-resume` — read-only status | ✅ Added |
| `/worker/documents/upload` failure contract | No change made | 🔲 Still open |
| Offline photo queuing | Not implemented | 🔲 Still open |
| Checkout wizard resilience | No change made | 🔲 Still open |
| Wizard saga / compensation model | Not implemented | 🔲 Still open |
| Backend wizard_draft persistence | Not implemented | 🔲 Still open |
| Cross-step rollback / compensation | Not implemented | 🔲 Still open |

---

## Test Results
- **0 new failures** introduced
- Pre-existing 52 failures (wave7/wave5/task model/router/system) unchanged
- `test_booking_checkin_checkout.py` + `test_checkin_role_guard.py`: ✅ 45 passing
- TypeScript: `tsc --noEmit` clean

---

## System State After This Phase

- **Backend on Railway:** auto-deployed via `git push` (`a6e8bdb`)
- **Frontend:** No Vercel deploy performed (no UI-only visible change requiring staging review)
- **DB migration:** Applied to production Supabase project `reykggmlcehswrxjviup`

---

## For the Next Chat

1. Read `docs/core/BOOT.md` and `docs/core/work-context.md` as always
2. Phase 1059 closed with partial delivery — the honest open items above should be re-evaluated for prioritization
3. Strongest remaining gaps from this work: saga/compensation model (item 5 still open), `/worker/documents/upload` failure contract, checkout wizard resilience
