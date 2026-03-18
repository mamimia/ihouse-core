# runtime-truth.md
# iHouse Core — Canonical Localhost / Runtime Truth
# ==================================================
# Phase 839 — Single source of truth for all ports, processes, and startup commands.
# BOOT protocol points here. Do NOT duplicate this data in BOOT.
# Last updated: 2026-03-18

---

## A. Canonical Ports (LOCKED)

| Service   | Canonical Port | Address                    | Notes |
|-----------|---------------|----------------------------|-------|
| Frontend  | **3000**      | http://localhost:3000      | Next.js dev server. Always :3000. |
| Backend   | **8000**      | http://localhost:8000      | FastAPI/uvicorn. Always :8000 in dev. |

> **Never guess between 8000 and 8001.**
> PORT=8001 in `.env` is a staging/docker override. For local dev, backend is always :8000.
> If something isn't reachable on :8000 → the backend is not running. Start it. Don't try other ports.

---

## B. Correct Startup Commands (LOCKED)

### Frontend
```bash
# From: /Users/clawadmin/Antigravity Proj/ihouse-core/ihouse-ui
npm run dev
# Serves: http://localhost:3000
```

### Backend (dev, correct command)
```bash
# From: /Users/clawadmin/Antigravity Proj/ihouse-core
set -a && source .env && set +a
source .venv/bin/activate
PYTHONPATH=src python -m uvicorn main:app --host 127.0.0.1 --port 8000
# Serves: http://localhost:8000
```

> **Why `main:app` not `app.main:app`?**
> The real entrypoint is `src/main.py`. With `PYTHONPATH=src`, uvicorn resolves `main` to `src/main.py`.
> `app.main:app` resolves to `src/app/main.py` — a stub that fails with `ModuleNotFoundError: No module named 'core'`.

### Quick liveness check (5-second diagnostic, no hanging)
```bash
# Frontend
curl -s --max-time 3 -o /dev/null -w "HTTP_%{http_code}" http://localhost:3000/ && echo ""

# Backend
curl -s --max-time 3 http://localhost:8000/health

# CORS check
curl -s --max-time 3 -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: POST" \
  -X OPTIONS http://localhost:8000/auth/login -o /dev/null -w "%{http_code}"
```

---

## C. Staging/Docker Port (Do Not Confuse with Dev)

| Context       | Port | Note |
|---------------|------|------|
| Staging       | 8001 | Set via PORT=8001 in `.env.staging`. Docker only. |
| Docker Compose| 8001 | As per `docker-compose.staging.yml`. |
| Local dev     | 8000 | Always. Override `PORT` env var if needed. |

---

## D. Scripts Audit — What Was Wrong

| Script | Status | Problem | Fix |
|--------|--------|---------|-----|
| `scripts/run_api.sh` | ⚠️ BROKEN | Uses `app.main:app` → resolves to stub, not real server. No .env loaded → no CORS. | Use dev script below |
| `scripts/dev/run_api.sh` | ⚠️ BROKEN | Same `app.main:app` problem. | Fixed by using `main:app` directly |
| Manual `PYTHONPATH=src uvicorn main:app` | ✅ CORRECT | Resolves `src/main.py` correctly. Loads `.env`. Full CORS. | This is the canonical command |

> **Action needed**: `scripts/run_api.sh` and `scripts/dev/run_api.sh` both have wrong entrypoints.
> Until fixed, use the manual command above.

---

## E. Diagnostic Ladder (Fixed — No Hanging)

When any service isn't reachable, run in order, each with max-time 3:

```
Step 1: curl -s --max-time 3 http://localhost:3000/  → HTTP 200 = frontend up
Step 2: curl -s --max-time 3 http://localhost:8000/health → {status:ok} = backend up
Step 3: lsof -ti tcp:3000 → PID = process on port (or empty = nothing)
Step 4: lsof -ti tcp:8000 → PID = process on port (or empty = nothing)
Step 5: tail -20 /tmp/backend.log → last startup error
Step 6: Kill stale: kill -9 $(lsof -ti tcp:8000) && restart
```

If frontend 200 but backend dead → start backend only.
If backend 200 but CORS fails → backend started without .env → restart with env loaded.
Never wait more than 3 seconds per check. Move to next step immediately on failure.

---

## F. Source of Truth — Single File

This file (`docs/ops/runtime-truth.md`) is the only place that defines ports and startup commands.

**No other document should define ports.** If `docs/core/current-snapshot.md` or `work-context.md` mentions ports, those are references — this file is authoritative.
