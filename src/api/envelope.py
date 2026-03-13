"""
api/envelope.py — Explicit Response Envelope Helpers
====================================================

Canonical API contract helpers. Every router that returns JSON
should use ok() for success and err() for errors.

Usage:
    from api.envelope import ok, err

    @router.get("/items")
    async def list_items():
        items = fetch_items()
        return ok(items)

    @router.post("/items")
    async def create_item(body: ItemCreate):
        if not body.name:
            return err("VALIDATION_ERROR", "name is required", status=400)
        item = save_item(body)
        return ok(item, status=201)
"""
from __future__ import annotations

from fastapi.responses import JSONResponse


def ok(data, *, status: int = 200, **meta) -> JSONResponse:
    """Wrap a successful response in the canonical envelope."""
    envelope = {
        "ok": True,
        "data": data,
    }
    if meta:
        envelope["meta"] = meta
    return JSONResponse(content=envelope, status_code=status)


def err(code: str, message: str, *, status: int = 400, **extra) -> JSONResponse:
    """Wrap an error response in the canonical envelope."""
    error_body = {"code": code, "message": message}
    if extra:
        error_body.update(extra)
    return JSONResponse(
        content={"ok": False, "error": error_body},
        status_code=status,
    )
