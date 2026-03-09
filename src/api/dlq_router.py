"""
Phase 131 — DLQ Inspector

Provides per-entry inspection of the OTA dead letter queue (ota_dead_letter table).
Phase 127 showed per-provider DLQ counts in the Integration Health Dashboard.
Phase 131 gives operators the ability to inspect individual DLQ entries for
manual resolution, debugging, and operational triage.

Endpoints:
    GET /admin/dlq                     — list DLQ entries (with filters)
    GET /admin/dlq/{envelope_id}       — single DLQ entry with full detail

Query parameters for GET /admin/dlq:
    - source (optional): filter by OTA provider
    - status (optional): "pending" | "applied" | "error" | "all" (default: all)
    - limit (int, 1–100, default 50)

DLQ entry status derivation:
    - "applied": replay_result in APPLIED_STATUSES
    - "error": replay_result not null and not in APPLIED_STATUSES
    - "pending": replay_result is null

Response shape (list):
    {
        "total": int,           # rows returned (not total in DB)
        "entries": [
            {
                "envelope_id": str,
                "source": str,
                "replay_result": str | null,
                "status": "pending" | "applied" | "error",
                "error_reason": str | null,
                "created_at": str | null,
                "replayed_at": str | null,
                "payload_preview": str | null,  # first 200 chars of raw_payload
            }
        ]
    }

Response shape (single entry):
    {
        ... all fields above ...,
        "raw_payload": str | null    # full payload (single entry only)
    }

Invariants:
    - Reads ota_dead_letter only (global, not tenant-scoped).
    - Admin endpoint: JWT auth required (any valid tenant = admin access).
    - Never writes to any table.
    - payload_preview truncated to 200 chars (list). Full payload in single entry.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import make_error_response

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50
_PAYLOAD_PREVIEW_CHARS = 200

_APPLIED_STATUSES = frozenset({
    "APPLIED",
    "ALREADY_APPLIED",
    "ALREADY_EXISTS",
    "ALREADY_EXISTS_BUSINESS",
})

_VALID_STATUSES = frozenset({"pending", "applied", "error", "all"})


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------

def _derive_status(replay_result: Optional[str]) -> str:
    """
    Derive human-readable DLQ entry status from replay_result field.

    Returns: "pending" | "applied" | "error"
    """
    if replay_result is None:
        return "pending"
    if replay_result in _APPLIED_STATUSES:
        return "applied"
    return "error"


def _matches_status_filter(
    replay_result: Optional[str],
    status_filter: str,
) -> bool:
    """
    Returns True if this row's derived status matches the requested filter.
    "all" matches everything.
    """
    if status_filter == "all":
        return True
    return _derive_status(replay_result) == status_filter


# ---------------------------------------------------------------------------
# Row formatting
# ---------------------------------------------------------------------------

def _format_entry(row: Dict[str, Any], include_full_payload: bool = False) -> Dict[str, Any]:
    """
    Format a raw ota_dead_letter row into an API response dict.
    """
    replay_result = row.get("replay_result")
    raw_payload = row.get("raw_payload") or row.get("payload")
    payload_str = str(raw_payload) if raw_payload is not None else None

    entry: Dict[str, Any] = {
        "envelope_id": row.get("envelope_id") or row.get("id"),
        "source":       row.get("source"),
        "replay_result": replay_result,
        "status":       _derive_status(replay_result),
        "error_reason": row.get("error_reason") or row.get("error"),
        "created_at":   row.get("created_at"),
        "replayed_at":  row.get("replayed_at"),
        "payload_preview": (
            payload_str[:_PAYLOAD_PREVIEW_CHARS] if payload_str else None
        ),
    }

    if include_full_payload:
        entry["raw_payload"] = payload_str

    return entry


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/admin/dlq",
    tags=["admin"],
    summary="DLQ Inspector — list dead letter queue entries (Phase 131)",
    description=(
        "List entries in the OTA dead letter queue (`ota_dead_letter` table) "
        "for operational triage.\n\n"
        "**Filters:** `source` (OTA provider), `status` (pending/applied/error/all).\n\n"
        "**Status derivation:**\n"
        "- `pending`: `replay_result` is null\n"
        "- `applied`: `replay_result` in APPLIED/ALREADY_APPLIED/ALREADY_EXISTS\n"
        "- `error`: `replay_result` not null and not applied\n\n"
        "**payload_preview**: first 200 chars of raw payload. "
        "Use GET /admin/dlq/{envelope_id} for full payload.\n\n"
        "**Source:** `ota_dead_letter` — global (not tenant-scoped). Read-only."
    ),
    responses={
        200: {"description": "DLQ entries matching the requested filters."},
        400: {"description": "Invalid query parameter."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_dlq_entries(
    source: Optional[str] = None,
    status: str = "all",
    limit: int = _DEFAULT_LIMIT,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /admin/dlq?source=&status=&limit=

    Lists DLQ entries. JWT auth required (admin surface).
    Reads from ota_dead_letter only. Never writes.
    """
    # Validate status filter
    if status not in _VALID_STATUSES:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"status must be one of: {sorted(_VALID_STATUSES)}",
        )

    # Clamp limit
    if limit < 1 or limit > _MAX_LIMIT:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"limit must be between 1 and {_MAX_LIMIT}.",
        )

    try:
        db = client if client is not None else _get_supabase_client()

        query = (
            db.table("ota_dead_letter")
            .select(
                "id, envelope_id, source, replay_result, error_reason, error, "
                "raw_payload, payload, created_at, replayed_at"
            )
            .order("created_at", desc=True)
            .limit(limit * 3)  # over-fetch to allow client-side status filtering
        )

        if source is not None:
            query = query.eq("source", source)

        result = query.execute()
        rows = result.data or []

    except Exception:  # noqa: BLE001
        return make_error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="Failed to query DLQ.",
        )

    # Apply status filter in Python (replay_result can't be enum-filtered easily)
    filtered = [
        r for r in rows
        if _matches_status_filter(r.get("replay_result"), status)
    ][:limit]

    entries = [_format_entry(r) for r in filtered]

    return JSONResponse(
        status_code=200,
        content={
            "total": len(entries),
            "status_filter": status,
            "source_filter": source,
            "entries": entries,
        },
    )


@router.get(
    "/admin/dlq/{envelope_id}",
    tags=["admin"],
    summary="DLQ Inspector — single entry with full payload (Phase 131)",
    description=(
        "Retrieve a single DLQ entry by `envelope_id` with the full raw payload.\n\n"
        "Use this after finding an entry via `GET /admin/dlq` to inspect the "
        "full payload for debugging.\n\n"
        "**Source:** `ota_dead_letter` — global. Read-only."
    ),
    responses={
        200: {"description": "Full DLQ entry including raw payload."},
        401: {"description": "Missing or invalid JWT token."},
        404: {"description": "No DLQ entry found with this envelope_id."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_dlq_entry(
    envelope_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /admin/dlq/{envelope_id}

    Returns full DLQ entry including raw_payload. JWT auth required.
    Reads from ota_dead_letter only. Never writes.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        # Try matching envelope_id field, fallback to id field
        result = (
            db.table("ota_dead_letter")
            .select(
                "id, envelope_id, source, replay_result, error_reason, error, "
                "raw_payload, payload, created_at, replayed_at"
            )
            .eq("envelope_id", envelope_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []

    except Exception:  # noqa: BLE001
        return make_error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="Failed to query DLQ.",
        )

    if not rows:
        return make_error_response(
            status_code=404,
            code="NOT_FOUND",
            message=f"No DLQ entry found with envelope_id: {envelope_id}",
        )

    return JSONResponse(
        status_code=200,
        content=_format_entry(rows[0], include_full_payload=True),
    )
