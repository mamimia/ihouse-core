"""
Phase 866 — Preview Mode Middleware (Server-Enforced Data Isolation)
=====================================================================

Global middleware that blocks ALL mutation requests (POST/PUT/PATCH/DELETE)
when the preview mode header ``X-Preview-Role`` is present.

This is the server-side enforcement layer. The frontend also has a cosmetic
``MutationGuard`` (Phase 863), but this middleware is the canonical safety net
— no mutation can slip through even if the frontend is bypassed.

Rules:
  - If ``X-Preview-Role`` header is absent → pass through (no effect).
  - If present + method is GET/HEAD/OPTIONS → pass through (read-only ok).
  - If present + method is POST/PUT/PATCH/DELETE → return HTTP 403:
      ``{"ok": false, "error": {"message": "Preview mode: read-only", "code": "PREVIEW_READ_ONLY"}}``

Exempt paths (mutations that are safe/necessary even in preview):
  - /health, /readiness  (health probes)
  - /auth/*              (login/logout must still work)
"""
from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# HTTP methods that are always allowed in preview mode
_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Paths exempt from preview blocking (prefix match)
_EXEMPT_PREFIXES = (
    "/health",
    "/readiness",
    "/auth/",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class PreviewModeMiddleware(BaseHTTPMiddleware):
    """
    Phase 866 — Server-enforced read-only preview mode.

    When ``X-Preview-Role`` header is present, all mutation requests
    (POST, PUT, PATCH, DELETE) are rejected with HTTP 403.
    """

    async def dispatch(self, request: Request, call_next):
        preview_role = request.headers.get("x-preview-role")

        # No preview header → normal flow
        if not preview_role:
            return await call_next(request)

        # Read-only methods always pass
        if request.method.upper() in _READ_METHODS:
            return await call_next(request)

        # Exempt paths
        path = request.url.path.rstrip("/")
        for prefix in _EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Block mutation
        logger.warning(
            "Phase 866 PREVIEW_READ_ONLY: blocked %s %s (preview_role=%s)",
            request.method,
            path,
            preview_role,
        )

        return JSONResponse(
            status_code=403,
            content={
                "ok": False,
                "error": {
                    "message": "Preview mode: read-only — all mutations are disabled",
                    "code": "PREVIEW_READ_ONLY",
                },
            },
        )
