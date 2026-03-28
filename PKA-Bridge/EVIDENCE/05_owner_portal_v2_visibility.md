# Claim

Owner portal v2 visibility toggles are not fully proven as wired end-to-end.

# Verdict

CONTRADICTED (claim was too skeptical — toggles ARE wired)

# Why this verdict

Direct reading of `src/api/owner_portal_v2_router.py` lines 151–183 shows that the visibility toggle flags are fetched from the database and conditionally applied to each data section within the property summary endpoint. Three distinct sections are gated: `bookings`, `financial_summary`, and `maintenance_reports`. Each section is only queried and included in the response if its corresponding flag is truthy. The framework is not merely defined — it is executed at query time.

An earlier summary of this system stated the toggles were "defined but filtering logic incomplete." That was an error introduced by not reading the implementation directly. The implementation is complete for the three sections confirmed.

# Direct repository evidence

- `src/api/owner_portal_v2_router.py` lines 132–138 — visibility fetch from `owner_visibility_settings` table
- `src/api/owner_portal_v2_router.py` line 151 — `if visible.get("bookings", True):`
- `src/api/owner_portal_v2_router.py` line 161 — `if visible.get("financial_summary", True):`
- `src/api/owner_portal_v2_router.py` line 176 — `if visible.get("maintenance_reports", False):`
- `ihouse-ui/app/(app)/admin/managers/page.tsx` — capability toggle UI (visibility toggle administration surface)

# Evidence details

**Visibility fetch logic:**
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
This reads the `visible_fields` JSON column from `owner_visibility_settings` for the specific (tenant, owner, property) combination. If no row exists, `_DEFAULT_VISIBILITY` is used as a fallback.

**Bookings section gating:**
```python
if visible.get("bookings", True):
    try:
        bookings = (db.table("bookings").select("booking_id, check_in, check_out, status, guest_name")
                    .eq("property_id", property_id)
                    .order("check_in", desc=True).limit(20).execute())
        summary["bookings"] = bookings.data or []
    except Exception:
        summary["bookings"] = []
```
If `bookings` is `False` in `visible_fields`, this entire block is skipped. The `bookings` key is absent from the response. Default is `True` (owners see bookings unless explicitly hidden).

**Financial summary section gating:**
```python
if visible.get("financial_summary", True):
    try:
        fin = (db.table("booking_financial_facts").select("total_price, management_fee, net_to_property")
               .eq("property_id", property_id).execute())
        ...
        summary["financial"] = {...}
    except Exception:
        summary["financial"] = {}
```
Same pattern. Default `True`. When hidden, `summary["financial"]` is absent from the response.

**Maintenance reports section gating:**
```python
if visible.get("maintenance_reports", False):
    try:
        reports = (db.table("problem_reports").select("id, category, severity, status, description, created_at")
                   .eq("property_id", property_id)
                   .order("created_at", desc=True).limit(20).execute())
        summary["maintenance_reports"] = reports.data or []
    except Exception:
        summary["maintenance_reports"] = []
```
Default is `False` for maintenance_reports — meaning this section is hidden by default and must be explicitly enabled. This is the more conservative default for potentially sensitive maintenance information.

**Toggle flags defined in documentation/admin UI:**
The documentation mentions 8 configurable visibility toggles: `bookings`, `financial_summary`, `occupancy_rates`, `maintenance_reports`, `guest_details`, `task_details`, `worker_info`, `cleaning_photos`. Direct reading confirmed 3 of these are implemented in the property summary endpoint. The other 5 (`occupancy_rates`, `guest_details`, `task_details`, `worker_info`, `cleaning_photos`) were not confirmed as implemented in the same endpoint during this read.

# Conflicts or contradictions

- Earlier system map and summary notes stated: "the filtered summary endpoint does not appear to actively apply them to the query — the framework is defined but the filtering logic is incomplete." This was incorrect. Three toggle flags ARE actively applied. The error originated from not reading the implementation directly and instead relying on a structural summary.
- 5 of the 8 documented toggle flags were not confirmed as implemented in `owner_portal_v2_router.py` during this read. It is possible they are applied elsewhere (a different endpoint, a separate v2 route) or they may be defined in documentation without corresponding backend implementation. This is genuinely unknown.
- `_DEFAULT_VISIBILITY` is referenced but not shown in the code excerpt read. Its content — which fields default to `True` vs `False` — determines what an owner sees if no visibility settings row exists for their (tenant, owner, property) combination. The maintenance_reports toggle defaults to `False` (confirmed from line 176), but `_DEFAULT_VISIBILITY` may override this.

# What is still missing

- Whether the other 5 toggle flags (`occupancy_rates`, `guest_details`, `task_details`, `worker_info`, `cleaning_photos`) are implemented in the same endpoint, a different endpoint, or not at all.
- The content of `_DEFAULT_VISIBILITY` — the fallback when no `owner_visibility_settings` row exists.
- Whether there is a write path for `owner_visibility_settings` — i.e., an API endpoint that allows an admin to set visibility flags for an owner. If the table is read but never written by any API, the toggles would only be configurable via direct DB manipulation.
- Whether the `ihouse-ui/app/(app)/admin/owners/page.tsx` or `admin/managers/page.tsx` surfaces expose a UI for configuring these toggle flags per owner per property.
- Whether RLS policies on `owner_visibility_settings` restrict writes to admin-only, or whether an owner could theoretically write their own visibility settings.

# Risk if misunderstood

If the toggles are assumed incomplete (as an earlier pass incorrectly concluded), an implementation effort may duplicate or overwrite the existing visibility gate logic in the property summary endpoint. The three wired gates are functional and should be treated as ground truth.

If the toggles are assumed complete for all 8 fields (as documentation implies), the 5 unconfirmed fields may silently not filter anything, exposing data to owners who should not see it. The risk is the opposite of the first scenario — over-trusting the documentation-described 8-toggle system.

The safest position: treat the 3 confirmed gated fields as proven, and treat the other 5 as unconfirmed until the full endpoint is read.
