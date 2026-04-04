"""
Phase 1062 — Canonical Payout Persistence API

Replaces the calculation-only POST /admin/financial/payout endpoint with a real
payout lifecycle system backed by the owner_payouts table.

Endpoints:
    POST   /admin/payouts                    — Create (persist) a new payout record
    GET    /admin/payouts                    — List payouts (tenant / property / status filter)
    GET    /admin/payouts/{payout_id}        — Get a single payout
    POST   /admin/payouts/{payout_id}/submit — draft → pending
    POST   /admin/payouts/{payout_id}/approve — pending → approved
    POST   /admin/payouts/{payout_id}/mark-paid — approved → paid
    POST   /admin/payouts/{payout_id}/void   — any → voided
    GET    /admin/payouts/{payout_id}/history — full audit event trail

Authorization:
    All endpoints require the "financial" capability (admin always allowed,
    manager only if delegated). Mirrors financial_writer_router.py pattern.

Design:
    No payout was retrievable before Phase 1062 — payout_id was a session reference only.
    After this phase: all payouts are persisted, addressable by UUID, and have
    full status lifecycle + audit trail.
"""
from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_auth, jwt_identity
from api.capability_guard import require_capability
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["payouts"])


def _db() -> Any:
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreatePayoutRequest(BaseModel):
    property_id: str = Field(..., description="Property ID")
    period_start: str = Field(..., description="Period start date (YYYY-MM-DD)")
    period_end: str = Field(..., description="Period end date (YYYY-MM-DD)")
    mgmt_fee_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="Management fee %")
    notes: str = Field(default="", description="Optional notes")
    initial_status: str = Field(
        default="draft",
        description="Initial status: 'draft' (default) or 'pending' to submit immediately",
    )


class TransitionRequest(BaseModel):
    notes: str = Field(default="", description="Optional transition notes")
    payment_reference: Optional[str] = Field(
        default=None,
        description="Payment reference (required for mark-paid: bank ref, transfer ID, etc.)",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _actor(identity: dict, tenant_id: str) -> str:
    return identity.get("user_id") or tenant_id


def _not_found(payout_id: str) -> JSONResponse:
    return make_error_response(
        status_code=404,
        code=ErrorCode.BOOKING_NOT_FOUND,
        message=f"Payout {payout_id} not found",
        extra={"payout_id": payout_id},
    )


# ---------------------------------------------------------------------------
# POST /admin/payouts — Create and persist a payout
# ---------------------------------------------------------------------------

@router.post(
    "/admin/payouts",
    summary="Create and persist a canonical owner payout record (Phase 1062)",
    responses={
        201: {"description": "Payout created and persisted."},
        400: {"description": "Validation error or duplicate period."},
        401: {"description": "Missing or invalid JWT."},
        403: {"description": "CAPABILITY_DENIED — requires financial capability."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def create_payout(
    body: CreatePayoutRequest,
    tenant_id: str = Depends(jwt_auth),
    identity: dict = Depends(jwt_identity),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Calculate the payout from booking_financial_facts for the given property+period,
    then persist it to owner_payouts. Returns the full payout record with a stable UUID.

    Unlike the old POST /admin/financial/payout, this result is retrievable later.
    """
    from services.payout_service import create_payout as _create

    db = client or _db()
    actor = _actor(identity, tenant_id)

    result = _create(
        db,
        tenant_id=tenant_id,
        property_id=body.property_id,
        period_start=body.period_start,
        period_end=body.period_end,
        mgmt_fee_pct=body.mgmt_fee_pct,
        actor_id=actor,
        notes=body.notes,
        initial_status=body.initial_status,
    )

    if "error" in result:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   message=result["error"])
    return JSONResponse(status_code=201, content=result)


# ---------------------------------------------------------------------------
# GET /admin/payouts — List payouts
# ---------------------------------------------------------------------------

@router.get(
    "/admin/payouts",
    summary="List owner payouts for a tenant (Phase 1062)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_payouts(
    property_id: Optional[str] = Query(default=None, description="Filter by property ID"),
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: draft | pending | approved | paid | voided",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    from services.payout_service import list_payouts as _list

    db = client or _db()
    rows = _list(db, tenant_id=tenant_id, property_id=property_id, status=status, limit=limit)

    return JSONResponse(status_code=200, content={
        "payouts": rows,
        "count": len(rows),
        "filters": {"property_id": property_id, "status": status},
    })


# ---------------------------------------------------------------------------
# GET /admin/payouts/{payout_id} — Get single payout
# ---------------------------------------------------------------------------

@router.get(
    "/admin/payouts/{payout_id}",
    summary="Get a single owner payout by ID (Phase 1062)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_payout(
    payout_id: str,
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    from services.payout_service import get_payout as _get

    db = client or _db()
    payout = _get(db, payout_id=payout_id, tenant_id=tenant_id)
    if not payout:
        return _not_found(payout_id)
    return JSONResponse(status_code=200, content=payout)


# ---------------------------------------------------------------------------
# GET /admin/payouts/{payout_id}/history — Audit trail
# ---------------------------------------------------------------------------

@router.get(
    "/admin/payouts/{payout_id}/history",
    summary="Full audit event trail for a payout (Phase 1062)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_payout_history(
    payout_id: str,
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    from services.payout_service import get_payout as _get, get_payout_history as _history

    db = client or _db()
    payout = _get(db, payout_id=payout_id, tenant_id=tenant_id)
    if not payout:
        return _not_found(payout_id)
    events = _history(db, payout_id=payout_id, tenant_id=tenant_id)
    return JSONResponse(status_code=200, content={"payout_id": payout_id, "events": events})


# ---------------------------------------------------------------------------
# Transition helpers
# ---------------------------------------------------------------------------

async def _transition(
    payout_id: str,
    to_status: str,
    body: TransitionRequest,
    tenant_id: str,
    identity: dict,
    client: Optional[Any],
) -> JSONResponse:
    from services.payout_service import transition_status

    db = client or _db()
    actor = _actor(identity, tenant_id)

    result = transition_status(
        db,
        payout_id=payout_id,
        tenant_id=tenant_id,
        to_status=to_status,
        actor_id=actor,
        payment_reference=body.payment_reference,
        notes=body.notes,
    )

    if "error" in result:
        if "not_found" in str(result.get("error", "")):
            return _not_found(payout_id)
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR, message=result["error"]
        )
    return JSONResponse(status_code=200, content=result)


# ---------------------------------------------------------------------------
# POST /admin/payouts/{payout_id}/submit — draft → pending
# ---------------------------------------------------------------------------

@router.post(
    "/admin/payouts/{payout_id}/submit",
    summary="Submit payout for approval: draft → pending (Phase 1062)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def submit_payout(
    payout_id: str,
    body: TransitionRequest = TransitionRequest(),
    tenant_id: str = Depends(jwt_auth),
    identity: dict = Depends(jwt_identity),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    return await _transition(payout_id, "pending", body, tenant_id, identity, client)


# ---------------------------------------------------------------------------
# POST /admin/payouts/{payout_id}/approve — pending → approved
# ---------------------------------------------------------------------------

@router.post(
    "/admin/payouts/{payout_id}/approve",
    summary="Approve payout: pending → approved (Phase 1062)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def approve_payout(
    payout_id: str,
    body: TransitionRequest = TransitionRequest(),
    tenant_id: str = Depends(jwt_auth),
    identity: dict = Depends(jwt_identity),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    return await _transition(payout_id, "approved", body, tenant_id, identity, client)


# ---------------------------------------------------------------------------
# POST /admin/payouts/{payout_id}/mark-paid — approved → paid
# ---------------------------------------------------------------------------

@router.post(
    "/admin/payouts/{payout_id}/mark-paid",
    summary="Confirm payment disbursement: approved → paid (Phase 1062)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def mark_payout_paid(
    payout_id: str,
    body: TransitionRequest = TransitionRequest(),
    tenant_id: str = Depends(jwt_auth),
    identity: dict = Depends(jwt_identity),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    return await _transition(payout_id, "paid", body, tenant_id, identity, client)


# ---------------------------------------------------------------------------
# POST /admin/payouts/{payout_id}/void — any pre-paid → voided
# ---------------------------------------------------------------------------

@router.post(
    "/admin/payouts/{payout_id}/void",
    summary="Void a payout (draft/pending/approved only) (Phase 1062)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def void_payout(
    payout_id: str,
    body: TransitionRequest = TransitionRequest(),
    tenant_id: str = Depends(jwt_auth),
    identity: dict = Depends(jwt_identity),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    return await _transition(payout_id, "voided", body, tenant_id, identity, client)
