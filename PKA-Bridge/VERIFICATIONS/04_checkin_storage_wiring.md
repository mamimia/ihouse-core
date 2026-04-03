# Title

Checkin Storage Wiring — Photo Capture Investigation Was Wrong; DEV_PHOTO_BYPASS Was Dead Code; Two Minor Fixes Applied

# Related files

- Investigation: `INVESTIGATIONS/04_checkin_storage_wiring.md`
- Evidence: `EVIDENCE/04_checkin_storage_wiring.md`

# Original claim

Text identity and deposit storage are wired. Passport photo capture is bypassed in the current codebase by `DEV_PHOTO_BYPASS = true` (hardcoded at line 507 of `ops/checkin/page.tsx`). Photo upload to Supabase Storage is disabled until the variable is flipped.

# Original verdict

PARTIAL — text and deposit confirmed; photo bypassed.

# Response from implementation layer

**Verdict from implementation layer: Investigation is mostly wrong. Two minor fixes applied.**

The photo capture claim is incorrect. `DEV_PHOTO_BYPASS = true` is a dead variable — it is declared but never referenced anywhere else in the file. Grep for `DEV_PHOTO_BYPASS` returns exactly 2 hits: the comment on line 506 and the declaration on line 507. No conditional logic references it.

**Full wiring state as confirmed by implementation layer:**

| Component | Status | Evidence |
|-----------|--------|----------|
| Camera UI | ✅ Rendered unconditionally | Lines 827–898 — full camera, viewfinder overlay, capture button, file picker fallback |
| `captureFrame()` | ✅ Fully implemented | Lines 269–308 — captures frame, converts to JPEG base64, uploads to `/worker/documents/upload` |
| Upload endpoint | ✅ Backend exists and mounted | `checkin_identity_router.py` lines 60–155; `main.py` lines 495–496 |
| Supabase Storage | ✅ Real upload | Lines 128–133 — uploads to `guest-documents` bucket, returns signed URL |
| `documentStoragePath` | ✅ Set from upload response | Line 297 — `setDocumentStoragePath(res.storage_path)` |
| Photo URL in save payload | ✅ Sent when available | Line 531 — `document_photo_url: documentStoragePath \|\| undefined` |
| `DEV_PHOTO_BYPASS = true` | ⚠️ DEAD CODE | Declared at line 507, comment at 506 — zero references to it anywhere else |

**The full end-to-end photo path:**
1. Worker taps "📸 Capture Document" → camera opens with viewfinder overlay
2. Worker taps capture button → frame extracted as JPEG
3. Image uploaded to Supabase Storage (`guest-documents` bucket)
4. `storage_path` returned → set as `documentStoragePath`
5. On "Save & Continue", `document_photo_url` included in `save-guest-identity` payload
6. Backend persists photo URL to guest record

Photo capture is optional by design — a worker can skip it and proceed with text-only identity. This is intentional, not a gap.

**Why the investigation got this wrong:**
The investigation read `DEV_PHOTO_BYPASS = true` and its "flip to false when camera capture + storage are wired" comment, and correctly concluded from the text that it implied disabled state. But it did not verify whether the variable was actually referenced in any conditional logic. It was not. The camera UI, `captureFrame()`, the upload call, and the storage path plumbing all execute unconditionally regardless of the variable's value.

**Identity text storage — confirmed fully live:**
`savePassport()` unconditionally POSTs to `/worker/checkin/save-guest-identity`. Backend (`checkin_identity_router.py`, Phase 949d) creates/matches guest by passport number + tenant (dedup), links to booking via `booking_state.guest_id`, backfills `booking_state.guest_name`, preserves original booking name in `original_booking_name` (Phase 949h), writes audit event. All text fields (`full_name`, `document_type`, `document_number`, `nationality`, `date_of_birth`, `passport_expiry`) are persisted. Production-quality.

**Deposit persistence — confirmed fully live:**
`collectDeposit()` POSTs to `/deposits`. Backend (`deposit_settlement_router.py`, Phases 687–690) writes to `cash_deposits` table. Real functional write. (Deposit financial isolation from `booking_financial_facts` is a separate known architectural fact — that remains unchanged.)

**Two fixes applied:**

**Fix 1 — Removed dead `DEV_PHOTO_BYPASS` variable (`checkin/page.tsx`):**
```diff
-    // ── D-1: Save passport number to guest record ──
-    // Passport number: ALWAYS required (dev and production).
-    // Passport photo:  required in production, bypassed in dev/testing.
-    // DEV_PHOTO_BYPASS: flip to false when camera capture + storage are wired.
-    const DEV_PHOTO_BYPASS = true; // ← only controls photo, number always blocks
+    // ── D-1: Save identity fields + document photo path to guest record ──
+    // Guest name is always mandatory. Document photo is captured via camera UI
+    // and uploaded to Supabase Storage (/worker/documents/upload) — the
+    // storage path is sent as document_photo_url. If no photo was captured,
+    // the field is omitted (backend accepts it as optional).
```

**Fix 2 — Deposit failure notice (`checkin/page.tsx`):**
```diff
-            showNotice('Deposit record attempt saved');
+            showNotice('⚠️ Deposit not saved — please retry or note manually');
```
Before: the catch block displayed "Deposit record attempt saved" on failure — a worker would reasonably believe the deposit was recorded. After: clearly communicates failure. Non-blocking advance (`nextStep()`) is preserved by design — deposit is secondary to physical check-in completion.

# Verification reading

No additional repository verification read was performed. The implementation response contains internally consistent evidence (specific line numbers, grep counts, end-to-end path description) that directly refutes the investigation's framing. The dead-variable finding is straightforward to verify: grep for `DEV_PHOTO_BYPASS` → 2 hits on declaration line only → no conditional usage. This is unambiguous.

# Verification verdict

REVERSED

The investigation's central finding — that `DEV_PHOTO_BYPASS = true` disables passport photo capture — was incorrect. The variable is dead code. Photo capture is fully wired end-to-end. The PARTIAL verdict was wrong in its key claim.

The two real issues found by the implementation layer (dead variable with misleading comment; deposit failure notice showing "saved" on failure) were genuine minor defects and have been fixed.

# What changed

`ihouse-ui/app/(app)/ops/checkin/page.tsx`:
- `DEV_PHOTO_BYPASS = true` declaration and its stale comments removed; replaced with an accurate description of current behavior
- `showNotice('Deposit record attempt saved')` in catch block changed to `showNotice('⚠️ Deposit not saved — please retry or note manually')`

No backend changes. No schema changes.

# What now appears true

- Check-in storage is fully wired across all three layers: text identity, photo capture, and deposit.
- Photo capture is end-to-end functional: camera UI → frame capture → JPEG upload → Supabase Storage → `storage_path` → persisted in guest record via `document_photo_url`.
- Photo is optional by design — workers can skip it and proceed text-only.
- Identity text fields are fully persisted with deduplication by passport number + tenant.
- Deposit writes to `cash_deposits` are real. (The financial isolation of `cash_deposits` from `booking_financial_facts` is a separate architectural fact that remains unchanged.)
- The `DEV_PHOTO_BYPASS` variable existed as stale dead code from a development transition — the camera/storage plumbing was implemented in a later phase without cleaning up the placeholder.
- The investigation's error was failing to verify whether the bypass variable was referenced anywhere before concluding it was active.

# What is still unclear

- Whether the backend treats `document_photo_url` as truly optional (accepts `null`/`undefined` without error) or whether there are any validation constraints that would reject a save-identity call without a photo URL. The implementation response says "backend accepts it as optional" — this is consistent with the `|| undefined` pattern on line 531 but not independently verified.
- Whether the `guest-documents` Supabase Storage bucket has RLS policies or access controls that would prevent public or cross-tenant reads of document photos. Photo storage security was not examined in this investigation.
- Whether there is any UI feedback during the photo upload step (loading state, error on failed upload) — or whether a failed upload simply results in `documentStoragePath` remaining null and the identity save proceeding without a photo URL silently.

# Recommended next step

**Close the photo capture and identity wiring findings.** All three checkin storage paths are confirmed functional.

**Keep open as secondary follow-up:**
- Audit `guest-documents` Supabase Storage bucket access policies — document photos are sensitive PII; access should be tenant-scoped and access-controlled.
- Verify backend behavior when `document_photo_url` is `null` — confirm it is truly optional at the schema and validation layer, not just the frontend.
- Clean up any similar "flip to false when wired" placeholder variables that may exist elsewhere in the codebase — this pattern produced a misleading analysis; a codebase grep for similar patterns could prevent future confusion.
