# Phase 775 — Deployment & Staging Activation (Phases 758–775)

**Status:** Closed
**Prerequisite:** Phase 757 (Roadmap Complete)
**Date Closed:** 2026-03-15

## Goal

Prepare iHouse Core for staging deployment by fixing runtime baseline issues, provisioning storage, completing the auth model, and creating operational monitoring endpoints. This is the first post-roadmap hardening stage.

## Invariant

- 48/48 public tables have RLS enabled, 0 security advisories
- DB role is authoritative (role_authority.py) — self-declared roles are ignored
- Admin bootstrap is idempotent and secret-protected

## Design / Files

| File | Change |
|------|--------|
| `src/services/role_authority.py` | NEW — DB role lookup, resolve_role() |
| `src/services/tenant_bridge.py` | NEW — Supabase UUID → iHouse tenant_id bridge |
| `src/api/bootstrap_router.py` | NEW — POST /admin/bootstrap (idempotent) |
| `src/api/webhook_test_router.py` | NEW — POST /admin/webhook-test |
| `src/api/notification_health_router.py` | NEW — GET /admin/notification-health |
| `src/api/system_status_router.py` | NEW — GET /admin/system-status |
| `src/api/invite_router.py` | MODIFIED — accept creates Supabase Auth user |
| `src/api/auth_router.py` | MODIFIED — password reset + update endpoints |
| `src/main.py` | MODIFIED — registered 3 new routers |
| `docker-compose.staging.yml` | MODIFIED — IHOUSE_BOOTSTRAP_SECRET added |

## Result

**277 tests pass, 0 failed.**
- 48 RLS-protected tables
- 4 storage buckets provisioned
- 5 new admin ops endpoints
- Frontend: 54 pages compile, 29 usable / 25 data-dependent / 0 broken
- Multi-tenant reality check documented — major gaps identified for next stage
