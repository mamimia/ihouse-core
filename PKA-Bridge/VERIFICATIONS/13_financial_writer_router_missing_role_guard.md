# Title

Financial Writer Router Missing Role Guard — Investigation Fully Correct; Both Claims Fixed; Actor Identity Now Recorded in Audit Log

# Related files

- Investigation: `INVESTIGATIONS/13_financial_writer_router_missing_role_guard.md`
- Evidence: `EVIDENCE/13_financial_writer_router_missing_role_guard.md`

# Original claim

`POST /admin/financial/payment` and `POST /admin/financial/payout` had only `Depends(jwt_auth)` — no role check. Any authenticated user could call these endpoints. `record_manual_payment()` hardcoded `actor_id: "frontend"` in the audit log, making all financial adjustments indistinguishable by actor.

# Original verdict

PROVEN

# Response from implementation layer

**Verdict from implementation layer: Investigation fully correct. Both claims proven. Fixed.**

**All 5 questions confirmed:**

**1. `financial_writer_router.py` used only `Depends(jwt_auth)`:**
Confirmed. Router initialized as `APIRouter(tags=["financial-writer"])` — no router-level dependencies. Both endpoints had only `Depends(jwt_auth)`, which returns `tenant_id` and validates JWT signature but never inspects the `role` claim.

**2. Any authenticated user could call these endpoints:**
Confirmed. A cleaner, checkout worker, or maintenance worker with a valid JWT could call `POST /admin/financial/payment` and overwrite OTA-sourced `booking_financial_facts` rows for any booking.

**3. The write path could overwrite `booking_financial_facts`:**
Confirmed. `record_manual_payment()` uses `.upsert(..., on_conflict="booking_id,tenant_id")` — a single booking can have only one financial fact row, and that row is replaced in-place. Original OTA-sourced data was silently overwritten with no versioning or conflict warning.

**4. The audit log had zero accountability:**
Confirmed. The hardcode was literal: `"frontend"` the string, not a variable. Every financial adjustment written through this endpoint was indistinguishable in the audit log regardless of who actually called it.

**5. Fix aligned with the guarded read side:**
Yes — `financial_router.py` (the read side) already used `require_capability("financial")` on all read endpoints. The write router now uses the same guard.

**Changes applied:**

| File | Change |
|------|--------|
| `financial_writer_router.py` | Added `from api.auth import jwt_identity` and `from api.capability_guard import require_capability` |
| `financial_writer_router.py` — `POST /admin/financial/payment` | Added `identity: dict = Depends(jwt_identity)` + `_cap: None = Depends(require_capability("financial"))`; extracts `actor_id = identity.get("user_id")`; passes it to `record_manual_payment()` |
| `financial_writer_router.py` — `POST /admin/financial/payout` | Added `_cap: None = Depends(require_capability("financial"))` |
| `services/financial_writer.py` — `record_manual_payment()` | Added `actor_id: str = "unknown"` parameter; replaced hardcoded `"frontend"` with `actor_id` in the audit insert |

**Guard semantics (from `capability_guard.py`):**
- `admin` → always allowed
- `manager` → allowed only if `financial` capability delegated in `tenant_permissions`
- All other roles → HTTP 403 `CAPABILITY_DENIED`

This is identical to the behavior already applied to the read side (`financial_router.py`), making the authorization model consistent across the entire financial surface.

**Note on the payout endpoint:**
`POST /admin/financial/payout` also received the capability guard, even though the function is an orphaned Phase 502 with no frontend consumer (see Investigation 08 / Verification 08). The guard is correct hygiene: if a frontend surface is ever built for the payout endpoint, the authorization is already in place and does not need to be added as a separate step.

# Verification reading

No additional repository verification read performed. The implementation response is internally consistent, resolves all five investigation questions with direct code evidence, and the fix pattern is identical to the already-confirmed pattern from Verification 06 (staff performance router fix using the same `require_capability` dependency).

# Verification verdict

RESOLVED

# What changed

`src/api/financial_writer_router.py`:
- `require_capability("financial")` added to both `POST /admin/financial/payment` and `POST /admin/financial/payout`
- `jwt_identity` dependency added to `POST /admin/financial/payment` to extract real `user_id`
- `actor_id` extracted from identity and passed to `record_manual_payment()`

`src/services/financial_writer.py`:
- `record_manual_payment()` now accepts `actor_id: str = "unknown"` parameter
- Audit log `actor_id` field now populated with the calling user's actual `user_id` instead of the hardcoded string `"frontend"`

Any caller without `admin` role or delegated `financial` capability now receives HTTP 403 instead of executing a write.

All new financial adjustment audit records will contain the real actor identity. Historical audit records with `actor_id: "frontend"` remain in `admin_audit_log` and cannot be attributed — they represent an audit gap that cannot be retroactively closed.

# What now appears true

- The full financial surface (reads + writes) now uses a consistent authorization model: `require_capability("financial")` gates all operations.
- `record_manual_payment()` audit entries now record the real actor. The `actor_id: "unknown"` default is a safety fallback — in production, `jwt_identity` always provides `user_id`.
- The upsert behavior (`on_conflict="booking_id,tenant_id"`) was not changed. Financial adjustments still silently overwrite OTA-sourced data. This is the intended behavior for manual corrections; what changed is that only authorized actors can now perform those corrections.
- All historical `admin_audit_log` entries with `actor_id: "frontend"` are permanently non-attributable. This is a known limitation of the prior implementation.
- The payout endpoint guard is forward-looking hygiene — the endpoint remains orphaned, but authorization is now in place for when it gains a frontend consumer.

# What is still unclear

- **Whether any `tenant_permissions` rows exist with the `financial` capability delegated to managers.** If no managers have been delegated this capability, managers now get 403 for financial writes — a potential operational regression if managers were using `POST /admin/financial/payment` before the fix. Admin users are unaffected (always allowed).
- **Whether `actor_id: "unknown"` can ever appear in production** — if `jwt_identity` fails for some reason (e.g., malformed JWT that passes signature check but has no `user_id` claim), the default `"unknown"` would be stored. This is a very unlikely edge case but worth noting.
- **Whether the upsert-overwrites-OTA behavior should have a confirmation gate or version check** — the guard now ensures only authorized users can overwrite OTA data, but there is still no "are you sure you want to overwrite the OTA-sourced record?" safeguard at the API layer. A concurrent OTA sync could also overwrite a manual adjustment. Not changed in this fix.

# Recommended next step

**Close both claims.** Role guard is in place. Audit accountability is restored.

**The authorization surface is now consistent across the financial module:**
- Read endpoints (`financial_router.py`): `require_capability("financial")` ✅ (pre-existing)
- Write endpoints (`financial_writer_router.py`): `require_capability("financial")` ✅ (this fix)
- Read-only endpoints (`financial_aggregation_router.py`, `owner_statement_router.py`): verify these also use appropriate guards — not checked in this investigation pass

**Keep the OTA-overwrite behavior on the watchlist:**
The authorized-but-silent overwrite of OTA-sourced financial data is now properly gated. But the lack of a conflict warning or version check means a financially significant OTA record could be silently replaced by a manual adjustment (or vice versa via OTA sync). This is a data integrity concern separate from the authorization gap.
