# iHouse Core — Deploy Quickstart

## Prerequisites

- Docker + Docker Compose v2
- `.env` file with all required secrets (copy from `.env.production.example`)
- Supabase project URL + keys (Dashboard → Project Settings → API)

## Staging Deploy

```bash
# 1. Copy env template and fill secrets
cp .env.production.example .env
# Edit .env — set SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY, IHOUSE_JWT_SECRET

# 2. Build images
docker compose -f docker-compose.staging.yml build

# 3. Start services
docker compose -f docker-compose.staging.yml up -d

# 4. Verify health
curl http://localhost:8001/health
# Expected: {"status":"ok","version":"0.1.0-staging",...}

# 5. Verify frontend
open http://localhost:3000

# 6. Run integration tests
docker compose -f docker-compose.staging.yml run tests

# 7. View logs
docker compose -f docker-compose.staging.yml logs -f api
```

## Production Deploy

```bash
# 1. Build production images
docker compose -f docker-compose.production.yml build

# 2. Start services
docker compose -f docker-compose.production.yml up -d

# 3. Verify
curl http://localhost:8000/health
curl http://localhost:8000/readiness
```

## Health Endpoints

| Endpoint | Purpose | Expected |
|----------|---------|----------|
| `GET /health` | Liveness + DLQ check | 200 ok/degraded, 503 unhealthy |
| `GET /readiness` | Supabase reachable? | 200 ready, 503 not ready |
| `GET /docs` | OpenAPI docs | 200 (Swagger UI) |

## Important Notes

- **Staging** uses `IHOUSE_DRY_RUN=true` — outbound OTA sync calls are skipped.
- **Production** uses `IHOUSE_DRY_RUN` unset — real outbound calls to OTA APIs.
- All auth requires valid JWT in production. Use `POST /auth/signup` to create first user.
- Docker daemon must be running before `docker compose` commands.
