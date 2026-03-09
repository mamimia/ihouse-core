"""
Phase 140 — Outbound Executor Router

Updated from Phase 138:
  Phase 139 — real adapters wired via registry.
  Phase 140 — check_in / check_out fetched from booking_state and forwarded
               to execute_sync_plan() so iCal adapters emit real DTSTART/DTEND.

POST /internal/sync/execute

End-to-end pipeline:
  1. Accept a booking_id in the body.
  2. Resolve property_id from booking_state (same as Phase 137 trigger).
  3. Fetch channel mappings + registry.
  4. Build sync_plan via build_sync_plan() (Phase 137 service).
  5. Execute the plan via execute_sync_plan() (Phase 138 service).
  6. Return execution_report.

This endpoint combines Phase 137 (plan) + Phase 138 (execute) in a single call.
Callers who want just the plan can still use POST /internal/sync/trigger.

Response schema:
    {
        "booking_id":    "bk-airbnb-HZ001",
        "property_id":   "prop-villa-alpha",
        "tenant_id":     "tenant-001",
        "total_actions": 3,
        "ok_count":      1,
        "failed_count":  0,
        "skip_count":    2,
        "dry_run":       true,
        "results": [
            {
                "provider":    "airbnb",
                "external_id": "HZ12345",
                "strategy":    "api_first",
                "status":      "dry_run",
                "http_status": null,
                "message":     "[Phase 138 stub] api_first dispatched..."
            }
        ]
    }

Invariants:
    - JWT auth required.
    - Never writes to any booking table.
    - apply_envelope is NOT involved.
    - 404 if booking not found.
    - 200 with empty results if no channel mappings exist.
    - All Phase 138 adapter calls are dry-run stubs.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response
from services.outbound_sync_trigger import build_sync_plan
from services.outbound_executor import execute_sync_plan, serialise_report

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# POST /internal/sync/execute
# ---------------------------------------------------------------------------

@router.post(
    "/internal/sync/execute",
    tags=["sync"],
    summary="Execute outbound sync plan for a booking (Phase 138)",
    description=(
        "Combines Phase 137 (plan) + Phase 138 (execute) into a single call.\\n\\n"
        "Builds the sync plan for the given booking, then dispatches each "
        "non-skip action to the appropriate outbound adapter.\\n\\n"
        "**Phase 138 adapters are stubs** — they log intent and return `dry_run` "
        "status. Real OTA API calls are implemented in Phase 139.\\n\\n"
        "**404** if booking not found.\\n"
        "**200** with empty results if property has no channel mappings.\\n\\n"
        "For plan-only (no execution), use `POST /internal/sync/trigger`."
    ),
    responses={
        200: {"description": "Execution report."},
        400: {"description": "Invalid request body."},
        401: {"description": "Missing or invalid JWT token."},
        404: {"description": "Booking not found."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def execute_sync(
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    booking_id = body.get("booking_id")
    if not booking_id or not str(booking_id).strip():
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'booking_id' is required and must be a non-empty string."},
        )

    booking_id = str(booking_id).strip()

    try:
        db = client if client is not None else _get_supabase_client()

        # ---- Resolve property_id, check_in, check_out from booking_state ----
        booking_result = (
            db.table("booking_state")
            .select("property_id, tenant_id, check_in, check_out")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        booking_rows: List[Dict[str, Any]] = booking_result.data or []
        if not booking_rows:
            return make_error_response(
                status_code=404,
                code="NOT_FOUND",
                extra={"detail": f"Booking '{booking_id}' not found for this tenant."},
            )

        property_id: str = booking_rows[0].get("property_id", "")

        # Phase 140 — convert ISO dates to compact iCal format (YYYYMMDD)
        def _to_ical(iso: object) -> Optional[str]:
            if not iso:
                return None
            return str(iso).replace("-", "")[:8]

        check_in:  Optional[str] = _to_ical(booking_rows[0].get("check_in"))
        check_out: Optional[str] = _to_ical(booking_rows[0].get("check_out"))

        # ---- Fetch channel mappings ----------------------------------------
        channels_result = (
            db.table("property_channel_map")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .execute()
        )
        channels: List[Dict[str, Any]] = channels_result.data or []

        if not channels:
            return JSONResponse(
                status_code=200,
                content={
                    "booking_id":    booking_id,
                    "property_id":   property_id,
                    "tenant_id":     tenant_id,
                    "total_actions": 0,
                    "ok_count":      0,
                    "failed_count":  0,
                    "skip_count":    0,
                    "dry_run":       True,
                    "results":       [],
                },
            )

        # ---- Fetch registry -------------------------------------------------
        registry_result = (
            db.table("provider_capability_registry")
            .select("*")
            .execute()
        )
        registry_rows: List[Dict[str, Any]] = registry_result.data or []
        registry: Dict[str, Dict[str, Any]] = {
            row["provider"]: row for row in registry_rows if row.get("provider")
        }

        # ---- Build plan (Phase 137) + Execute (Phase 138) ------------------
        actions = build_sync_plan(
            booking_id=booking_id,
            property_id=property_id,
            channels=channels,
            registry=registry,
        )

        report = execute_sync_plan(
            booking_id=booking_id,
            property_id=property_id,
            tenant_id=tenant_id,
            actions=actions,
            check_in=check_in,    # Phase 140
            check_out=check_out,  # Phase 140
        )

        return JSONResponse(status_code=200, content=serialise_report(report))

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "POST /internal/sync/execute error for booking=%s tenant=%s: %s",
            booking_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
