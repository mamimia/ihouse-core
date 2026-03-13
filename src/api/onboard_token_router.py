"""
Onboard Token Flow Router — Phase 402
========================================

Public owner self-service property onboarding via access tokens (Phase 399).

Endpoints:
    GET  /onboard/validate/{token}  — Validate an onboard token
    POST /onboard/submit            — Submit property (consumes token)
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.access_token_service import (
    TokenType,
    verify_access_token,
    validate_and_consume,
    _hash_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["onboard"])


def _get_db() -> Any:  # pragma: no cover
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class OnboardSubmitRequest(BaseModel):
    token: str = Field(..., description="Onboard access token")
    property_name: str = Field(..., description="Property name")
    property_type: str = Field("apartment", description="Property type")
    address: str = Field("", description="Full address")
    capacity: str = Field("", description="Max guests")
    contact_name: str = Field("", description="Owner contact name")
    contact_phone: str = Field("", description="Owner phone")
    contact_email: str = Field("", description="Owner email")
    wifi_name: str = Field("", description="Wi-Fi network name")
    wifi_password: str = Field("", description="Wi-Fi password")
    house_rules: str = Field("", description="House rules (newline-separated)")
    special_notes: str = Field("", description="Special notes")


# ---------------------------------------------------------------------------
# Public endpoints (no JWT — for onboarding pages)
# ---------------------------------------------------------------------------

@router.get(
    "/onboard/validate/{token}",
    summary="Validate an onboard token (Phase 402)",
)
async def validate_onboard_token(token: str) -> JSONResponse:
    """
    GET /onboard/validate/{token}

    Public endpoint. Returns 200 if the token is valid for onboarding.
    Frontend only checks r.ok status — minimal response needed.
    """
    # 1. Crypto verification
    claims = verify_access_token(token, expected_type=TokenType.ONBOARD)
    if not claims:
        return JSONResponse(status_code=401, content={
            "valid": False,
            "error": "ONBOARD_TOKEN_INVALID_OR_EXPIRED",
        })

    # 2. DB check: not used, not revoked
    try:
        db = _get_db()
        token_hash = _hash_token(token)
        res = (
            db.table("access_tokens")
            .select("id, used_at, revoked_at")
            .eq("token_hash", token_hash)
            .eq("token_type", "onboard")
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if rows:
            row = rows[0]
            if row.get("revoked_at"):
                return JSONResponse(status_code=401, content={"valid": False, "error": "TOKEN_REVOKED"})
            if row.get("used_at"):
                return JSONResponse(status_code=401, content={"valid": False, "error": "TOKEN_ALREADY_USED"})
    except Exception:
        pass  # If DB check fails, trust HMAC

    return JSONResponse(status_code=200, content={"valid": True})


@router.post(
    "/onboard/submit",
    summary="Submit property via onboard token (Phase 402)",
    status_code=201,
)
async def onboard_submit(body: OnboardSubmitRequest) -> JSONResponse:
    """
    POST /onboard/submit

    Public endpoint. Consumes the onboard token (one-use) and creates
    a property record in pending_review status in the properties table.
    """
    db = _get_db()

    # 1. Consume the token (HMAC + DB verify + mark used)
    claims = validate_and_consume(
        raw_token=body.token,
        expected_type=TokenType.ONBOARD,
        db=db,
    )

    if not claims:
        return JSONResponse(status_code=401, content={
            "error": "TOKEN_INVALID",
            "message": "This onboarding link is invalid, expired, or has already been used.",
        })

    # 2. Parse house_rules from newline-separated string to list
    house_rules = [r.strip() for r in body.house_rules.split("\n") if r.strip()] if body.house_rules else []

    # 3. Insert property record (pending_review)
    tenant_id = claims.get("entity_id", "")
    property_data = {
        "tenant_id": tenant_id,
        "name": body.property_name,
        "property_type": body.property_type,
        "address": body.address,
        "capacity": int(body.capacity) if body.capacity.isdigit() else None,
        "contact_name": body.contact_name,
        "contact_phone": body.contact_phone,
        "contact_email": body.contact_email or claims.get("email", ""),
        "wifi_name": body.wifi_name,
        "wifi_password": body.wifi_password,
        "house_rules": house_rules,
        "special_notes": body.special_notes,
        "status": "pending_review",
    }

    try:
        res = db.table("properties").insert(property_data).execute()
        property_row = res.data[0] if res.data else {}
        property_id = property_row.get("property_id", property_row.get("id", ""))
    except Exception as exc:
        logger.exception("onboard_submit property insert error: %s", exc)
        return JSONResponse(status_code=500, content={
            "error": "PROPERTY_INSERT_FAILED",
            "message": "Failed to create property. Please try again.",
        })

    # 4. Log audit event
    try:
        db.table("audit_events").insert({
            "tenant_id": tenant_id,
            "event_type": "property_onboarded",
            "entity_type": "property",
            "entity_id": property_id,
            "payload": {
                "property_name": body.property_name,
                "submitted_by_email": claims.get("email"),
                "token_type": "onboard",
            },
        }).execute()
    except Exception:
        pass  # Best-effort audit

    logger.info("onboard: property submitted name=%s tenant=%s", body.property_name, tenant_id)

    return JSONResponse(
        status_code=201,
        content={
            "status": "submitted",
            "property_id": property_id,
            "property_name": body.property_name,
            "message": "Your property has been submitted for review.",
        },
    )
