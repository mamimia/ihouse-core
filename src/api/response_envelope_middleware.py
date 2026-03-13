"""
Phase 570-572 — Response Envelope Middleware
=============================================

Global middleware that wraps all API responses in the standard envelope format:

  Success: { "ok": true, "data": <original body>, "meta": { ... } }
  Error:   { "ok": false, "error": { "message": "...", "code": "..." } }

Works as a Starlette middleware — no router changes needed.
Skips streaming responses (CSV exports) and already-enveloped responses.
"""
from __future__ import annotations

import json
import time
import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse, JSONResponse
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger(__name__)


class ResponseEnvelopeMiddleware(BaseHTTPMiddleware):
    """
    Phase 570 — Wraps all JSON responses in the standard envelope.
    
    Skips:
      - Streaming responses (CSV downloads etc.)
      - Responses already containing { "ok": true/false }
      - Health check endpoint (/health)
      - OpenAPI/docs endpoints
      - When IHOUSE_ENVELOPE_DISABLED=true (test environment)
    """

    SKIP_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})

    async def dispatch(self, request: Request, call_next):
        # Allow tests to run against raw JSON — middleware is tested independently
        import os
        if os.getenv("IHOUSE_ENVELOPE_DISABLED", "").lower() in ("true", "1", "yes"):
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)

        # Skip non-JSON streaming responses (CSV downloads etc.)
        if isinstance(response, StreamingResponse):
            return response

        # Skip health/docs
        if request.url.path in self.SKIP_PATHS:
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Read the response body
        body_bytes = b""
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                body_bytes += chunk
            else:
                body_bytes += chunk.encode("utf-8")

        try:
            body = json.loads(body_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # Already enveloped — skip
        if isinstance(body, dict) and "ok" in body:
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type="application/json",
            )

        duration_ms = round((time.monotonic() - start) * 1000, 1)

        # Wrap in envelope
        if 200 <= response.status_code < 400:
            envelope = {
                "ok": True,
                "data": body,
                "meta": {
                    "duration_ms": duration_ms,
                },
            }
        else:
            # Error response
            msg = "Unknown error"
            code = "UNKNOWN_ERROR"
            if isinstance(body, dict):
                msg = body.get("message", body.get("detail", str(body)))
                code = body.get("code", body.get("error", {}).get("code", "UNKNOWN_ERROR")) if isinstance(body.get("error"), dict) else body.get("code", "UNKNOWN_ERROR")
            envelope = {
                "ok": False,
                "error": {
                    "message": str(msg),
                    "code": str(code),
                },
            }

        return JSONResponse(
            content=envelope,
            status_code=response.status_code,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Phase 572 — Global exception handlers for consistent error envelopes.
    """

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        detail = "; ".join(
            f"{'.'.join(str(l) for l in e.get('loc', []))}: {e.get('msg', '')}"
            for e in errors
        )
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "error": {
                    "message": detail,
                    "code": "VALIDATION_ERROR",
                    "details": errors,
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": {
                    "message": "Internal server error",
                    "code": "INTERNAL_ERROR",
                },
            },
        )
