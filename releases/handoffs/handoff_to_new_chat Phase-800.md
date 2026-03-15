> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 800

**Date:** 2026-03-15
**Last Closed Phase:** 800 — Single-Tenant Live Activation + Auth Identity Fix
**Checkpoint:** XXV-B
**Next Phase:** 801 — Property Config & Channel Mapping

---

## Where We Are

The single-tenant staging environment is **fully operational** with runtime-verified authentication:

| What | Status |
|------|--------|
| Docker staging | ✅ Healthy on port 8001 |
| Supabase connection | ✅ 313ms latency |
| Admin login | ✅ admin@domaniqo.com → role=admin |
| Manager login | ✅ manager@domaniqo.com → role=manager |
| Worker login | ✅ worker@domaniqo.com → role=worker |
| OTA webhook chain | ✅ Proven: webhook → event_log → booking_state → financial_facts → tasks |
| Notification dispatch | ✅ Proven to provider boundary (no Twilio/SendGrid creds yet) |
| Frontend | ✅ 54 pages, 5 core flows working |

## Auth Architecture (Critical for 801+)

Two login flows exist:

1. **Production login** (`POST /auth/login`): Email + password → Supabase Auth → `tenant_permissions` lookup → JWT with `sub=user_id(UUID), tenant_id, role`
2. **Dev login** (`POST /auth/dev-login`): Tenant ID + secret → JWT with `sub=tenant_id, role`. Gated behind `IHOUSE_DEV_MODE=true`. Deprecated for production.

Key files:
- `src/api/auth_login_router.py` — production login endpoint
- `src/api/auth.py` — `get_identity()` + `jwt_identity` dependency (supports both JWT formats)
- `src/api/session_router.py` — dev login (deprecated path)
- `src/api/invite_router.py` — uses separate `supa_admin` (service_role) and `supa_login` (anon) clients

## Supabase Auth Users

| Email | UUID | Role | Tenant |
|-------|------|------|--------|
| admin@domaniqo.com | 25407914-2071-4ee8-b8ae-8aa5967d8f20 | admin | tenant_e2e_amended |
| manager@domaniqo.com | ecc69a1a-0070-4234-b49b-5aab70c09396 | manager | tenant_e2e_amended |
| worker@domaniqo.com | 19f9f4ed-34ae-45a3-87e2-309b8054d738 | worker | tenant_e2e_amended |

Staging password for all: `StagingTest2026!`

## Environment

- `.env.staging` has all required vars (copied to `.env` for Docker compose)
- Supabase project: `reykggmlcehswrxjviup.supabase.co`
- Docker compose: `docker compose up -d --build` on port 8001→8000

## Next Phases

### Layer A — Single-Tenant Completion (801–804)

| Phase | Goal |
|-------|------|
| **801** | Property Config & Channel Mapping — configure actual properties, link to OTA channels |
| **802** | Full Day Simulation — end-to-end operational day: arrivals, departures, cleanings, tasks, notifications |
| **803** | Monitoring & Alerting Setup — production observability |
| **804** | Operator Runbook & Handoff — operational documentation |

### Layer B — Multi-Tenant (805–812)

| Phase | Goal |
|-------|------|
| **805** | Multi-Tenant Data Isolation |
| **806** | Platform Admin & Super-Admin Model |
| **807** | Tenant Provisioning & Onboarding |
| **808** | First Admin Bootstrap Protocol |
| **809** | Billing & Usage Metering |
| **810** | Platform Observability & Support |
| **811** | Migration Path: Single → Multi-Tenant |
| **812** | Platform Architecture Review |

## Product Documents (Future Reference)

- `docs/product/admin-preview-mode.md` — read-only role preview for admins
- `docs/product/staffing-flexibility.md` — check-in/check-out always two screens, people flexible (admin decides)

## Deferred Items

| Phase | Title | Status |
|-------|-------|--------|
| 614 | Pre-Arrival Email (SMTP) | 🟡 Needs SMTP config |
| 617 | Wire Form → Checkin Router | 🟡 Needs live check-in data |
| 618 | Wire QR → Checkin Response | 🟡 Same as 617 |

## Known Issues

- 20 pre-existing E2E test failures (mostly integration tests requiring live Supabase)
- Notification dispatch not end-to-end: no Twilio/SendGrid credentials configured
- `.env.staging` was copied to `.env` for Docker — restore if needed

## Key Canonical Docs

| Doc | Status |
|-----|--------|
| `docs/core/BOOT.md` | ✅ Current |
| `docs/core/current-snapshot.md` | ✅ Updated to Phase 800 |
| `docs/core/work-context.md` | ✅ Updated to Phase 800 |
| `docs/core/phase-timeline.md` | ✅ Phases 793–800 appended |
| `docs/core/construction-log.md` | ✅ Phases 793–800 appended |
| Phase specs (793–800) | ✅ All 8 created in `docs/archive/phases/` |
| ZIP | ✅ `releases/phase-zips/iHouse-Core-Docs-Phase-800.zip` (287KB) |
