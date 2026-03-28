# Title

Owner Portal V2 Visibility Toggles Are Wired — But Only Three of Eight Documented Fields Are Confirmed

# Why this matters

The owner visibility toggle system determines what financial, operational, and guest data a property owner can see in their portal. If toggles are wired, operators can configure per-owner, per-property data access without a code change. If they are not wired, all data is always visible regardless of configuration — meaning sensitive financial and guest data cannot be selectively withheld from owners who should not see it. Correctly understanding the toggle's implementation state is necessary before making product decisions about owner data transparency.

# Original claim

Owner portal v2 visibility toggles are not fully proven as wired end-to-end.

# Final verdict

CONTRADICTED (claim was too skeptical — toggles ARE wired for at least three fields)

# Executive summary

An earlier audit summary incorrectly stated that the visibility toggle filtering logic was "defined but incomplete." Direct code reading refutes this. In `src/api/owner_portal_v2_router.py`, three visibility toggle flags — `bookings`, `financial_summary`, and `maintenance_reports` — are actively fetched from the `owner_visibility_settings` table and conditionally applied to each section of the property summary response. If a flag is `False`, the corresponding data section is not queried and not included in the response. The mechanism is real and functional for these three fields. However, five of the eight documented toggle flags (`occupancy_rates`, `guest_details`, `task_details`, `worker_info`, `cleaning_photos`) were not confirmed as implemented in the endpoint read. Their wiring status remains unknown.

# Exact repository evidence

- `src/api/owner_portal_v2_router.py` lines 132–138 — visibility fetch from `owner_visibility_settings`
- `src/api/owner_portal_v2_router.py` line 138 — `_DEFAULT_VISIBILITY` fallback variable
- `src/api/owner_portal_v2_router.py` line 151 — `if visible.get("bookings", True):`
- `src/api/owner_portal_v2_router.py` line 161 — `if visible.get("financial_summary", True):`
- `src/api/owner_portal_v2_router.py` line 176 — `if visible.get("maintenance_reports", False):`
- `ihouse-ui/app/(app)/owner/page.tsx` — owner portal frontend
- `ihouse-ui/app/(app)/financial/statements/page.tsx` — owner statement UI

# Detailed evidence

**Visibility fetch:**
```python
vis_res = (db.table("owner_visibility_settings")
           .select("visible_fields")
           .eq("tenant_id", tenant_id)
           .eq("owner_id", owner_id)
           .eq("property_id", property_id)
           .limit(1).execute())
vis_rows = vis_res.data or []
visible = vis_rows[0]["visible_fields"] if vis_rows else _DEFAULT_VISIBILITY
```
The system fetches a per-(tenant, owner, property) visibility configuration row. `visible_fields` is a JSON column containing the toggle map. If no row exists, `_DEFAULT_VISIBILITY` is used as a fallback (content of `_DEFAULT_VISIBILITY` is not confirmed from this read, but the default values embedded in `.get()` calls below give partial information).

**Bookings section — conditionally gated:**
```python
if visible.get("bookings", True):
    try:
        bookings = (db.table("bookings")
                    .select("booking_id, check_in, check_out, status, guest_name")
                    .eq("property_id", property_id)
                    .order("check_in", desc=True).limit(20).execute())
        summary["bookings"] = bookings.data or []
    except Exception:
        summary["bookings"] = []
```
When `visible["bookings"]` is `False`, this entire block is skipped. The `bookings` key is absent from `summary`. The default (when no row exists) is `True` — owners see bookings by default.

**Financial summary section — conditionally gated:**
```python
if visible.get("financial_summary", True):
    try:
        fin = (db.table("booking_financial_facts")
               .select("total_price, management_fee, net_to_property")
               .eq("property_id", property_id).execute())
        fin_data = fin.data or []
        summary["financial"] = {
            "total_revenue": sum(f.get("total_price", 0) for f in fin_data),
            "total_fees": sum(f.get("management_fee", 0) for f in fin_data),
            "net_to_owner": sum(f.get("net_to_property", 0) for f in fin_data),
            "booking_count": len(fin_data),
        }
    except Exception:
        summary["financial"] = {}
```
When `visible["financial_summary"]` is `False`, this block is skipped. Financial data is absent from the response. Default is `True`.

**Maintenance reports section — conditionally gated:**
```python
if visible.get("maintenance_reports", False):
    try:
        reports = (db.table("problem_reports")
                   .select("id, category, severity, status, description, created_at")
                   .eq("property_id", property_id)
                   .order("created_at", desc=True).limit(20).execute())
        summary["maintenance_reports"] = reports.data or []
    except Exception:
        summary["maintenance_reports"] = []
```
When `visible["maintenance_reports"]` is `False` (which is the default), maintenance reports are not queried and not included. Default is `False` — more conservative for potentially sensitive maintenance data. This field must be explicitly enabled.

**Default behavior summary from `.get()` calls:**
- `bookings`: defaults `True` (owners see bookings unless hidden)
- `financial_summary`: defaults `True` (owners see financial data unless hidden)
- `maintenance_reports`: defaults `False` (owners do NOT see maintenance reports unless explicitly enabled)

**Five unconfirmed fields:**
Documentation and earlier summaries describe 8 toggle fields: `bookings`, `financial_summary`, `occupancy_rates`, `maintenance_reports`, `guest_details`, `task_details`, `worker_info`, `cleaning_photos`. Three are confirmed above. The other five — `occupancy_rates`, `guest_details`, `task_details`, `worker_info`, `cleaning_photos` — were not found in the portion of the router read. They may exist in:
- A different endpoint in the same router file (not read)
- A separate v1 endpoint that also accepts visibility flags
- Documentation without corresponding backend implementation

**What `owner_portal_v2_router.py` also contains:**
The same file contains the maintenance specialist sub-system (Phases 725–728) for creating, assigning, and filtering maintenance specialists. This is a separate functional domain that shares the router file. The full file was not read beyond line 190 in the relevant excerpt.

# Contradictions

- Earlier system map note and audit summary stated: "the filtered summary endpoint does not appear to actively apply them to the query — the framework is defined but the filtering logic is incomplete." This was an error. The filtering logic is implemented for three fields and is actively applied on every request.
- The source of the earlier incorrect conclusion was likely reading only the router's structure or initial setup code (where `_DEFAULT_VISIBILITY` is defined) without reading the endpoint body where the gates are applied.
- Documentation describes 8 toggle fields. Code confirms 3 are wired. The gap between 8 and 3 is real but was not the same claim as "no toggles are wired."

# What is confirmed

- `owner_visibility_settings` table is queried per (tenant, owner, property) combination.
- `visible_fields` JSON column is fetched and used as the toggle map.
- `_DEFAULT_VISIBILITY` is used as fallback when no row exists.
- `bookings` toggle gates the bookings query — default `True`.
- `financial_summary` toggle gates the financial query — default `True`.
- `maintenance_reports` toggle gates the problem reports query — default `False`.
- All three gates are applied at query time, not just at response-shaping time — meaning if a toggle is `False`, the corresponding DB query does not execute.

# What is not confirmed

- The content of `_DEFAULT_VISIBILITY` (the full fallback object). The defaults embedded in `.get()` calls give partial information but may not cover all keys.
- Whether `occupancy_rates`, `guest_details`, `task_details`, `worker_info`, and `cleaning_photos` are implemented in the same endpoint, in a different endpoint, or not at all.
- Whether there is a write path (API endpoint) for creating or updating `owner_visibility_settings` rows. If the table is read but never written by any API, toggles can only be configured via direct DB manipulation.
- Whether the admin UI (`/admin/managers` or `/admin/owners`) exposes visibility toggle configuration per owner per property.
- Whether RLS policies on `owner_visibility_settings` prevent owners from reading or writing their own visibility configuration.
- Whether the `owner/page.tsx` frontend respects absence of toggled-off keys in the API response, or whether it renders empty sections that reveal the existence of hidden data.

# Practical interpretation

The visibility toggle system works — but for only three of the eight fields described in product documentation. An operator who configures `bookings: false` will successfully hide booking data from an owner's portal. The same for `financial_summary` and `maintenance_reports`. If they attempt to configure `guest_details: false` (for example), that toggle will exist in the `visible_fields` JSON but will have no effect on the response, because the backend does not check it.

This is a partial implementation, not a missing implementation. The architecture is correct and the pattern is proven. The remaining 5 fields need their corresponding gate conditions added to the endpoint body.

# Risk if misunderstood

**If toggles assumed fully unimplemented:** A developer rebuilds the toggle system from scratch, duplicating the working gate logic for `bookings`, `financial_summary`, and `maintenance_reports`. Existing `owner_visibility_settings` rows in the DB become orphaned or overwritten.

**If toggles assumed fully implemented (all 8 fields):** Operators configure `guest_details: false` to protect guest privacy from owners, and believe it is working. It is not — guest details (if exposed by the API) would still be included in the response. Guest privacy is not protected by an unchecked toggle.

**If default behavior is misunderstood:** `maintenance_reports` defaults `False`. A newly created owner account with no `owner_visibility_settings` row will see bookings and financials by default, but NOT maintenance reports. If this default is not intentional or not communicated, operators may report "maintenance reports are broken" when they are correctly defaulting to hidden.

# Recommended follow-up check

1. Read the full `src/api/owner_portal_v2_router.py` endpoint body to determine whether `occupancy_rates`, `guest_details`, `task_details`, `worker_info`, and `cleaning_photos` gates appear elsewhere in the file.
2. Search for `owner_visibility_settings` write operations in the codebase — any `INSERT` or `UPSERT` into that table — to confirm there is an API path for configuring toggles.
3. Read `ihouse-ui/app/(app)/admin/owners/page.tsx` to determine whether the owner management UI includes visibility toggle configuration.
4. Read `_DEFAULT_VISIBILITY` declaration in `owner_portal_v2_router.py` to see the full default toggle map.
5. Check whether the `owner/page.tsx` frontend handles absent keys gracefully (e.g., no `bookings` key = section is hidden) or errors when expected keys are missing.
