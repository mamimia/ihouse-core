"""
Notification Dispatch Router — Phase 299
==========================================

Outbound dispatch endpoints for SMS and Email.
Integrates with Phase 298 guest token issuance for one-step
"issue token + notify guest" flows.

Endpoints:
    POST /notifications/send-sms         — Send SMS to a phone number
    POST /notifications/send-email       — Send email
    POST /notifications/guest-token-send — Issue guest token AND send to guest (one-step)
    GET  /notifications/log              — List notification log for the caller

All endpoints require JWT auth (caller_id = operator).
Dispatch is best-effort — responses always 200/201, status in body.
"""
from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field

from api.auth import jwt_auth
from services.notification_dispatcher import (
    dispatch_sms,
    dispatch_email,
    dispatch_guest_token_notification,
    list_notification_log,
)
from services.guest_token import issue_guest_token, record_guest_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])

_DEFAULT_PORTAL_URL = "https://app.domaniqo.com"


def _get_db():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SendSmsRequest(BaseModel):
    to_number: str = Field(..., description="Recipient phone number in E.164 format (+66xxxxxxxxx)")
    body: str = Field(..., min_length=1, max_length=1600)
    notification_type: str = Field("generic", description="'generic' | 'task_alert' | 'booking_confirm'")
    reference_id: str | None = Field(None, description="booking_ref, task_id, etc. for audit")


class SendEmailRequest(BaseModel):
    to_email: str = Field(..., description="Recipient email address")
    subject: str = Field(..., min_length=1, max_length=200)
    body_html: str = Field(..., min_length=1)
    notification_type: str = Field("generic")
    reference_id: str | None = Field(None)


class GuestTokenSendRequest(BaseModel):
    booking_ref: str = Field(..., description="The booking reference for the guest token")
    to_phone: str | None = Field(None, description="Phone number to send token to (E.164)")
    to_email: str | None = Field(None, description="Email to send token to")
    guest_name: str = Field("Guest", description="Guest name for personalising the message")
    guest_email_for_token: str = Field("", description="Email embedded in the token (audit)")
    ttl_days: int = Field(7, ge=1, le=30)
    portal_base_url: str = Field(_DEFAULT_PORTAL_URL)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/send-sms",
    summary="Send an outbound SMS (Phase 299)",
    tags=["notifications"],
)
async def send_sms(
    body: SendSmsRequest,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    POST /notifications/send-sms

    Send an SMS to a phone number via Twilio.
    In dry-run mode (env vars not set), logs status='dry_run' and returns 200.

    Returns: { notification_id, status, channel, recipient }
    """
    db = _get_db()
    result = dispatch_sms(
        db=db,
        tenant_id=caller_id,
        to_number=body.to_number,
        body=body.body,
        notification_type=body.notification_type,
        reference_id=body.reference_id,
    )
    return JSONResponse(status_code=200, content=result)


@router.post(
    "/send-email",
    summary="Send an outbound email (Phase 299)",
    tags=["notifications"],
)
async def send_email(
    body: SendEmailRequest,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    POST /notifications/send-email

    Send an email via SendGrid.
    In dry-run mode (env vars not set), logs status='dry_run' and returns 200.

    Returns: { notification_id, status, channel, recipient }
    """
    db = _get_db()
    result = dispatch_email(
        db=db,
        tenant_id=caller_id,
        to_email=body.to_email,
        subject=body.subject,
        body_html=body.body_html,
        notification_type=body.notification_type,
        reference_id=body.reference_id,
    )
    return JSONResponse(status_code=200, content=result)


@router.post(
    "/guest-token-send",
    summary="Issue guest token AND send to guest in one step (Phase 299)",
    status_code=201,
    tags=["notifications"],
)
async def guest_token_send(
    body: GuestTokenSendRequest,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    POST /notifications/guest-token-send

    One-step flow:
      1. Issues a signed HMAC-SHA256 guest token for the booking.
      2. Records the token hash in the `guest_tokens` DB table.
      3. Sends the portal link via SMS (if to_phone) and/or Email (if to_email).
      4. Logs all dispatches to `notification_log`.

    The raw token is NOT returned in the response (security).
    Returns notification results + token_id.

    At least one of `to_phone` or `to_email` must be provided.
    """
    if not body.to_phone and not body.to_email:
        return JSONResponse(
            status_code=422,
            content={"error": "MISSING_RECIPIENT", "message": "Provide to_phone and/or to_email."},
        )

    if not os.environ.get("IHOUSE_GUEST_TOKEN_SECRET"):
        return JSONResponse(
            status_code=503,
            content={"error": "GUEST_TOKEN_NOT_CONFIGURED",
                     "message": "IHOUSE_GUEST_TOKEN_SECRET is not set."},
        )

    # Issue the token
    try:
        raw_token, exp = issue_guest_token(
            booking_ref=body.booking_ref,
            guest_email=body.guest_email_for_token,
            ttl_seconds=body.ttl_days * 86_400,
        )
    except RuntimeError as exc:
        return JSONResponse(
            status_code=503,
            content={"error": "GUEST_TOKEN_NOT_CONFIGURED", "message": str(exc)},
        )

    db = _get_db()

    # Record token hash
    token_record = record_guest_token(
        db=db,
        booking_ref=body.booking_ref,
        tenant_id=caller_id,
        raw_token=raw_token,
        exp=exp,
        guest_email=body.guest_email_for_token,
    )

    # Dispatch notifications
    dispatch_results = dispatch_guest_token_notification(
        db=db,
        tenant_id=caller_id,
        booking_ref=body.booking_ref,
        raw_token=raw_token,
        portal_base_url=body.portal_base_url,
        to_phone=body.to_phone,
        to_email=body.to_email,
        guest_name=body.guest_name,
    )

    logger.info(
        "guest-token-send: booking=%s channels=%d tenant=%s",
        body.booking_ref, len(dispatch_results), caller_id,
    )

    return JSONResponse(
        status_code=201,
        content={
            "booking_ref": body.booking_ref,
            "token_id": token_record.get("token_id"),
            "notifications": dispatch_results,
            "channels_used": len(dispatch_results),
        },
    )


@router.get(
    "/log",
    summary="List notification dispatch log for the caller (Phase 299)",
    tags=["notifications"],
)
async def get_notification_log(
    caller_id: Annotated[str, Depends(jwt_auth)],
    limit: int = Query(50, ge=1, le=200),
    reference_id: str | None = Query(None, description="Filter by booking_ref, task_id etc."),
) -> JSONResponse:
    """
    GET /notifications/log?limit=50&reference_id=BOOKING-123

    Returns the notification history for the authenticated operator.
    Results are newest-first. PII fields (recipient) are included — callers
    must have appropriate operator-level JWT access.
    """
    db = _get_db()
    entries = list_notification_log(
        db=db,
        tenant_id=caller_id,
        limit=limit,
        reference_id=reference_id,
    )
    return JSONResponse(
        status_code=200,
        content={"entries": entries, "count": len(entries)},
    )
