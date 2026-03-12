# Phase 286 — Production Docker Hardening

**Date:** 2026-03-12
**Category:** 🔧 Infrastructure

## Objective

Make production compose deployment-ready with a pre-deploy validation checklist and confirm the healthcheck is correctly wired end-to-end.

## Deliverables

### 1. `scripts/deploy_checklist.sh` — NEW

Pre-deploy validation script with 7 sequential checks:

1. **Env file** — confirms `.env` (or custom `--env` arg) exists
2. **Required vars** — `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `IHOUSE_JWT_SECRET`, `IHOUSE_API_KEY`
3. **Supabase connectivity** — HTTP ping to `/rest/v1/` with service role key
4. **Port availability** — confirms port 8000 (or `$PORT`) is free
5. **Docker** — confirms `docker` + `docker compose` v2 + daemon running
6. **Dockerfile + compose syntax** — multi-stage stages present, `docker compose config` passes
7. **Env example completeness** — `.env.production.example` contains all required keys

Exits non-zero on first failure. Coloured terminal output (✓/✗/!).

Usage:
```bash
./scripts/deploy_checklist.sh           # uses .env
./scripts/deploy_checklist.sh .env.prod  # custom env file
```

### 2. `docker-compose.production.yml` — MODIFIED

- Updated `com.ihouse.version` label: `phase278` → `phase286`

### Note — Health Check (already present from Phase 278)

`docker-compose.production.yml` already includes a production-hardened `healthcheck`:
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
  interval: 30s
  timeout: 5s
  start_period: 20s
  retries: 5
```
No changes needed — confirmed correct.

### Note — `depends_on` (N/A)

The production compose is a single-service file (API only — Supabase is hosted). `depends_on` health conditions are not applicable.

## Test Results

Full test suite: **6,216 passed · 0 failed · exit 0**
