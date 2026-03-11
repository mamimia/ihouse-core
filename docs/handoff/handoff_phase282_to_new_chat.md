# iHouse Core — Handoff to New Chat Session
# Phase 282 — Platform Checkpoint XIII
# Generated: 2026-03-11T22:XX:XX+07:00

## Last Closed Phase
**Phase 282 — Platform Checkpoint XIII** (this document is the handoff)

## Phases Closed in This Session (273-282)

| Phase | Title |
|-------|-------|
| 273 | Documentation Integrity Sync XIII |
| 274 | Supabase Migration Reproducibility |
| 275 | Deployment Readiness Audit |
| 276 | Real JWT Authentication Flow |
| 277 | Supabase RPC + Schema Alignment |
| 278 | Production Environment Config |
| 279 | CI Pipeline Hardening |
| 280 | Real Webhook Endpoint Validation |
| 281 | First Live OTA Integration Test |
| 282 | Platform Checkpoint XIII |

## System State

- **Test count:** ~6,250 (exit 0)
- **Pre-existing failures:** 10 (test_worker_copilot_contract.py — unchanged)
- **Known ordering failures:** 5 (test_webhook_validation_p280 — all pass in isolation)
- **Supabase:** Project reykggmlcehswrxjviup — 28 tables, 12 RPCs — ACTIVE_HEALTHY
- **Git branch:** checkpoint/supabase-single-write-20260305-1747
- **Last commit:** Phase 282 — Platform Checkpoint XIII

## Key Files Changed This Session

| File | What |
|------|------|
| `src/api/auth.py` | Supabase Auth JWT support (Phase 276) |
| `src/api/auth_router.py` | /auth/supabase-verify endpoint (Phase 276) |
| `supabase/migrations/20260311230000_phase277_event_kind_booking_amended.sql` | Drift fix |
| `supabase/migrations/20260311230100_phase277_booking_state_guest_id.sql` | Drift fix |
| `supabase/BOOTSTRAP.md` | Phase 277 migrations added |
| `.env.production.example` | Production env template (Phase 278) |
| `docker-compose.production.yml` | Hardened compose (Phase 278) |
| `.github/workflows/ci.yml` | Python 3.14, blocking lint, 2 new jobs (Phase 279) |
| `tests/test_webhook_validation_p280.py` | 22 new webhook tests (Phase 280) |
| `tests/test_webhook_endpoint.py` | autouse _dev_mode fixture fix |
| `tests/test_webhook_ingestion_e2e.py` | IHOUSE_DEV_MODE=true setdefault |
| `scripts/e2e_live_ota_staging.py` | Live staging runner (Phase 281) |
| `tests/test_live_ota_staging_p281.py` | 15 CI-safe staging tests |

## Immediate Next Actions for New Chat

1. **Fix 5 p280 full-suite ordering failures** — create `conftest.py` with session-scoped cleanup for `IHOUSE_WEBHOOK_SECRET_*` vars
2. **Apply `properties` table to live Supabase** — `supabase/migrations/phase_156_properties_table.sql`
3. **Re-export `artifacts/supabase/schema.sql`** — capture live state (BOOKING_AMENDED, guest_id, rebuild_booking_state)
4. **Next phase block (283-292)** — propose based on roadmap

## Critical Files to Read First (in this order)
1. `docs/core/BOOT.md` — session rules
2. `docs/core/current-snapshot.md` — system state
3. `docs/core/work-context.md` — current work context
4. `docs/core/roadmap.md` — next 20 phases
