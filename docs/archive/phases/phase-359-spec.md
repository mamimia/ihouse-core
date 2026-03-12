# Phase 359 — Production Readiness Hardening

**Status:** Closed
**Prerequisite:** Phase 358 (Outbound Sync Interface Hardening)
**Date Closed:** 2026-03-12

## Goal

Audit and harden production infrastructure for deployment readiness. Identify and fix gaps in startup validation, version labelling, and configuration management.

## Design / Files

| File | Change |
|------|--------|
| `src/main.py` | MODIFIED — Added startup env validation block (SUPABASE_URL, SUPABASE_KEY, IHOUSE_JWT_SECRET warnings). Changed `app.version` from hardcoded `"0.1.0"` to dynamic `BUILD_VERSION` env var. |
| `docker-compose.production.yml` | MODIFIED — Added `BUILD_VERSION` env var to api service. Updated api + frontend labels from stale `phase313` to dynamic `${BUILD_VERSION:-latest}`. |

## Result

**0 new tests. No regressions.**

Pre-existing failures (9): Supabase connectivity (test_main_app × 2, test_health_enriched × 1, test_logging_middleware × 1) + 5 infra tests.

### Audit Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Dockerfile | ✅ | Multi-stage, non-root, HEALTHCHECK |
| docker-compose.production.yml | ✅ (fixed) | 4 workers, memory/CPU limits, read-only FS, security_opt |
| /health endpoint | ✅ | Supabase ping + DLQ count + outbound probes |
| /readiness endpoint | ✅ | Kubernetes-style probe |
| CORS | ✅ | Configurable via IHOUSE_CORS_ORIGINS |
| Request logging | ✅ | UUID request ID + X-Request-ID header |
| deploy_checklist.sh | ✅ | 7-step pre-deploy validation |
| Startup env validation | ✅ (NEW) | Warns on missing critical vars |
| Dynamic version | ✅ (NEW) | BUILD_VERSION → app.version + Docker labels |
