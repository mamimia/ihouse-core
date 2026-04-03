# Phase 1058 — Operational Audit Closure: PKA-Bridge Group B + Group C + Backend Authorization Hardening

**Status:** Closed
**Prerequisite:** Phase 1057 — Settlement Finalize Atomicity Hardening (PLANNED)
**Date Closed:** 2026-04-04

## Goal

Complete the canonical closure of all Group B (Operational Product Surfaces) and Group C (Stakeholder-Facing Product)
PKA-Bridge audit items, including the final depth-check fixes and backend authorization hardening.

The primary systemic fix is the introduction of `admin_only_auth` — a FastAPI dependency that enforces `role == 'admin'`
at the API layer for all admin-namespace and DLQ endpoints. This closes the backend authorization gap that existed
alongside the previously implemented frontend admin layout guard, completing end-to-end defense-in-depth for all
admin operations.

Additionally, all audit result files were reconciled to match their true final classification, and three test contract
files were updated to reflect the new `identity:` dict signature on the affected endpoints.

## Invariant

**INV-1058-ADMIN-AUTH:** All admin-namespace endpoints (`/admin/*`) and DLQ endpoints (`/admin/dlq/*`) require
`role == 'admin'` at the backend layer via `admin_only_auth`. Frontend layout guard (redirect to `/manager`) is a
complementary presentation layer. The backend gate is the canonical enforcement point. A caller without
`role=admin` in their JWT receives HTTP 403 `CAPABILITY_DENIED { required_role: admin, caller_role: <actual> }`.

## Design / Files

| File | Change |
|------|--------|
| `src/api/auth.py` | NEW — `admin_only_auth` FastAPI dependency. Reads JWT `role` claim via `get_identity()`. Returns 403 CAPABILITY_DENIED for any non-admin role. Dev mode bypasses with admin identity. |
| `src/api/dlq_router.py` | MODIFIED — All 3 DLQ endpoints (`GET /admin/dlq`, `GET /admin/dlq/{id}`, `POST /admin/dlq/{id}/replay`) now use `Depends(admin_only_auth)`. `tenant_id` extracted from `identity["tenant_id"]`. |
| `src/api/admin_router.py` | MODIFIED — All 11 admin-namespace endpoints now use `Depends(admin_only_auth)`. Includes summary, metrics, dlq-summary, health/providers, booking timeline, reconciliation, audit-log, integrations GET, integrations PUT, integrations test POST. |
| `tests/test_dlq_e2e.py` | MODIFIED — All direct endpoint calls updated from `tenant_id=TENANT` to `identity={"tenant_id": TENANT, "role": "admin"}`. 18 test cases fixed. |
| `tests/test_admin_audit_log_contract.py` | MODIFIED — Endpoint calls in `_audit_get` helper updated to `identity=`. Direct `write_audit_event()` calls retain `tenant_id=` (it is a utility function, not an endpoint). 34 test cases fixed. |
| `tests/test_admin_properties_e2e.py` | MODIFIED — Admin router endpoint calls (Groups A–E) updated to `identity=`. Properties router calls (Group F) retained `tenant_id=` since `properties_router.py` still uses `jwt_auth`. 15 test cases fixed. |
| `PKA-Bridge/ACTIVATION/group_b_operational_product_surfaces/evidence/result/06_sonia_result.md` | MODIFIED — Closure table corrected from "frontend only" to "Fully closed — both layers". "What Remains" section replaced with canonical backend fix summary. |
| `PKA-Bridge/ACTIVATION/group_b_operational_product_surfaces/evidence/result/08_marco_result.md` | MODIFIED — Offline/photo-upload closure reclassified from "Safe enough now" to "Real residual risk, partially mitigated". Rationale: sentinel URL preserves DB record but photo bytes can be permanently lost — not the same as data integrity. |

## PKA-Bridge Group B — Final Closure Summary

| Item | Reviewer | Final State |
|------|----------|-------------|
| 06 — Manager FULL_ACCESS / admin surface | Sonia | ✅ Fully closed — frontend layout guard + `admin_only_auth` backend gate |
| 07 — Cash deposit UNIQUE constraint | Victor | ✅ Fully closed (prior pass) — migration applied, 0 duplicates confirmed |
| 08 — Offline photo upload failure | Marco | ⚠️ Real residual risk, partially mitigated — sentinel URL preserves record, bytes lost |
| 09 — Deactivation auto-cleanup | Hana | ✅ Fully closed (prior pass) — PATCH endpoint clears assignments + PENDING tasks atomically |
| 10 — Multi-role worker navigation | Marco | ✅ Fully closed (prior pass) — `resolveSecondaryRoles()` surfaces secondary work areas |

## PKA-Bridge Group C — Final Closure Summary

| Item | Reviewer | Final State |
|------|----------|-------------|
| 11 — Storage bucket RLS | Oren | ✅ Fully closed — live SQL audit confirmed all PII buckets private; public buckets intentional |
| 12 — DB tables UNIQUE constraints | Victor | ✅ Fully closed (merged into 07/09 fixes) |
| 13 — Session invalidation on deactivation | Sonia | 🔵 Future gap — requires auth-layer redesign (Redis revocation list); current deactivation blocks login but existing sessions persist until expiry |
| 14 — Receipt/statement accuracy | Hana | ✅ Verified correct — settlement calculation uses correct rate at time of booking |

## Result

**8,138 passed, 52 failed (all pre-existing mock stubs — wave7/wave5/wave3/task model, guest portal, reconciliation),
22 skipped. TypeScript build: not run in this phase (no frontend changes).**

Pre-existing failures confirmed unchanged — none introduced by Phase 1058.
New failures from `admin_only_auth` signature change: resolved by updating 3 test contract files.
