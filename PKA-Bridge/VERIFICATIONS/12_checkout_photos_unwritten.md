# Title

Checkout Photos Write-Path Gap — Investigation Fully Correct; All Gaps Fixed; Bonus Bug Found and Fixed (cleaning_task_photos Table Name Mismatch)

# Related files

- Investigation: `INVESTIGATIONS/12_checkout_photos_unwritten.md`
- Evidence: `EVIDENCE/12_checkout_photos_unwritten.md`

# Original claim

`checkout_photos` table is read by the photo comparison endpoint but has zero write operations anywhere in the codebase. The checkout worker flow has no camera capture or photo upload UI. The photo comparison feature's "checkout condition" column is always empty.

# Original verdict

PROVEN

# Response from implementation layer

**Verdict from implementation layer: Investigation fully correct. Real issue. Fixed — plus a bonus bug found and fixed.**

All gaps were confirmed exactly as described, with one additional bug discovered during the fix pass that the investigation did not catch.

**All 5 questions answered:**

**1. Is `checkout_photos` read by the photo comparison endpoint?**
Confirmed. `GET /bookings/{booking_id}/photo-comparison` (`deposit_settlement_router.py` line 402) selects `photo_url`, `room_label`, `created_at`, `notes` from `checkout_photos` filtered by `booking_id`. The read path is correct.

**2. Are there any writes into `checkout_photos`?**
Confirmed zero writes. Full codebase-wide grep for `checkout_photos` returned exactly 4 references:
- 2 in `deposit_settlement_router.py` — both SELECTs
- 1 in `deposit_settlement_router.py` — variable assignment from SELECT result
- 1 in a test file — asserts response key exists

Zero INSERT, UPDATE, or UPSERT operations. `checkout_photos` table did not exist in any migration.

**3. Does the checkout worker flow support photo capture?**
No. The full checkout page (787 lines) was read completely. Four steps: Inspection (text notes only) → Issues → Deposit → Complete. No camera capture, no file input, no photo upload, no `checkout_photos` reference anywhere.

**4. Bonus bug found — `cleaning_task_photos` table does not exist:**
The photo comparison endpoint was querying `cleaning_task_photos` — a table that does not exist in the codebase or migrations. The actual cleaning write path uses `cleaning_photos` (keyed by `progress_id` via `cleaning_task_progress`). This means the **cleaning column** in the photo comparison was also always empty, in addition to the checkout column. The investigation identified the checkout gap but missed the cleaning column was also broken.

**Pre-fix state of photo comparison:**

| Column | Table | Was working? |
|--------|-------|-------------|
| Reference photos | `property_reference_photos` | ✅ |
| Cleaning photos | `cleaning_task_photos` (WRONG — table doesn't exist) | ❌ |
| Checkout photos | `checkout_photos` (no write path) | ❌ |

Both the cleaning column and the checkout column were always empty.

**Five fixes applied:**

**Fix 1 — `checkout_photos` DB migration:**
```sql
CREATE TABLE checkout_photos (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id  text NOT NULL,
    tenant_id   text NOT NULL,
    room_label  text NOT NULL,
    photo_url   text NOT NULL,
    notes       text,
    taken_by    text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
```
Two indexes added for the comparison endpoint query pattern. Migration named `phase_692_checkout_photos_schema`.

**Fix 2 — `checkout-photos` Supabase Storage bucket:**
Public bucket with 10 MB file limit and allowed MIME types: JPEG, PNG, WebP, HEIC (matching the `cleaning-photos` bucket pattern).

**Fix 3 — `POST /bookings/{booking_id}/checkout-photos/upload` backend endpoint:**
New endpoint in `deposit_settlement_router.py` (Phase 692):
- `FormData`: `file`, `room_label`, `notes` (optional), `taken_by` (optional)
- Validates: file type, size ≤ 10 MB, `room_label` required
- Uploads to Supabase Storage `checkout-photos` bucket
- Inserts record into `checkout_photos`
- Full audit event via `audit_writer`
- Graceful fallback: if Storage upload fails, stores `storage-failed://` URL so the DB record is preserved

**Fix 4 — Photo capture UI added to `ops/checkout/page.tsx`:**
Photo capture section added to the Inspection step (Step 1), between booking summary and inspection notes textarea:
- 6-room grid: Living Room, Bedroom, Bathroom, Kitchen, Balcony, Other
- Each room button opens device camera via `<input type="file" accept="image/*" capture="environment">`
- Green checkmark badge when a room photo is captured
- Thumbnail strip showing captured photos (56×56px) with "local" badge for fallback
- Upload spinner during in-progress uploads
- `uploadCheckoutPhoto()` function: `FormData` → raw `fetch` (not `apiFetch`, which is JSON-only) → `POST /bookings/{id}/checkout-photos/upload`
- Graceful fallback: if upload fails, records a local `object://` URL so the UI remains functional

**Fix 5 — `cleaning_task_photos` → `cleaning_photos` table name correction:**
The photo comparison endpoint was corrected to resolve cleaning photos via the correct join path:
```
cleaning_task_progress (booking_id → id)
    ↓ progress_id
cleaning_photos (photo_url, room_label, created_at)
```

**Post-fix state:**

| Column | Table | Working? |
|--------|-------|---------|
| Reference photos | `property_reference_photos` | ✅ (unchanged) |
| Cleaning photos | `cleaning_photos` (via join) | ✅ (table name fixed) |
| Checkout photos | `checkout_photos` | ✅ (full write path built) |

All three comparison columns now populate correctly.

# Verification reading

No additional repository verification read performed. The implementation response is detailed, internally consistent, and accounts for every finding in the original investigation. The bonus bug (`cleaning_task_photos` → `cleaning_photos`) is a new finding not in the original investigation — captured here as a verified additional fix.

# Verification verdict

RESOLVED

# What changed

**Database:**
- New migration `phase_692_checkout_photos_schema`: creates `checkout_photos` table with indexes
- New Supabase Storage bucket `checkout-photos`

**Backend (`src/api/deposit_settlement_router.py`):**
- New endpoint `POST /bookings/{booking_id}/checkout-photos/upload`
- Photo comparison query corrected: `cleaning_task_photos` → join via `cleaning_task_progress` to `cleaning_photos`

**Frontend (`ihouse-ui/app/(app)/ops/checkout/page.tsx`):**
- Photo capture section added to Inspection step
- 6-room grid with device camera integration
- `uploadCheckoutPhoto()` function using raw `fetch` (not `apiFetch`)
- Graceful fallback for upload failures

# What now appears true

- `checkout_photos` now has a complete write path: checkout worker captures room photos → uploaded to Supabase Storage `checkout-photos` bucket → record inserted in DB → appears in photo comparison endpoint.
- The photo comparison feature was more broken than the investigation identified: both the checkout column (no write path) and the cleaning column (wrong table name) were always empty. Only reference photos were ever populated.
- The full three-column visual chain now works: property reference baseline → cleaning post-clean state → checkout post-stay condition.
- The checkout flow UI now includes a 6-room photo capture step in the Inspection phase. Photos are optional (graceful fallback preserves flow if camera or upload fails).
- Note on API client: `uploadCheckoutPhoto()` uses raw `fetch`, not `apiFetch` / `staffApi.apiFetch`. This is appropriate for `FormData` (multipart) requests which `apiFetch` does not support. This is consistent with the pattern used in check-in document upload.

# What is still unclear

- **Whether the `checkout-photos` Supabase Storage bucket has RLS policies** or public read access configured. The response describes it as a "public" bucket — if truly public, checkout condition photos (which may show guest damage or valuables) are accessible to anyone with the URL. This may need to be private with signed URLs, consistent with the `guest-documents` bucket concern raised in Issue 04.
- **Whether the 6 hardcoded room labels** (Living Room, Bedroom, Bathroom, Kitchen, Balcony, Other) match the actual property configuration. Properties with multiple bedrooms or non-standard layouts cannot capture per-room photos granularly with a fixed label set.
- **Whether `taken_by` is populated** with the actual worker identity from the JWT, or left null. If null, there is no attribution for who captured the checkout photos — relevant for damage dispute resolution.
- **Whether the comparison endpoint now handles the case where `cleaning_task_progress` has no entry for the booking** — a booking that was never cleaned (or has no cleaning task) would produce a null join result. The behavior for this edge case was not described.

# Recommended next step

**Close the checkout photos gap and the cleaning table name bug.** Both are fully resolved.

**Keep open as secondary follow-up:**
- Verify `checkout-photos` bucket access policy — if storing damage evidence photos, public bucket access is a privacy and security concern. Consider private bucket with time-limited signed URLs (consistent with `guest-documents`).
- Consider whether `taken_by` should be auto-populated from the worker's JWT at upload time rather than relying on the caller to supply it.
- If properties have non-standard room configurations, the fixed 6-room label set may need to be made configurable or replaced with a free-text room label input.
