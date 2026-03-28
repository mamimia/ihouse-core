# Title

Financial Write Endpoints Are Accessible to Any Authenticated User — Manual Payment Records Can Be Created by Any Role

# Why this matters

`POST /admin/financial/payment` allows creating or overwriting financial facts for any booking. `POST /admin/financial/payout` allows querying full financial calculations for any property. Both operations are explicitly admin-scoped by their path prefix, their OpenAPI tag, and their purpose — manual financial adjustments and owner payout generation are high-stakes administrative actions. Both endpoints are protected only by `Depends(jwt_auth)`, which validates JWT existence but does not check the `role` claim. A checkout worker, cleaner, or maintenance worker with a valid JWT can call these endpoints directly via HTTP. The write endpoint specifically can overwrite OTA-sourced financial data with fabricated values, and the audit log entry produced obscures who made the change by hardcoding `actor_id: "frontend"`.

# Original claim

`financial_writer_router.py` exposes financial write operations to any authenticated user without role validation — identical pattern to `staff_performance_router.py` but with higher consequence.

# Final verdict

PROVEN

# Executive summary

Both endpoints in `src/api/financial_writer_router.py` use only `Depends(jwt_auth)` with no role check. The router has no router-level dependencies. The `SUPABASE_SERVICE_ROLE_KEY` is used, bypassing RLS. The pattern is identical to the gap already documented in `staff_performance_router.py` (Investigation 06), but the consequence is higher here: the write endpoint can create or overwrite `booking_financial_facts` rows with arbitrary amounts, and `record_manual_payment` hardcodes `actor_id: "frontend"` in the audit entry — meaning the audit log cannot identify which user made the change. This combination of missing role guard and anonymized audit attribution is a compounding risk.

# Exact repository evidence

- `src/api/financial_writer_router.py` line 24 — `router = APIRouter(tags=["financial-writer"])` (no dependencies)
- `src/api/financial_writer_router.py` lines 61–64 — `record_manual_payment_endpoint` with `Depends(jwt_auth)` only
- `src/api/financial_writer_router.py` lines 99–102 — `generate_payout_endpoint` with `Depends(jwt_auth)` only
- `src/api/financial_writer_router.py` lines 27–32 — uses `SUPABASE_SERVICE_ROLE_KEY` (bypasses RLS)
- `src/services/financial_writer.py` lines 60–74 — `record_manual_payment` writes `actor_id: "frontend"` to audit log
- `src/api/financial_router.py` lines 66, 153 — `Depends(require_capability("financial"))` used on READ endpoints but NOT on writer router

# Detailed evidence

**Writer router endpoint 1 — POST /admin/financial/payment:**
```python
@router.post("/admin/financial/payment", tags=["financial-writer"], ...)
async def record_manual_payment_endpoint(
    body: ManualPaymentRequest,
    tenant_id: str = Depends(jwt_auth),   # ← only guard
    client: Optional[Any] = None,
) -> JSONResponse:
```
Calls `record_manual_payment()`. This function:
1. Upserts a row in `booking_financial_facts` with `on_conflict="booking_id,tenant_id"` — meaning it OVERWRITES the existing financial fact for that booking
2. Inserts into `admin_audit_log` with `actor_id: "frontend"` (hardcoded string, not the user's actual ID)

**The audit log entry hardcodes `actor_id`:**
```python
db.table("admin_audit_log").insert({
    "tenant_id": tenant_id,
    "actor_id": "frontend",         # ← hardcoded — actor is anonymous in audit
    "action": "financial_adjustment",
    "entity_type": "booking",
    "entity_id": booking_id,
    "details": {
        "payment_id": payment_id,
        "amount": amount,
        "currency": currency,
        "type": payment_type,
        "notes": notes,
    },
    "performed_at": now.isoformat(),
}).execute()
```
The audit entry cannot be traced back to the actual user who made the change. Any role, any user: the audit says `actor_id = "frontend"`.

**Writer router endpoint 2 — POST /admin/financial/payout:**
```python
@router.post("/admin/financial/payout", tags=["financial-writer"], ...)
async def generate_payout_endpoint(
    body: PayoutRequest,
    tenant_id: str = Depends(jwt_auth),   # ← only guard
    client: Optional[Any] = None,
) -> JSONResponse:
```
Calls `generate_payout_record()`. Any authenticated user can query complete financial summaries for any property in the tenant (full period revenue, management fees, net payout amounts).

**Contrast with READ financial endpoints:**
`financial_router.py` uses `require_capability("financial")` on all its endpoints:
```python
async def get_financial_facts(
    ...,
    _cap: None = Depends(require_capability("financial")),
    ...
)
```
The read endpoints have a capability guard. The write endpoints (in a different router file) do not. This is an inconsistency: reading financial data requires the `financial` capability, but writing financial data does not.

**What `record_manual_payment` can do:**
The upsert uses `on_conflict="booking_id,tenant_id"`. If a booking already has an OTA-sourced financial fact row, a `POST /admin/financial/payment` call with that booking's ID will overwrite it with the manually provided amount. The original OTA-sourced data is lost. Since the financial system reads the most recent row (`ORDER BY recorded_at DESC LIMIT 1`), an overwrite could hide real financial data under a fabricated entry.

**Service role key bypasses RLS:**
```python
return create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)
```
RLS cannot compensate for the missing application-layer role check.

**The read/write inconsistency pattern:**
Two routers in the financial domain — `financial_router.py` (reads) and `financial_writer_router.py` (writes). The read router uses `require_capability`. The write router does not. This split suggests the write router was written by a different hand or at a different time without checking the guard pattern used in the read router.

# Contradictions

- `financial_router.py` uses `require_capability("financial")` on all endpoints. `financial_writer_router.py` — which writes the same `booking_financial_facts` table — uses no capability guard.
- The path prefix `/admin/financial/` signals admin-only. Implementation enforces only authentication (any role).
- `record_manual_payment` writes to `admin_audit_log` — which is the system's tamper-evident history. But the audit entry has no usable actor identity. Audit logging without actor attribution is functionally useless for accountability.

# What is confirmed

- Both write endpoints use `Depends(jwt_auth)` only — no role check.
- The router has no router-level dependencies.
- `SUPABASE_SERVICE_ROLE_KEY` bypasses RLS — no DB-level protection.
- `record_manual_payment` hardcodes `actor_id: "frontend"` in the audit log.
- The upsert in `record_manual_payment` can overwrite existing OTA-sourced financial facts.
- Financial READ endpoints in a parallel router file use `require_capability("financial")` — writes do not.

# What is not confirmed

- Whether any infrastructure-level guard (Railway proxy, Nginx) restricts `/admin/*` backend routes to specific IPs or roles before reaching FastAPI.
- Whether `require_capability("financial")` would adequately guard these endpoints if added — specifically, which roles have the `financial` capability.
- Whether the `actor_id: "frontend"` anonymization was a deliberate decision (to not leak user IDs into audit logs) or an accidental hardcode that was never updated.

# Practical interpretation

Today, the highest-risk gap in the financial system is not the payout non-persistence (Investigation 08/14) — it is the ability for any worker to make manual financial adjustments to booking facts with no role guard and no actor attribution in the audit trail.

A scenario: a maintenance worker who knows the FastAPI backend URL notices their hours are not reflected in a booking's financial record. They call `POST /admin/financial/payment` with a fabricated amount. The booking's financial fact is overwritten. The audit log records `actor_id: "frontend"` — untraceable. The owner's financial report now shows incorrect revenue figures.

This is a small attack surface in a trusted single-property operation. It becomes a meaningful financial integrity risk in multi-staff, multi-property operations where workers may have varying levels of trust.

# Risk if misunderstood

**If missing role guard assumed protected by middleware:** Middleware blocks the `/admin/financial/` UI route. It does not protect the FastAPI API endpoint.

**If audit log assumed sufficient for accountability:** The audit log entry for `record_manual_payment` shows `actor_id: "frontend"`. This is not accountability — it is a record that something happened, with no trace of who did it.

**If the read/write guard inconsistency is not noticed:** A security review that checks the read endpoints (`financial_router.py`) will find `require_capability` and conclude financial endpoints are guarded. The write endpoints are in a separate file and will be missed.

# Recommended follow-up check

1. Read `src/api/capability_guard.py` to understand what `require_capability("financial")` checks — specifically, whether it validates role or a delegated capability field.
2. Add `Depends(require_capability("financial"))` or a role check to both endpoints in `financial_writer_router.py`, matching the pattern in `financial_router.py`.
3. Fix `actor_id: "frontend"` in `record_manual_payment` — the `jwt_auth` dependency returns `tenant_id`, but the function receives `db` and `tenant_id` without the caller's user ID. The function signature needs a `user_id` parameter passed from the calling router, where the JWT identity is available.
4. Audit all other `/admin/` prefixed routers for the same missing guard pattern (staff_performance, financial_writer confirmed — others may exist).
