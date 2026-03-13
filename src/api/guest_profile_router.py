"""
Phase 159 — Guest Profile Router

GET /bookings/{booking_id}/guest-profile

Returns extracted PII (guest name, email, phone) for a booking.
Data is sourced from the `guest_profile` table (never event_log).

Rules:
  - JWT auth required.
  - Tenant isolation: only data for the authenticated tenant is returned.
  - 404 returned if booking exists but no guest profile has been extracted yet.
  - 404 returned for cross-tenant requests (no 403 to avoid existence leak).
  - Read-only. Never writes to any table.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

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
# GET /bookings/{booking_id}/guest-profile
# ---------------------------------------------------------------------------

@router.get(
    "/bookings/{booking_id}/guest-profile",
    tags=["bookings", "guest"],
    summary="Retrieve extracted guest profile for a booking (Phase 159)",
    description=(
        "Returns the canonical guest profile (name, email, phone) extracted from "
        "the OTA webhook payload at booking creation time.\\n\\n"
        "**Source:** `guest_profile` table only. Never reads `event_log`.\\n\\n"
        "**404** if no guest profile exists for this booking + tenant.\\n\\n"
        "**PII note:** This endpoint returns PII. Ensure appropriate access control."
    ),
    responses={
        200: {"description": "Guest profile for the booking."},
        401: {"description": "Missing or invalid JWT."},
        404: {"description": "No guest profile found for this booking."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_guest_profile(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /bookings/{booking_id}/guest-profile

    Retrieves the guest profile from the `guest_profile` table.
    Tenant-scoped — cross-tenant reads return 404.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("guest_profile")
            .select("*")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )

        if not (result.data or []):
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                extra={
                    "booking_id": booking_id,
                    "detail": "No guest profile found for this booking.",
                },
            )

        row = result.data[0]
        return JSONResponse(
            status_code=200,
            content={
                "booking_id":  row.get("booking_id"),
                "tenant_id":   row.get("tenant_id"),
                "guest_name":  row.get("guest_name"),
                "guest_email": row.get("guest_email"),
                "guest_phone": row.get("guest_phone"),
                "source":      row.get("source"),
                "created_at":  row.get("created_at"),
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /bookings/%s/guest-profile error for tenant=%s: %s",
            booking_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /guests/extract-batch  (Phase 471 — Guest Profile Real Data)
# ---------------------------------------------------------------------------

@router.post(
    "/guests/extract-batch",
    tags=["guest"],
    summary="Batch-extract guest profiles from existing booking payloads (Phase 471)",
    responses={
        200: {"description": "Extraction results: how many profiles created"},
        401: {"description": "Missing or invalid JWT"},
    },
)
async def extract_batch_guest_profiles(
    provider: Optional[str] = None,
    limit: int = 50,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Phase 471: Batch-extract guest profiles from booking_state payloads.

    Scans booking_state for bookings that don't yet have a guest_profile row.
    For each, runs the guest profile extractor on last_payload and persists
    the result to guest_profile.

    **Query parameters:**
    - `provider` — filter by OTA provider (optional)
    - `limit` — max bookings to process (1–100, default 50)
    """
    limit = max(1, min(limit, 100))

    try:
        from adapters.ota.guest_profile_extractor import extract_guest_profile

        db = client if client is not None else _get_supabase_client()

        # Get bookings from booking_state
        query = (
            db.table("booking_state")
            .select("booking_id,provider,last_payload")
            .eq("tenant_id", tenant_id)
        )
        if provider:
            query = query.eq("provider", provider)
        bookings = query.limit(limit).execute()

        rows = bookings.data or []
        created = 0
        skipped = 0
        errors = 0

        for row in rows:
            try:
                booking_id = row.get("booking_id", "")
                prov = row.get("provider", "")
                last_payload = row.get("last_payload") or {}

                # Check if profile already exists
                existing = (
                    db.table("guest_profile")
                    .select("booking_id")
                    .eq("booking_id", booking_id)
                    .eq("tenant_id", tenant_id)
                    .limit(1)
                    .execute()
                )
                if existing.data:
                    skipped += 1
                    continue

                # Extract guest profile from payload
                profile = extract_guest_profile(prov, last_payload)
                if profile.is_empty():
                    skipped += 1
                    continue

                # Persist
                db.table("guest_profile").insert({
                    "booking_id": booking_id,
                    "tenant_id": tenant_id,
                    "guest_name": profile.guest_name,
                    "guest_email": profile.guest_email,
                    "guest_phone": profile.guest_phone,
                    "source": profile.source,
                }).execute()

                created += 1
                logger.info("guests/extract-batch: created profile for %s", booking_id)
            except Exception as exc:
                logger.warning("guests/extract-batch: error for %s: %s", row.get("booking_id"), exc)
                errors += 1

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "scanned": len(rows),
                "created": created,
                "skipped": skipped,
                "errors": errors,
            },
        )

    except Exception as exc:
        logger.exception("POST /guests/extract-batch error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /guests/stats  (Phase 471)
# ---------------------------------------------------------------------------

@router.get(
    "/guests/stats",
    tags=["guest"],
    summary="Guest profile coverage stats (Phase 471)",
    responses={
        200: {"description": "Profile coverage by provider"},
        401: {"description": "Missing or invalid JWT"},
    },
)
async def guest_profile_stats(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Phase 471: Report guest profile coverage — how many bookings have
    a guest profile vs how many exist in booking_state.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        # Count bookings
        bookings_result = (
            db.table("booking_state")
            .select("provider", count="exact")
            .eq("tenant_id", tenant_id)
            .execute()
        )

        # Count profiles
        profiles_result = (
            db.table("guest_profile")
            .select("source", count="exact")
            .eq("tenant_id", tenant_id)
            .execute()
        )

        total_bookings = bookings_result.count if hasattr(bookings_result, "count") else len(bookings_result.data or [])
        total_profiles = profiles_result.count if hasattr(profiles_result, "count") else len(profiles_result.data or [])

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "total_bookings": total_bookings,
                "total_profiles": total_profiles,
                "coverage_pct": round(total_profiles / max(total_bookings, 1) * 100, 1),
            },
        )

    except Exception as exc:
        logger.exception("GET /guests/stats error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
