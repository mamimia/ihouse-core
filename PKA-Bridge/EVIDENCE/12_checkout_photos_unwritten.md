# Claim

The `checkout_photos` table is read by the photo comparison endpoint but has no confirmed write path anywhere in the codebase.

# Verdict

PROVEN

# Why this verdict

`src/api/deposit_settlement_router.py` reads from `checkout_photos` at line 335 for the `GET /bookings/{booking_id}/photo-comparison` endpoint. A full-codebase grep for `checkout_photos` returns only three results: that read, a variable assignment from it, and a test assertion checking the response key exists. There is no Python code that inserts into or writes to `checkout_photos`. The checkout page frontend (`ops/checkout/page.tsx`) has no photo upload logic visible in the portion read. The table can never be populated through the current application code.

# Direct repository evidence

- `src/api/deposit_settlement_router.py` lines 333–341 — read from `checkout_photos`
- Codebase-wide grep: only 3 references to `checkout_photos` — all reads or tests, no writes
- `ihouse-ui/app/(app)/ops/checkout/page.tsx` — no photo upload in the portion read
- `tests/test_wave6_checkout_deposit_contract.py` line 85 — test asserts key exists in response

# Evidence details

**The read (lines 333–341):**
```python
checkout = (
    db.table("checkout_photos").select("photo_url, room_label, created_at, notes")
    .eq("booking_id", booking_id)
    .order("created_at")
    .execute()
)
checkout_photos = checkout.data or []
```
Reads from `checkout_photos` filtered by `booking_id`. Returns an array (always empty in practice).

**Full grep results for `checkout_photos`:**
```
src/api/deposit_settlement_router.py:335 — SELECT from checkout_photos
src/api/deposit_settlement_router.py:340 — variable assignment
tests/test_wave6_checkout_deposit_contract.py:85 — assertIn("checkout_photos", body)
```
Zero INSERT, UPDATE, or UPSERT operations anywhere in the Python codebase.

**The photo comparison feature cannot work:**
`GET /bookings/{booking_id}/photo-comparison` is designed to show three photo categories side by side: reference photos (from `property_reference_photos`), cleaning photos (from `cleaning_task_photos`), and checkout condition photos (from `checkout_photos`). The third category is always empty.

# Conflicts or contradictions

- The endpoint exists and is called from a test that asserts the `checkout_photos` key exists in the response. The test passes because the endpoint returns an empty array — not because photos are present.
- The photo comparison concept implies a workflow where a checkout worker photographs the property condition. This workflow does not exist in the current backend or frontend.

# What is still missing

- Whether the `checkout_photos` table itself is defined in any migration (table structure exists but may be empty).
- Whether the checkout page frontend, in portions not read, has a photo upload call to an endpoint that writes to `checkout_photos`.
- Whether a mobile-specific upload endpoint (e.g., `POST /bookings/{id}/checkout-photos`) exists but was not discovered.

# Risk if misunderstood

If the photo comparison feature is presented to operators as functional, they will attempt to use it for checkout damage documentation and find no photos. The deposit deduction workflow that may reference `photo_url` in the `deposit_deductions` table is a separate system — but a checkout worker taking condition photos via the comparison feature will produce no usable output.
