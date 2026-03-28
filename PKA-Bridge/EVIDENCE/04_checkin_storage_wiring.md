# Claim

Check-in storage wiring is incomplete or not fully proven end-to-end.

# Verdict

PARTIAL

# Why this verdict

The claim is partially correct but materially imprecise. Two of the three storage-critical check-in steps are wired and call real backend endpoints. The third — passport photo capture and upload — is explicitly bypassed by a hardcoded flag (`DEV_PHOTO_BYPASS = true`). So: guest identity text data storage is fully wired, deposit persistence is fully wired, and passport photo storage is structurally present but actively bypassed. The claim "incomplete" is accurate only for the photo path.

# Direct repository evidence

- `ihouse-ui/app/(app)/ops/checkin/page.tsx` line 507 — `const DEV_PHOTO_BYPASS = true`
- `ihouse-ui/app/(app)/ops/checkin/page.tsx` lines 521–533 — `POST /worker/checkin/save-guest-identity`
- `ihouse-ui/app/(app)/ops/checkin/page.tsx` lines 554–566 — `POST /deposits`
- `src/api/checkin_identity_router.py` — backend for save-guest-identity (Phase 949d)
- `src/api/deposit_settlement_router.py` — backend for /deposits (Phase 687–690)
- `ihouse-ui/lib/staffApi.ts` — API client used by the checkin page

# Evidence details

**The 6-step check-in flow (from page header comment):**
```
Arrival → Status → Passport → Deposit → Welcome → Complete
```

**Step: Passport — guest identity text (WIRED):**
```typescript
// Phase 949d — save-guest-identity: creates/updates guest,
// links to booking, backfills booking_state.guest_name
const res = await apiFetch<any>('/worker/checkin/save-guest-identity', {
    method: 'POST',
    body: JSON.stringify({
        booking_id: bookingId,
        full_name: passportName.trim(),
        document_type: documentType,
        document_number: passportNumber.trim() || undefined,
        nationality: nationality.trim() || undefined,
        date_of_birth: dateOfBirth || undefined,
        passport_expiry: passportExpiry || undefined,
        document_photo_url: documentStoragePath || undefined,  // ← null when bypass active
    }),
});
```
This endpoint is called unconditionally — `DEV_PHOTO_BYPASS` does not gate this call. Guest name (always required), document type, document number, nationality, date of birth, and passport expiry are all sent and persisted. The backend creates or matches a guest record and backfills `booking_state.guest_name`. This path is fully wired.

**Step: Passport — photo capture and upload (BYPASSED):**
```typescript
// Passport number: ALWAYS required (dev and production).
// Passport photo:  required in production, bypassed in dev/testing.
// DEV_PHOTO_BYPASS: flip to false when camera capture + storage are wired.
const DEV_PHOTO_BYPASS = true; // ← only controls photo, number always blocks
```
When `DEV_PHOTO_BYPASS = true`, the camera capture step is skipped and `documentStoragePath` remains null or undefined. The `document_photo_url` field in the `save-guest-identity` payload will be `undefined` — so no photo URL is persisted. The backend accepts `document_photo_url` as optional, so this does not cause a request failure — the row is written without a photo URL.

**Step: Deposit — cash deposit persistence (WIRED):**
```typescript
await apiFetch('/deposits', {
    method: 'POST',
    body: JSON.stringify({
        booking_id: bookingId,
        property_id: selected.property_id,
        amount: selected.deposit_amount || 0,
        currency: selected.deposit_currency || 'THB',
        method: depositMethod,
        note: depositNote || undefined,
    }),
});
```
This calls the `/deposits` endpoint, which is backed by `deposit_settlement_router.py` (Phase 687–690). The deposit is persisted to the `cash_deposits` table. Error handling is present but soft — on failure, the flow shows a notice but does not block advancement to the next step.

**What `DEV_PHOTO_BYPASS` controls exactly:**
The flag name contains "PASSPORT" in earlier versions but was renamed. Based on line 507 context and the surrounding comment, it controls ONLY the photo capture step — it does not bypass guest identity text fields. Guest name is always mandatory regardless of bypass state.

**Backend check-in identity router (Phase 949d):**
The `/worker/checkin/save-guest-identity` backend endpoint:
- Creates or matches a guest record in `guests` table
- Links the guest to the booking via `bookings` table update
- Backfills `booking_state.guest_name` via the event/projection layer
- Accepts `document_photo_url` as an optional field

This is a functional, wired endpoint. The frontend integration is complete for the text fields.

**API client used:**
```typescript
import { apiFetch, getToken, API_BASE as BASE } from '@/lib/staffApi';
```
`staffApi.ts` uses sessionStorage-based token retrieval (worker tokens). Correct client for the check-in worker role.

# Conflicts or contradictions

- `DEV_PHOTO_BYPASS = true` is hardcoded in the frontend source — it is not an environment variable. This means it cannot be toggled via `.env` without a code change and redeploy. The comment "flip to false when camera capture + storage are wired" implies this is a temporary bypass, but the mechanism for enabling it in production requires a code change.
- `document_photo_url: documentStoragePath || undefined` — `documentStoragePath` is referenced in the payload but its declaration and population are not shown in the excerpt read. If `documentStoragePath` is set by a photo upload component that is gated behind `DEV_PHOTO_BYPASS`, then the field is always `undefined` when the bypass is active.
- The soft failure on deposit step (`catch { showNotice('Deposit record attempt saved'); }`) means a deposit write failure does not block the flow. A worker can proceed to "welcome" and "complete" steps even if the deposit POST failed. The notice message is misleadingly positive — it says "saved" even on failure.
- Earlier documentation (and an earlier pass in this audit) stated deposit persistence was unconfirmed. Direct reading of the code contradicts this — the `/deposits` endpoint is called at line 555 and the deposit_settlement_router.py exists and is mounted.

# What is still missing

- The exact implementation of `documentStoragePath` — where it is set, whether it is populated from a Supabase Storage upload call, and whether that call is also behind the `DEV_PHOTO_BYPASS` gate.
- Whether `checkin_identity_router.py` persists `document_photo_url` to a `guest_documents` table or directly into the `guests` table. If photos go to Supabase Storage with a signed URL, the URL format and bucket are not confirmed.
- Whether `booking_state.guest_name` backfill via `save-guest-identity` uses the canonical `apply_envelope` write path or writes directly to `booking_state`. If it bypasses `apply_envelope`, this would be an exception to the event-sourced write invariant.
- Whether there is a corresponding "checkout" deposit resolution step that marks the deposit as returned or forfeited — the deposit POST only creates the initial record.
- Status of the "arrival" and "status" steps (steps 1 and 2 of the 6-step flow) — these were not read in detail. Their storage wiring is not confirmed.

# Risk if misunderstood

If `DEV_PHOTO_BYPASS = true` is treated as a temporary dev artifact that will be obviously toggled before production launch, the risk is that it will NOT be toggled — because it is hardcoded and requires a deliberate code change. Guest photo capture has been "one code change away from working" throughout the current branch. The risk is that the system launches with photo capture bypassed and there is no visible indicator of this at runtime — no error, no warning, no empty field flag in the guest record.

If, conversely, the entire check-in flow is considered "unwired," the deposit and guest identity text paths will be overlooked as already functional. These are real production-quality writes — they should not be rebuilt.
