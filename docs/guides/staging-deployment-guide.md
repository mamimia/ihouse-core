# iHouse Core — Staging Deployment Guide

**Phase 423 — 2026-03-13**

## Prerequisites

1. **Supabase project** — Create at [supabase.com](https://supabase.com)
2. **Docker** — Installed and running
3. **Node.js 20+** — For frontend build
4. **Python 3.14+** — For backend

## Step 1 — Environment Setup

```bash
# Copy and fill in the environment template
cp .env.production.example .env.staging

# Validate environment variables
bash scripts/validate_env.sh
```

Required variables:
- `SUPABASE_URL` — Your Supabase project URL
- `SUPABASE_KEY` — Supabase anon key
- `SUPABASE_SERVICE_ROLE_KEY` — Supabase service role key
- `IHOUSE_ENV=staging`
- `IHOUSE_JWT_SECRET` — Secret for signing JWTs (min 32 chars)
- `IHOUSE_ACCESS_TOKEN_SECRET` — Secret for HMAC access tokens (min 32 chars)

## Step 2 — Supabase Migrations

```bash
# Apply all 16 migrations in order
# Use the Supabase SQL editor or CLI
supabase db push
```

Verify with:
```bash
bash scripts/verify_migrations.sh
```

## Step 3 — Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Start the backend
cd src && uvicorn main:app --host 0.0.0.0 --port 8000

# Verify health
curl http://localhost:8000/health
```

## Step 4 — Frontend

```bash
cd ihouse-ui
npm install
npm run build
npm start
```

## Step 5 — Docker (Alternative)

```bash
docker-compose -f docker-compose.production.yml up -d
```

## Step 6 — Verification

1. Health check: `curl http://localhost:8000/health`
2. OpenAPI docs: `http://localhost:8000/docs`
3. Frontend: `http://localhost:3000` (local dev) or `http://localhost:8001` (Docker staging — backend port mapping)
4. Login with admin credentials

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Health returns 503 | Check Supabase connection variables |
| TypeScript build fails | Run `npx tsc --noEmit` in `ihouse-ui/` |
| Migration fails | Check `supabase/SCHEMA_REFERENCE.md` for migration order |
| CORS errors | Set `IHOUSE_CORS_ORIGINS` to frontend URL |
