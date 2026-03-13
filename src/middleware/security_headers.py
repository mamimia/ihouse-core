"""
Phase 480 — Security Headers Middleware

Adds standard security headers to all HTTP responses.
Follows OWASP best practices for web application security headers.

Headers added:
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - X-XSS-Protection: 0  (modern browsers, CSP preferred)
  - Strict-Transport-Security: max-age=31536000; includeSubDomains
  - Referrer-Policy: strict-origin-when-cross-origin
  - Permissions-Policy: camera=(), microphone=(), geolocation=()
  - Cache-Control: no-store (on API responses only)

Enable by importing and adding to the FastAPI app:
    from middleware.security_headers import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)
"""
from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject security headers into all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Core security headers (always applied)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # HSTS — only in production (not dev/staging behind non-HTTPS proxy)
        if os.environ.get("IHOUSE_ENV", "development") == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Prevent caching of API responses (not static assets)
        path = request.url.path
        if not path.startswith(("/static", "/favicon")):
            response.headers["Cache-Control"] = "no-store"

        return response
