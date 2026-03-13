"""
Phase 505 — Property Dashboard API Router

Dedicated API endpoints for the property_dashboard.py data service (Phase 499).

Endpoints:
    GET /admin/property-dashboard/{property_id}
        Full property dashboard: occupancy, revenue, tasks, upcoming, feedback.

    GET /admin/property-dashboard-overview
        Portfolio-level overview across all properties for this tenant.

Design:
    - JWT auth required on both endpoints.
    - Tenant isolation: tenant_id from JWT claim only.
    - Delegates to property_dashboard.py service functions.
    - Graceful degradation: each section handles its own errors.
    - No new tables — pure read from existing infrastructure.
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
router = APIRouter(tags=["property-dashboard"])


def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


@router.get(
    "/admin/property-dashboard/{property_id}",
    tags=["property-dashboard"],
    summary="Property Dashboard — single property view (Phase 505)",
    description=(
        "Comprehensive dashboard for a single property.\\n\\n"
        "Returns:\\n"
        "- **Occupancy**: current month occupied nights, occupancy %, active bookings\\n"
        "- **Revenue**: total gross, net, management fee from booking_financial_facts\\n"
        "- **Tasks**: open, in-progress, completed counts\\n"
        "- **Upcoming**: arrivals this week, next arrival\\n"
        "- **Feedback**: total reviews, average rating\\n\\n"
        "Each section degrades gracefully — returns error detail instead of failing the whole request."
    ),
    responses={
        200: {"description": "Property dashboard data."},
        401: {"description": "Missing or invalid JWT."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_property_dashboard_endpoint(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /admin/property-dashboard/{property_id}

    Full per-property dashboard aggregation.
    """
    try:
        from services.property_dashboard import get_property_dashboard

        db = client if client is not None else _get_supabase_client()
        result = get_property_dashboard(db, tenant_id, property_id)
        return JSONResponse(status_code=200, content=result)

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /admin/property-dashboard/%s error tenant=%s: %s",
            property_id, tenant_id, exc,
        )
        return make_error_response(
            status_code=500, code=ErrorCode.INTERNAL_ERROR
        )


@router.get(
    "/admin/property-dashboard-overview",
    tags=["property-dashboard"],
    summary="Portfolio Overview — all properties (Phase 505)",
    description=(
        "High-level overview across all properties for the authenticated tenant.\\n\\n"
        "Returns: total properties, total bookings, open tasks, and a list of properties."
    ),
    responses={
        200: {"description": "Portfolio overview data."},
        401: {"description": "Missing or invalid JWT."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_property_dashboard_overview_endpoint(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /admin/property-dashboard-overview

    Cross-property overview for tenant.
    """
    try:
        from services.property_dashboard import get_portfolio_overview

        db = client if client is not None else _get_supabase_client()
        result = get_portfolio_overview(db, tenant_id)
        return JSONResponse(status_code=200, content=result)

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /admin/property-dashboard-overview error tenant=%s: %s",
            tenant_id, exc,
        )
        return make_error_response(
            status_code=500, code=ErrorCode.INTERNAL_ERROR
        )
