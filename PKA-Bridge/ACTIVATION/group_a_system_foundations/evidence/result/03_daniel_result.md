# Group A Audit Result: Daniel — Role & Permission Architect

**Audit date:** 2026-04-04
**Auditor:** Antigravity (session 627e84a9)

---

## Verdict: NOT REAL

The concern that settlement and financial mutation endpoints may lack role guards is **disproven by direct code reading**. All settlement and financial mutation endpoints have explicit role enforcement.

---

## Evidence Basis

### Settlement endpoint role guards

**`checkout_settlement_router.py` (lines 81–91):**
```python
_WRITE_ROLES     = frozenset({"admin", "ops", "worker", "checkin", "checkout"})
_DEDUCT_ROLES    = frozenset({"admin", "ops", "checkout"})
_FINALIZE_ROLES  = frozenset({"admin", "ops", "worker", "checkout"})
_VOID_ROLES      = frozenset({"admin"})
_CHECKOUT_DATE_BYPASS_ROLES = frozenset({"admin", "manager"})
```
Every mutation endpoint enforces one of these frozensets. `_VOID_ROLES = frozenset({"admin"})` means only admin can void a settlement. This is correct.

**`checkin_settlement_router.py` (lines 64–67, 222):**
```python
_WRITE_ROLES    = frozenset({"admin", "ops", "worker", "checkin"})
_CORRECT_ROLES  = frozenset({"admin", "ops", "checkin"})
_ADMIN_ROLES    = frozenset({"admin", "manager"})
```
Role is checked at line 222 on the deposit write endpoint: `if role not in _WRITE_ROLES`.

**`deposit_settlement_router.py` (line 84):**
```python
_cap: None = Depends(require_capability("financial")),
```
The manual deposit collection endpoint requires the `financial` delegated capability — manager-only. This is the strictest guard of the three.

### Financial router capability guards

**Confirmed correct** (from Daniel's evidence file, Claim 5): `financial_router.py` and `financial_writer_router.py` use `Depends(require_capability("financial"))` on all endpoints.

### Unknown role fallback

**Not real.** `middleware.ts` (edge middleware) runs before `roleRoute.ts`. An unknown role is redirected to `/no-access` at the edge. `roleRoute.ts`'s fallback to `/dashboard` for unknown roles is **dead code** — it is never reached because middleware blocks the route first.

### Dev mode bypass

**Confirmed mitigated.** `env_validator.py` raises a fatal error if `IHOUSE_DEV_MODE=true` with `IHOUSE_ENV=production`. The bypass is intentional for development and properly blocked in production.

### Auth coverage across routers

**Confirmed pervasive.** 414 occurrences of `Depends(jwt_identity)` or `Depends(jwt_auth)` across 120 of 134 routers. The ~14 without auth are intentionally public (guest portal token endpoints, health checks, invite acceptance).

---

## Fix Needed

**No fix triggered.**

---

## Why Not Fixed

All settlement and financial mutation endpoints have explicit role guards. The concern was based on a hypothesis that the code might only use `jwt_identity` (authentication only) without role checking. The code uses `jwt_identity` for authentication AND checks `role not in _WRITE_ROLES` within the endpoint body. This is functionally equivalent to a FastAPI `Depends()` role guard — just enforced at the function body level rather than the dependency injection level. Both patterns are valid.
