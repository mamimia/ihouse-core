"""
iHouse Core — FastAPI Application Entrypoint
=============================================

This is the unified production entrypoint for the OTA webhook ingestion stack.

Routes:
    GET  /health                — liveness check (no auth)
    POST /webhooks/{provider}  — OTA webhook ingestion (Phase 58)

Middleware added in future phases:
    Phase 60 — Structured request logging
    Phase 61 — JWT auth (tenant_id from token)
    Phase 62 — Per-tenant rate limiting

Run locally:
    PYTHONPATH=src uvicorn main:app --reload --port 8000

Or via this file directly:
    PYTHONPATH=src python src/main.py
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from api.webhooks import router as webhooks_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ihouse-core")

# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

_ENV = os.getenv("IHOUSE_ENV", "development")


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN001
    logger.info("iHouse Core API starting — env=%s version=%s", _ENV, app.version)
    yield
    logger.info("iHouse Core API shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="iHouse Core",
    version="0.1.0",
    description="OTA webhook ingestion and canonical event pipeline",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(webhooks_router)


@app.get("/health", tags=["ops"])
async def health() -> JSONResponse:
    """
    Liveness check. No authentication required.

    Returns:
        200 {"status": "ok", "version": "0.1.0", "env": "<env>"}
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "version": app.version,
            "env": _ENV,
        },
    )


# ---------------------------------------------------------------------------
# Local dev runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("IHOUSE_ENV", "development") == "development",
        log_level="info",
    )
