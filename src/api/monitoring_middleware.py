"""
Phase 537 — Monitoring Middleware
===================================

FastAPI middleware that records every request to the monitoring service.
Tracks route, status code, and latency.
"""
from __future__ import annotations

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from services.monitoring import record_request


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Records request metrics for every HTTP request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()
        response: Response = await call_next(request)
        latency = time.monotonic() - start

        # Extract route path
        route = request.url.path or "/"

        record_request(
            route=route,
            status_code=response.status_code,
            latency_s=latency,
        )

        return response
