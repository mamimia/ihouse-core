"""
Phase 866 — Preview Mode Middleware (Server-Enforced Data Isolation)
Phase 866b — Trust gap fix: admin-only activation
=====================================================================

Global middleware that blocks ALL mutation requests (POST/PUT/PATCH/DELETE)
when an **authenticated admin** sends the ``X-Preview-Role`` header.

Trust model (Phase 866b):
  - The ``X-Preview-Role`` header alone is NOT sufficient.
  - The middleware independently decodes the JWT from the Authorization header.
  - Preview blocking activates ONLY when BOTH conditions are met:
      1. The request has ``X-Preview-Role`` header
      2. The JWT decodes to a user with ``role == "admin"``
  - If the JWT is missing, invalid, expired, or non-admin:
      the ``X-Preview-Role`` header is SILENTLY IGNORED.
      The request passes through normally (auth deps handle real auth errors).

Rules (when preview is confirmed active):
  - GET/HEAD/OPTIONS → pass through (read-only ok).
  - POST/PUT/PATCH/DELETE → return HTTP 403 PREVIEW_READ_ONLY.

Exempt paths (mutations always allowed even in preview):
  - /health, /readiness  (health probes)
  - /auth/*              (login/logout must still work)

Phase truth:
  - Phase 866 = server-enforced read-only mutation blocking ✅
  - Phase 866 ≠ role-correct data projection (still shows admin-shaped data)
"""
from __future__ import annotations

import logging
import os

import jwt as pyjwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Shared constants — must match api/auth.py
_ENV_SECRET = "IHOUSE_JWT_SECRET"
_ENV_DEV_MODE = "IHOUSE_DEV_MODE"
_ALGORITHM = "HS256"

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


def _is_dev_mode() -> bool:
    return os.environ.get(_ENV_DEV_MODE, "").lower().strip() == "true"


def _extract_admin_from_jwt(request: Request) -> bool:
    """
    Decode the JWT from the Authorization header and return True
    only if the token belongs to an admin user.

    Returns False (silently) for:
      - missing/malformed Authorization header
      - invalid/expired JWT
      - valid JWT but role != "admin"

    In dev mode (IHOUSE_DEV_MODE=true): returns True (dev user is admin).
    """
    # Dev mode: dev user is always admin
    if _is_dev_mode():
        return True

    secret = os.environ.get(_ENV_SECRET, "")
    if not secret:
        return False  # No secret configured → can't verify → don't activate preview

    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return False

    token = auth_header[7:].strip()
    if not token:
        return False

    try:
        payload = pyjwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
            options={"verify_aud": False},
        )
    except Exception:
        return False  # Invalid/expired token → ignore preview header

    # Check role: new format has explicit role claim, legacy uses "manager" default
    role = str(payload.get("role", "")).strip().lower()
    return role == "admin"


class PreviewModeMiddleware(BaseHTTPMiddleware):
    """
    Phase 866/866b — Server-enforced read-only preview mode.

    Activates ONLY for authenticated admin users sending X-Preview-Role.
    Non-admin users' X-Preview-Role headers are silently ignored.
    """

    async def dispatch(self, request: Request, call_next):
        preview_role = request.headers.get("x-preview-role")

        # No preview header → normal flow
        if not preview_role:
            return await call_next(request)

        # Read-only methods always pass (even if preview header is present)
        if request.method.upper() in _READ_METHODS:
            return await call_next(request)

        # Exempt paths
        path = request.url.path.rstrip("/")
        for prefix in _EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # ── Phase 866b: Verify admin context ──────────────────────────
        # Only block mutations if the JWT confirms an admin user.
        # Non-admin X-Preview-Role headers are silently ignored.
        if not _extract_admin_from_jwt(request):
            logger.debug(
                "Preview header ignored — non-admin JWT for %s %s",
                request.method,
                path,
            )
            return await call_next(request)

        # ── Confirmed: authenticated admin in preview mode ────────────
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
