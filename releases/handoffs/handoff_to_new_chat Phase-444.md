> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# iHouse Core — Handoff to Next Chat (Phase 444)

**Date:** 2026-03-13
**Last Closed Phase:** 444
**Next Phase:** 445

---

## What Was Done (Phases 425-444)

20-phase production readiness verification across 4 blocks:

**Block 1 (425-429):** Fixed 4 doc discrepancies (page count 38→37, test file count 248→251, stale roadmap forward). Full test suite baseline: 7,200 passed, 9 failed (Supabase infra). Supabase live: 5,335 events, 1,516 bookings, 14 tenants, 43 RLS tables. 12 env vars added to .env.production.example.

**Block 2 (430-434):** Docker verified structurally (daemon not running). JWT auth verified (HS256, role claims, 3 endpoints). RLS verified (43 tables). Live webhook data confirmed (37 BOOKING_CREATED, 6 BOOKING_CANCELED).

**Block 3 (435-439):** Frontend API (NEXT_PUBLIC_API_URL in all pages), SSE (6 channels), monitoring (/health + SENTRY_DSN), notification channels (5 dispatchers) all verified.

**Block 4 (440-444):** Onboarding pipeline (1 real property DOM-001), financial facts (300 EUR, 15% commission), security (no hardcoded secrets, rate limiter), deploy scripts verified.

---

## System Numbers

| Metric | Value |
|--------|-------|
| Tests | 7,200 passed / 9 failed / 17 skipped |
| API routers | 87 |
| Test files | 251 |
| Frontend pages | 37 |
| Services | 29 |
| Supabase migrations (local) | 16 |
| Supabase migrations (live) | 35 |
| OTA adapters | 14 unique |
| Channels | 5 |
| Supabase tables | 43 (all RLS) |
| Live events | 5,335 |
| Live bookings | 1,516 (1,121 active / 378 canceled) |
| Tenants | 14 |
| Phase specs | 444 |

---

## Known Issues

1. 9 test failures — all Supabase connectivity (5 apply_envelope E2E, 2 health 503, 1 health_enriched, 1 logging_middleware)
2. Docker daemon not running on dev machine — build not tested
3. 0 Supabase Auth users — system uses internal JWT token issuer
4. Notification channels all dry-run (no tokens configured)
5. IHOUSE_JWT_SECRET not set in .env (in .env.production.example only)

---

## Starting Point for Next Session

Phase 445. The system is verified production-ready from a code and architecture perspective. The next focus should be:
- **Real deployment** — start Docker, build image, deploy to staging
- **Supabase Auth setup** — create first auth user, test real JWT flow
- **First real channel dispatch** — configure LINE or email token, send real notification
- **Live data integration testing** — ingest a real OTA webhook from a real provider

Read `docs/core/BOOT.md` first, then Layer C docs.
