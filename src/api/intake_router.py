"""
Phase 856B — Intake Request Router
/intake/request

Receives structured intake submissions from /get-started.
Stores in the intake_requests table for admin review.
Returns a reference ID. Does NOT create any user accounts or permissions.

This is the gated top of the funnel:
  Visitor → Get Started → intake_requests table → Admin reviews → Pipeline A or B invite
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_db():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


class IntakeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=3, max_length=320)
    company: Optional[str] = Field(None, max_length=200)
    portfolio_size: Optional[str] = Field(None, max_length=50)
    message: Optional[str] = Field(None, max_length=2000)
    source: str = Field("get-started", max_length=50)


@router.post(
    "/intake/request",
    tags=["public"],
    summary="Submit an access request (Phase 856B — intake funnel top)",
    status_code=201,
)
async def create_intake_request(body: IntakeRequest) -> JSONResponse:
    """
    POST /intake/request

    Public endpoint — no auth required.
    Accepts intake form submissions from /get-started.
    Saves to intake_requests table. Returns reference_id.
    No accounts created, no permissions granted.
    """
    reference_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    try:
        db = _get_db()
        db.table("intake_requests").insert({
            "id": str(uuid.uuid4()),
            "reference_id": reference_id,
            "name": body.name.strip(),
            "email": body.email.strip().lower(),
            "company": (body.company or "").strip() or None,
            "portfolio_size": body.portfolio_size or None,
            "message": (body.message or "").strip() or None,
            "source": body.source,
            "status": "pending_review",
            "created_at": now,
        }).execute()
    except Exception as exc:
        logger.exception("intake/request: DB insert failed: %s", exc)
        return JSONResponse(status_code=500, content={
            "error": "INTERNAL_ERROR",
            "message": "Failed to save your request. Please email info@domaniqo.com.",
        })

    logger.info(
        "intake/request: new request reference=%s email=%s company=%s",
        reference_id, body.email, body.company,
    )

    return JSONResponse(status_code=201, content={
        "status": "received",
        "reference_id": reference_id,
        "message": (
            "Your request has been received. "
            "We'll review it and be in touch at the email you provided."
        ),
    })
