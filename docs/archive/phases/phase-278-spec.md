# Phase 278 — Production Environment Configuration

**Status:** Closed
**Prerequisite:** Phase 277 (Supabase RPC + Schema Alignment)
**Date Closed:** 2026-03-11

## Goal

Create hardened production configuration artifacts that a developer or ops engineer can use to deploy iHouse Core to production with zero guesswork.

## Files Created

### `.env.production.example`

Complete production environment template with:
- 5 security rules called out at the top (JWT ≥64 chars, API key ≥32 chars, DEV_MODE=false required, etc.)
- All 20+ variables with production-appropriate values (no dev defaults)
- Notes on where to find each secret (Supabase Dashboard, OTA Partner Portal, etc.)
- Explicit `IHOUSE_DEV_MODE=false` (prevents accidental dev bypass in prod)

### `docker-compose.production.yml`

Production-hardened compose over the existing `docker-compose.yml`:

| Setting | Dev (`docker-compose.yml`) | Prod (`docker-compose.production.yml`) |
|---------|------|------|
| Workers | 2 | 4 |
| Restart | `unless-stopped` | `always` (+ restart_policy with max_attempts) |
| Memory limit | 512MB | 1GB |
| CPU limit | 1.0 | 2.0 |
| Filesystem | writable | `read_only: true` + tmpfs |
| Security | — | `no-new-privileges:true` |
| Logging | 10MB / 3 files | 50MB / 5 files, compressed, with labels |
| `IHOUSE_DEV_MODE` | (not set) | explicitly `false` |

## Deployment Commands

```bash
# Build and start in production mode
docker compose -f docker-compose.production.yml up -d

# Verify
docker compose -f docker-compose.production.yml ps
curl http://localhost:8000/health

# Logs
docker compose -f docker-compose.production.yml logs -f api
```

## Important: `read_only: true` Note

The read-only filesystem is the most important security hardening. `tmpfs` is mounted at `/tmp` and `/run` for Python runtime writes. If any new code writes to a path outside these directories, it will fail at runtime — this is intentional.
