# Claim

`financial_writer_router.py` exposes financial write operations (`POST /admin/financial/payment`, `POST /admin/financial/payout`) to any authenticated user without role validation.

# Verdict

PROVEN

# Why this verdict

Both endpoints in `src/api/financial_writer_router.py` use only `Depends(jwt_auth)`. `jwt_auth` validates JWT existence and returns `tenant_id` — it does not check the `role` claim. Neither endpoint body contains a role check. The router is initialized without router-level dependencies. The endpoints are path-prefixed `/admin/financial/` — signaling admin-only intent — but any valid JWT holder can call them directly via HTTP.

# Direct repository evidence

- `src/api/financial_writer_router.py` line 24 — `router = APIRouter(tags=["financial-writer"])` (no dependencies)
- `src/api/financial_writer_router.py` lines 61–64 — `record_manual_payment_endpoint` with `Depends(jwt_auth)` only
- `src/api/financial_writer_router.py` lines 99–102 — `generate_payout_endpoint` with `Depends(jwt_auth)` only
- `src/api/financial_writer_router.py` line 31 — uses `SUPABASE_SERVICE_ROLE_KEY` (bypasses RLS)

# Evidence details

**Endpoint 1 — POST /admin/financial/payment:**
```python
async def record_manual_payment_endpoint(
    body: ManualPaymentRequest,
    tenant_id: str = Depends(jwt_auth),   # ← only guard
    client: Optional[Any] = None,
) -> JSONResponse:
```
Calls `record_manual_payment()` which upserts into `booking_financial_facts` and writes to `admin_audit_log`. Any authenticated user can create or overwrite financial facts for any booking in their tenant.

**Endpoint 2 — POST /admin/financial/payout:**
```python
async def generate_payout_endpoint(
    body: PayoutRequest,
    tenant_id: str = Depends(jwt_auth),   # ← only guard
    client: Optional[Any] = None,
) -> JSONResponse:
```
Calls `generate_payout_record()` — any authenticated user can query the full financial calculation for any property in their tenant.

**Both endpoints use `SUPABASE_SERVICE_ROLE_KEY`** — bypassing all Supabase RLS policies. No DB-level protection compensates for the missing application-layer role check.

**Pattern matches investigation 06** (staff_performance_router): same missing guard pattern — `/admin/` path prefix with admin tag, no role enforcement, service role key. This is a recurring issue in admin-tagged routers.

# Conflicts or contradictions

- Path prefix `/admin/financial/` signals admin-only. Implementation does not enforce this.
- `record_manual_payment` writes to `booking_financial_facts` and `admin_audit_log`. Allowing any role to write manual payment records means any worker with a JWT could fraudulently adjust financial records for bookings.

# What is still missing

- Whether any existing `require_capability("financial")` capability guard (seen in `financial_router.py`) is used here. It is not — this router does not use `require_capability`.
- Whether infrastructure-level guards protect `/admin/*` backend routes before reaching FastAPI.

# Risk if misunderstood

A cleaner or checkout worker with a valid JWT can call `POST /admin/financial/payment` directly via HTTP and write manual financial adjustments to any booking. This includes overwriting real OTA-sourced financial facts with fabricated amounts. The `admin_audit_log` entry would show `actor_id: "frontend"` (hardcoded in `record_manual_payment`) — obscuring who made the change.
