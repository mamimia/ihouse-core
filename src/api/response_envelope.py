"""
Phase 542 — API Response Envelope
====================================

Standard response wrapper for all API responses.
Ensures consistent format across all endpoints.
"""
from __future__ import annotations

from typing import Any
from fastapi.responses import JSONResponse


def success(
    data: Any = None,
    message: str | None = None,
    meta: dict | None = None,
    status_code: int = 200,
) -> JSONResponse:
    """
    Return a standardized success response.

    Envelope format:
        {
            "ok": true,
            "data": <payload>,
            "message": <optional>,
            "meta": <optional dict with pagination, timing, etc>
        }
    """
    body: dict[str, Any] = {"ok": True}
    if data is not None:
        body["data"] = data
    if message:
        body["message"] = message
    if meta:
        body["meta"] = meta
    return JSONResponse(content=body, status_code=status_code)


def error(
    message: str,
    code: str | None = None,
    status_code: int = 400,
    details: Any = None,
) -> JSONResponse:
    """
    Return a standardized error response.

    Envelope format:
        {
            "ok": false,
            "error": {
                "message": "...",
                "code": "VALIDATION_ERROR",
                "details": <optional>
            }
        }
    """
    err: dict[str, Any] = {"message": message}
    if code:
        err["code"] = code
    if details:
        err["details"] = details
    return JSONResponse(
        content={"ok": False, "error": err},
        status_code=status_code,
    )


def paginated(
    data: list,
    total: int,
    page: int = 1,
    per_page: int = 50,
    message: str | None = None,
) -> JSONResponse:
    """
    Return a standardized paginated response.

    Envelope format:
        {
            "ok": true,
            "data": [...],
            "meta": {
                "total": N,
                "page": 1,
                "per_page": 50,
                "total_pages": M
            }
        }
    """
    import math
    total_pages = math.ceil(total / per_page) if per_page > 0 else 0
    return success(
        data=data,
        message=message,
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        },
    )
