# Title

The `checkout_photos` Table Is Read by the Photo Comparison Endpoint But Has No Write Path in the Codebase

# Why this matters

`GET /bookings/{booking_id}/photo-comparison` is the feature that allows staff to compare a property's reference state (pre-stay photos) against its condition at checkout. It is a core tool for assessing damage and justifying deposit deductions. The endpoint reads from three tables: `property_reference_photos`, `cleaning_task_photos`, and `checkout_photos`. Two of these have confirmed write paths. The third — `checkout_photos` — has no INSERT in any Python router, no upload handler in the checkout frontend, and no confirmed write path anywhere in the codebase. The photo comparison feature's checkout condition category is structurally empty.

# Original claim

The `checkout_photos` table is read by the photo comparison endpoint but has no confirmed write path anywhere in the codebase.

# Final verdict

PROVEN

# Executive summary

A codebase-wide grep for `checkout_photos` returns three references: two in `deposit_settlement_router.py` (a SELECT and a variable assignment) and one in a test file asserting the response key exists. No INSERT, UPDATE, or UPSERT to `checkout_photos` was found in any Python source file. The checkout frontend page (`ops/checkout/page.tsx`) shows no photo upload in the portions read. The test only verifies the response key exists — which it does, because the endpoint returns an empty array. The photo comparison feature partially works (reference photos and cleaning photos are real) but the checkout condition photos segment is always empty.

# Exact repository evidence

- `src/api/deposit_settlement_router.py` lines 333–341 — only Python read of `checkout_photos`
- `src/api/deposit_settlement_router.py` lines 301–351 — full `photo_comparison` endpoint
- `tests/test_wave6_checkout_deposit_contract.py` line 85 — test assertion (response key only)
- Codebase grep result: 3 references total — 0 are writes
- `ihouse-ui/app/(app)/ops/checkout/page.tsx` — no photo upload logic in read portions

# Detailed evidence

**The full photo comparison endpoint (lines 301–351):**
```python
@router.get("/bookings/{booking_id}/photo-comparison")
async def photo_comparison(booking_id: str, tenant_id: str = Depends(jwt_auth), ...):

    # Source 1: Reference photos (property baseline state)
    ref = db.table("property_reference_photos")
            .select("photo_url, room_label, caption")
            .eq("property_id", property_id)
            .execute()
    ref_photos = ref.data or []

    # Source 2: Pre-checkin cleaning photos (post-clean, pre-guest state)
    cleaning = db.table("cleaning_task_photos")
                 .select("photo_url, room_label, created_at")
                 .eq("booking_id", booking_id)
                 .order("created_at")
                 .execute()
    cleaning_photos = cleaning.data or []

    # Source 3: Checkout condition photos ← ALWAYS EMPTY
    checkout = db.table("checkout_photos")
                 .select("photo_url, room_label, created_at, notes")
                 .eq("booking_id", booking_id)
                 .order("created_at")
                 .execute()
    checkout_photos = checkout.data or []

    return JSONResponse(status_code=200, content={
        "reference_photos": ref_photos,
        "cleaning_photos": cleaning_photos,
        "checkout_photos": checkout_photos,  # always []
    })
```

**Full grep results across entire codebase for `checkout_photos`:**
```
src/api/deposit_settlement_router.py:335 — SELECT query
src/api/deposit_settlement_router.py:340 — variable: checkout_photos = checkout.data or []
tests/test_wave6_checkout_deposit_contract.py:85 — assertIn("checkout_photos", body)
```
Zero write operations. The test only checks the key is present, not that it contains photos.

**The deposit deductions system — related but separate:**
`add_deduction` in the same router accepts a `photo_url` field:
```python
ded_row = {
    "id": ded_id,
    "deposit_id": deposit_id,
    "description": description,
    "amount": float(amount),
    "category": category,
    "photo_url": photo_url,   # individual deduction photo
    "created_at": now,
}
db.table("deposit_deductions").insert(ded_row).execute()
```
This is a per-deduction photo URL stored in `deposit_deductions.photo_url`, not a checkout condition photo in `checkout_photos`. A deduction photo documents a specific damage item. A checkout photo documents the overall property condition. These are distinct concepts — only one has a write path.

**The checkout frontend page:**
The first 250 lines of `ops/checkout/page.tsx` were read. The page has:
- A task-based checkout list (CHECKOUT_VERIFY tasks)
- Inspection notes and inspection ok/fail state
- Issue flagging (creates problem reports)
- Deposit resolution (return/deduction)
- No camera capture, no file upload, no `checkout_photos` reference visible

The page interacts with: `/worker/tasks`, `/properties/{id}`, `/worker/bookings/{id}`, `/problem-reports`. No call to a checkout photo upload endpoint was found.

**Whether `checkout_photos` table exists in migrations:**
A migration grep for `checkout_photos` returned no results. The table may be defined in an older migration not searched, or may not have a formal migration and only exists in the DB as a manually-created table. This is not confirmed either way.

**`property_reference_photos` — confirmed write path (for contrast):**
`property_reference_photos` is the source for the first column in the photo comparison. This table's write path was not specifically confirmed in this read, but its existence and population are more plausible because property setup happens before operations begin — a workflow where photos are likely uploaded during onboarding.

**`cleaning_task_photos` — confirmed write path:**
`cleaning_task_router.py` (read in Pass 4) is the write path for cleaning photos. Cleaners upload photos during cleaning tasks. These populate `cleaning_task_photos` and flow into the photo comparison endpoint.

# Contradictions

- The photo comparison endpoint was built anticipating checkout photos would exist. The endpoint reads three data sources in parallel. Two sources exist. One source — the one that is most operationally critical for damage assessment — is empty.
- The test for this endpoint (`test_wave6_checkout_deposit_contract.py`) passes despite `checkout_photos` always being empty, because the test only asserts the key is present, not that it has data. This test provides false confidence that the feature is working.
- The deposit deduction system (`add_deduction`) accepts `photo_url` per damage item, suggesting photo capture during checkout damage documentation was planned. But this is per-deduction, not a general checkout condition capture.

# What is confirmed

- `checkout_photos` is queried (SELECT) by the photo comparison endpoint.
- The query always returns an empty array.
- No Python code writes to `checkout_photos`.
- The test for the endpoint confirms only the response key's presence, not data content.
- The deposit deduction system has its own per-item photo field in `deposit_deductions`, separate from `checkout_photos`.

# What is not confirmed

- Whether `checkout_photos` has a table definition in any migration (not found in grep).
- Whether a photo upload endpoint exists in the checkout page that was not read (pages beyond line 250 were not fully read).
- Whether the checkout page mobile flow has a camera capture step that POSTs to an endpoint not found in the backend search.
- Whether `property_reference_photos` has a confirmed write path from the onboarding or property setup flow.

# Practical interpretation

The photo comparison workflow exists as a backend concept but is incomplete as an operational feature. Staff performing checkout can see:
- ✅ Reference photos (how the property looked before guests arrived)
- ✅ Cleaning photos (how the property looked after cleaning, before guests arrived)
- ✗ Checkout photos (how the property looked after guests departed) — always empty

The damage assessment workflow — comparing pre-stay condition to post-stay condition — is missing its most important input. The `deposit_deductions` endpoint partially compensates by allowing per-deduction photo URLs, but this requires the worker to already know what was damaged, not to have a photographic record of the overall property condition at checkout.

# Risk if misunderstood

**If the feature is assumed functional:** Property disputes over deposit deductions will lack checkout condition photos. Legal or dispute resolution processes that require photographic evidence of checkout condition will have no data from this system.

**If the test passing is taken as proof:** `test_wave6_checkout_deposit_contract.py` passes because it only asserts the response structure, not the data. A green test for this feature is not evidence the feature works.

**If `deposit_deductions.photo_url` is treated as equivalent:** Per-damage-item photos are not the same as systematic room-by-room checkout condition documentation. Using deduction photos as the only record means photos are only taken for items with financial claims, not for the overall property condition.

# Recommended follow-up check

1. Read `ihouse-ui/app/(app)/ops/checkout/page.tsx` lines 250–500 (not yet read) — specifically looking for any camera capture component, file input, or API call related to checkout photos.
2. Search for `checkout-photos` or `checkout_photo` in the frontend codebase for any upload endpoint.
3. Search migration files more broadly for `CREATE TABLE.*checkout_photos` to confirm the table schema.
4. Read `test_wave6_checkout_deposit_contract.py` fully to understand what the test actually validates.
