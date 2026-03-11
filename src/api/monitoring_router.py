"""
Phase 263 — Production Monitoring Router
==========================================

GET  /admin/metrics              — Full metrics snapshot
GET  /admin/metrics/health       — Liveness/readiness probe (returns 200 or 503)
GET  /admin/metrics/latency      — Latency breakdown by route prefix
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.monitoring import (
    get_full_metrics,
    get_request_counts,
    get_error_counts,
    get_latency_stats,
    get_uptime_seconds,
)

router = APIRouter(prefix="/admin/monitor", tags=["admin"])

# Thresholds for readiness
_MAX_5XX_RATE = 0.10  # 10% 5xx → degraded


@router.get("", summary="Full metrics snapshot — request counts, error counts, uptime, latency")
async def full_metrics() -> JSONResponse:
    """GET /admin/monitor"""
    return JSONResponse(status_code=200, content=get_full_metrics())


@router.get("/health", summary="Liveness / readiness probe")
async def health_probe() -> JSONResponse:
    """
    GET /admin/monitor/health

    Returns 200 OK if healthy, 503 if 5xx rate > 10%.
    Health envelope includes uptime, status, degraded flag.
    """
    uptime = get_uptime_seconds()
    req_counts = get_request_counts()
    err_counts = get_error_counts()

    total_requests = sum(req_counts.values())
    total_5xx = sum(v["5xx"] for v in err_counts.values())

    degraded = False
    if total_requests > 0:
        rate_5xx = total_5xx / total_requests
        if rate_5xx > _MAX_5XX_RATE:
            degraded = True

    body = {
        "status":          "degraded" if degraded else "ok",
        "uptime_seconds":  round(uptime, 2),
        "total_requests":  total_requests,
        "total_5xx":       total_5xx,
        "degraded":        degraded,
    }
    return JSONResponse(
        status_code=503 if degraded else 200,
        content=body,
    )


@router.get("/latency", summary="Latency stats by route prefix (min / max / avg / p95 in ms)")
async def latency_stats() -> JSONResponse:
    """GET /admin/monitor/latency"""
    return JSONResponse(status_code=200, content={
        "latency_by_prefix": get_latency_stats(),
    })
