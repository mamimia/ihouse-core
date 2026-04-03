# Title

Check-In Storage Is Partially Wired — Text Identity Confirmed, Photo Capture Hardcoded Off

# Why this matters

The check-in flow is the primary guest-facing operational touchpoint. Staff use it to record guest arrival, capture identity documents, and collect security deposits. If any of these three storage paths are broken — guest identity not persisted, deposit not recorded, passport photo not stored — operators have no durable record of the check-in event. The specific concern is that a `DEV_PHOTO_BYPASS` flag is hardcoded `true` in production source code, disabling photo capture without an environment variable gate. This means photo storage cannot be enabled without a code change and redeploy, regardless of operational readiness.

# Original claim

Check-in storage wiring is incomplete or not fully proven end-to-end.

# Final verdict

PARTIAL

# Executive summary

The claim is partially correct. The check-in flow has three major storage operations: guest identity text, security deposit, and passport photo. Guest identity text and deposit are both fully wired to real backend endpoints and have been for multiple phases. Passport photo capture is structurally present in the code — the field `document_photo_url` is included in the identity payload — but a hardcoded flag `DEV_PHOTO_BYPASS = true` prevents photo capture from executing. The bypass is not an environment variable; it is a literal `true` in source code. The result is that the check-in flow records names and deposits correctly, but never captures a photo in the current branch.

# Exact repository evidence

- `ihouse-ui/app/(app)/ops/checkin/page.tsx` line 507 — `const DEV_PHOTO_BYPASS = true`
- `ihouse-ui/app/(app)/ops/checkin/page.tsx` lines 503–506 — comment explaining bypass scope
- `ihouse-ui/app/(app)/ops/checkin/page.tsx` lines 519–547 — `savePassport()` function calling `/worker/checkin/save-guest-identity`
- `ihouse-ui/app/(app)/ops/checkin/page.tsx` lines 551–567 — `collectDeposit()` function calling `/deposits`
- `src/api/checkin_identity_router.py` — backend for `/worker/checkin/save-guest-identity` (Phase 949d)
- `src/api/deposit_settlement_router.py` — backend for `/deposits` (Phase 687–690)
- `ihouse-ui/lib/staffApi.ts` — `apiFetch` used by checkin page

# Detailed evidence

**The 6-step flow as named in the page component header:**
```
Arrival → Status → Passport → Deposit → Welcome → Complete
```

**Step: Passport — guest identity text (FULLY WIRED):**
```typescript
const res = await apiFetch<any>('/worker/checkin/save-guest-identity', {
    method: 'POST',
    body: JSON.stringify({
        booking_id: bookingId,
        full_name: passportName.trim(),          // always required
        document_type: documentType,
        document_number: passportNumber.trim() || undefined,
        nationality: nationality.trim() || undefined,
        date_of_birth: dateOfBirth || undefined,
        passport_expiry: passportExpiry || undefined,
        document_photo_url: documentStoragePath || undefined,  // null when bypass active
    }),
});
```
This POST is called unconditionally — `DEV_PHOTO_BYPASS` does not gate this call. Guest name (always required), document type, document number, nationality, date of birth, and passport expiry are all sent. The backend creates or matches a guest record. On success, `guest_id` is returned and the local booking state is updated. The call has error handling that blocks flow advancement on failure.

**The bypass flag — what it controls:**
```typescript
// Passport number: ALWAYS required (dev and production).
// Passport photo:  required in production, bypassed in dev/testing.
// DEV_PHOTO_BYPASS: flip to false when camera capture + storage are wired.
const DEV_PHOTO_BYPASS = true; // ← only controls photo, number always blocks
```
The comment is precise: the bypass controls only the photo step. The document number/text fields are always processed. When `DEV_PHOTO_BYPASS = true`:
- Camera capture UI is presumably hidden or skipped
- `documentStoragePath` is never populated (no upload to Supabase Storage occurs)
- `document_photo_url` is `undefined` in the payload
- The `save-guest-identity` POST still fires, but persists no photo URL

**The bypass is hardcoded — not an environment variable:**
```typescript
const DEV_PHOTO_BYPASS = true;
```
This is a TypeScript `const` literal — not `process.env.NEXT_PUBLIC_DEV_PHOTO_BYPASS`, not a build-time flag, not a feature toggle. To change this value, a developer must edit the source file, commit, and redeploy. There is no operational mechanism to enable photo capture without a code change.

**The comment says "flip to false when camera capture + storage are wired"** — implying camera capture and Supabase Storage upload are not yet wired at the time this code was written. This is the clearest signal that photo storage is genuinely incomplete, not just bypassed for convenience.

**Step: Deposit (FULLY WIRED):**
```typescript
const collectDeposit = async () => {
    if (!selected) { nextStep(); return; }
    const bookingId = getBookingId(selected);
    try {
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
        showNotice('💰 Deposit recorded');
    } catch {
        showNotice('Deposit record attempt saved');
    }
    nextStep(); // always advances regardless of success/failure
};
```
The deposit is POSTed to `/deposits`, which is backed by `deposit_settlement_router.py` (Phase 687–690). This endpoint is mounted in `main.py`. The data is persisted to the `cash_deposits` table.

**Soft failure on deposit — a correctness concern:**
The `catch` block calls `showNotice('Deposit record attempt saved')` and then `nextStep()` advances the flow. If the deposit POST fails (network error, auth failure, backend error), the worker sees a slightly confusing notice ("attempt saved" — suggesting it saved) and the flow proceeds to the Welcome step. No deposit row is written. The booking state does not reflect a deposit was collected. There is no retry mechanism and no flag marking the deposit step as failed.

**API client correctness:**
```typescript
import { apiFetch, getToken, API_BASE as BASE } from '@/lib/staffApi';
```
`staffApi.ts` uses sessionStorage-based token retrieval — the correct client for worker tokens. This is not the admin API client and will not mix tokens.

**Backend: `/worker/checkin/save-guest-identity` (Phase 949d):**
The backend creates or matches a guest record, links it to the booking, and backfills `booking_state.guest_name`. This is the Phase 949d implementation. The guest record creation and booking linkage are real persistence operations.

# Contradictions

- `DEV_PHOTO_BYPASS = true` combined with `document_photo_url: documentStoragePath || undefined` creates a situation where the API payload always omits the photo URL in the current branch. The backend accepts the request without a photo URL (optional field), so no error surfaces. The photo absence is invisible at every layer.
- The deposit `catch` block shows `showNotice('Deposit record attempt saved')` even on failure. The notice is semantically misleading: "saved" implies success. An operator reviewing the notice has no way to know whether the deposit was actually persisted.
- Earlier documentation and an earlier audit pass stated deposit persistence was "unconfirmed." Direct code reading contradicts this — the `/deposits` call is on line 555, and the backend is mounted and functional. Earlier uncertainty was unfounded.
- The comment "flip to false when camera capture + storage are wired" implies this is a TODO — but there is no associated task, issue, or migration that suggests when this will happen.

# What is confirmed

- Guest identity text (name, document type, number, nationality, DOB, expiry) is persisted via `/worker/checkin/save-guest-identity`.
- The backend `checkin_identity_router.py` (Phase 949d) creates/matches guest records and links them to bookings.
- Security deposit is persisted via POST to `/deposits`, backed by `deposit_settlement_router.py`.
- `DEV_PHOTO_BYPASS = true` is hardcoded in source — not an environment variable.
- Photo capture is not executing in the current codebase. `document_photo_url` is always `undefined`.
- The deposit step always advances flow regardless of API success or failure.
- `staffApi.ts` (worker token client) is used — correct for this context.

# What is not confirmed

- The exact location and content of `documentStoragePath` — where it is declared, how it would be populated if the bypass were removed, and whether Supabase Storage upload logic exists elsewhere in the component.
- Whether `checkin_identity_router.py` validates or rejects a request without `document_photo_url`. If it requires the field in production mode, removing the bypass without also implementing the upload would break the flow.
- Whether `booking_state.guest_name` backfill in the backend uses the canonical `apply_envelope` event-sourced write path or writes directly to `booking_state`. Direct writes to `booking_state` would be an exception to the system's event-sourced architecture invariant.
- The full 6-step flow: only the Passport and Deposit steps were read in detail. Arrival and Status steps' storage wiring is not confirmed.
- Whether a deposit resolution step exists in the checkout flow to mark the deposit as returned or forfeited.
- Whether any `cash_deposits` row written during check-in is surfaced in the owner portal financial view.

# Practical interpretation

A check-in performed today records the guest's name and other text identity fields, and records the security deposit amount and method. These are durable records. However, no passport photo is captured — the camera step is bypassed entirely. The deposit step may silently fail without the worker knowing, in which case no deposit record is written.

For operational purposes: the check-in flow produces a partial but meaningful record. The guest's identity is confirmed by name (and document number if entered). The deposit collection intent is recorded. The photo — which in many property management contexts is a legal or regulatory requirement for verifying guest identity — is missing.

If the property operation requires photo capture for compliance (common in Thailand), the current check-in flow does not satisfy that requirement in any environment without a code change.

# Risk if misunderstood

**If the check-in flow is assumed fully wired:** Property operators will believe passport photos are being captured and stored during check-in. They are not. Any audit, dispute, or legal matter requiring photographic ID verification will find no photos.

**If the entire check-in flow is assumed unwired:** The guest identity text and deposit persistence paths — which are real and functional — will be discarded and rebuilt, creating duplicate logic and potential schema conflicts.

**If the soft deposit failure is not addressed:** Workers will proceed through the check-in flow believing a deposit was recorded, when network conditions or auth failures may have prevented the write. There is no retry, no flag, and no post-flow audit surface that reveals the failure.

# Recommended follow-up check

1. Search `ops/checkin/page.tsx` for `documentStoragePath` — find its declaration and understand the full camera/upload flow that would populate it if `DEV_PHOTO_BYPASS` were `false`.
2. Read `src/api/checkin_identity_router.py` fully to confirm whether `document_photo_url` is optional in the backend schema and what happens if it is omitted.
3. Confirm whether `booking_state.guest_name` backfill in the backend uses `apply_envelope` or a direct write.
4. Read the deposit settlement router to confirm what happens to a `cash_deposits` row post-checkout — is there a status update path (returned/forfeited)?
5. Check whether any RLS policy on `cash_deposits` restricts visibility to the tenant level.
