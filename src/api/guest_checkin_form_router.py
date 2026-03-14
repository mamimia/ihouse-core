"""
Phases 606–618 — Guest Check-in Form System

Full lifecycle for guest check-in forms:
    POST /bookings/{booking_id}/checkin-form           — create form (606)
    GET  /bookings/{booking_id}/checkin-form            — get form state (606)
    POST /checkin-forms/{form_id}/guests                — add guest (607)
    POST /checkin-forms/{form_id}/guests/{guest_id}/passport-photo — upload (608)
    POST /bookings/{booking_id}/deposit                 — collect deposit (610)
    POST /checkin-forms/{form_id}/signature              — digital signature (611)
    POST /checkin-forms/{form_id}/submit                 — validate + complete (612)
    POST /bookings/{booking_id}/generate-qr              — QR code generation (613)
    GET  /guest/pre-arrival/{token}                      — pre-arrival form view (615)
    POST /guest/pre-arrival/{token}                      — pre-arrival submit (615)
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["guest-checkin"])

# ---------------------------------------------------------------------------
# PII Redaction — passport photos, signatures, cash deposit photos
# ---------------------------------------------------------------------------

_PII_URL_FIELDS = ("passport_photo_url", "signature_url", "cash_photo_url")
_REDACTED = "***"


def _redact_guest_pii(guest: Dict[str, Any]) -> Dict[str, Any]:
    """Replace PII URL with redaction marker and add boolean indicator."""
    g = dict(guest)
    if g.get("passport_photo_url"):
        g["passport_photo_captured"] = True
        g["passport_photo_url"] = _REDACTED
    else:
        g["passport_photo_captured"] = False
    return g


def _redact_deposit_pii(deposit: Dict[str, Any]) -> Dict[str, Any]:
    """Replace PII URL fields on deposit record."""
    d = dict(deposit)
    if d.get("signature_url"):
        d["signature_recorded"] = True
        d["signature_url"] = _REDACTED
    else:
        d["signature_recorded"] = False
    if d.get("cash_photo_url"):
        d["cash_photo_captured"] = True
        d["cash_photo_url"] = _REDACTED
    else:
        d["cash_photo_captured"] = False
    return d


def _get_supabase_client() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _generate_short_token(length: int = 12) -> str:
    """Generate a unique short token (nanoid-style)."""
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------------------
# Phase 606 — Create / Get check-in form
# ---------------------------------------------------------------------------

@router.post(
    "/bookings/{booking_id}/checkin-form",
    summary="Create guest check-in form (Phase 606)",
    responses={201: {}, 400: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def create_checkin_form(
    booking_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        body = {}

    guest_type = str(body.get("guest_type", "tourist")).strip().lower()
    if guest_type not in ("tourist", "resident"):
        guest_type = "tourist"

    form_language = str(body.get("form_language", "en")).strip().lower()
    if form_language not in ("en", "th", "he"):
        form_language = "en"

    property_id = str(body.get("property_id") or "").strip()

    row = {
        "tenant_id": tenant_id, "booking_id": booking_id,
        "property_id": property_id, "guest_type": guest_type,
        "form_language": form_language, "form_status": "pending",
    }

    try:
        db = client if client is not None else _get_supabase_client()

        # Check if form already exists for this booking
        existing = (
            db.table("guest_checkin_forms").select("*")
            .eq("tenant_id", tenant_id).eq("booking_id", booking_id)
            .limit(1).execute()
        )
        if (existing.data or []):
            form = existing.data[0]
            return JSONResponse(status_code=200, content={
                **form, "already_exists": True,
            })

        result = db.table("guest_checkin_forms").insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
        return JSONResponse(status_code=201, content={**rows[0], "already_exists": False})
    except Exception as exc:
        logger.exception("create checkin form error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get(
    "/bookings/{booking_id}/checkin-form",
    summary="Get check-in form state (Phase 606)",
    responses={200: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_checkin_form(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("guest_checkin_forms").select("*")
            .eq("tenant_id", tenant_id).eq("booking_id", booking_id)
            .limit(1).execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"No check-in form for booking '{booking_id}'."})

        form = rows[0]
        form_id = form.get("id")

        # Fetch guests
        guests_result = (
            db.table("guest_checkin_guests").select("*")
            .eq("form_id", form_id).order("guest_number", desc=False).execute()
        )

        # PII redaction — passport photos never returned in this endpoint
        form["guests"] = [_redact_guest_pii(g) for g in (guests_result.data or [])]

        # Redact deposit PII if embedded
        if form.get("signature_url"):
            form["signature_recorded"] = True
            form["signature_url"] = _REDACTED
        if form.get("cash_photo_url"):
            form["cash_photo_captured"] = True
            form["cash_photo_url"] = _REDACTED

        return JSONResponse(status_code=200, content=form)
    except Exception as exc:
        logger.exception("get checkin form error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 607 — Add guests to form
# ---------------------------------------------------------------------------

@router.post(
    "/checkin-forms/{form_id}/guests",
    summary="Add guest to check-in form (Phase 607)",
    responses={201: {}, 400: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def add_guest(
    form_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a JSON object."})

    full_name = str(body.get("full_name") or "").strip()
    if not full_name:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'full_name' is required."})

    row = {
        "form_id": form_id, "full_name": full_name,
        "guest_number": body.get("guest_number", 1),
        "nationality": body.get("nationality"),
        "document_type": body.get("document_type"),
        "document_number": body.get("document_number"),
        "phone": body.get("phone"),
        "email": body.get("email"),
        "is_primary": body.get("is_primary", False),
    }

    try:
        db = client if client is not None else _get_supabase_client()
        result = db.table("guest_checkin_guests").insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
        return JSONResponse(status_code=201, content=rows[0])
    except Exception as exc:
        logger.exception("add guest error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 608 — Passport photo upload
# ---------------------------------------------------------------------------

@router.post(
    "/checkin-forms/{form_id}/guests/{guest_id}/passport-photo",
    summary="Upload passport photo for guest (Phase 608)",
    responses={200: {}, 400: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def upload_passport_photo(
    form_id: str, guest_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a JSON object."})

    photo_url = str(body.get("photo_url") or "").strip()
    if not photo_url:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'photo_url' is required."})

    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("guest_checkin_guests")
            .update({"passport_photo_url": photo_url})
            .eq("id", guest_id).eq("form_id", form_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Guest '{guest_id}' not found."})
        return JSONResponse(status_code=200, content={"guest_id": guest_id, "photo_uploaded": True, "photo_url": photo_url})
    except Exception as exc:
        logger.exception("upload passport photo error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 610 — Deposit collection
# ---------------------------------------------------------------------------

@router.post(
    "/bookings/{booking_id}/deposit",
    summary="Collect deposit for booking (Phase 610)",
    responses={201: {}, 400: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def collect_deposit(
    booking_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a JSON object."})

    amount = body.get("amount")
    if amount is None:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'amount' is required."})
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'amount' must be numeric."})
    if amount <= 0:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'amount' must be > 0."})

    property_id = str(body.get("property_id") or "").strip()
    collected_by = str(body.get("collected_by") or "").strip()
    currency = str(body.get("currency", "THB")).upper()[:3]

    import datetime
    row = {
        "tenant_id": tenant_id, "booking_id": booking_id,
        "property_id": property_id, "amount": amount,
        "currency": currency, "status": "collected",
        "cash_photo_url": body.get("cash_photo_url"),
        "collected_by": collected_by,
        "collected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    try:
        db = client if client is not None else _get_supabase_client()
        result = db.table("guest_deposit_records").insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
        return JSONResponse(status_code=201, content=rows[0])
    except Exception as exc:
        logger.exception("collect deposit error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 611 — Digital signature
# ---------------------------------------------------------------------------

@router.post(
    "/checkin-forms/{form_id}/signature",
    summary="Save digital signature (Phase 611)",
    responses={200: {}, 400: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def save_signature(
    form_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a JSON object."})

    signature_url = str(body.get("signature_url") or "").strip()
    if not signature_url:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'signature_url' is required (base64 data URI or storage URL)."})

    # Store signature URL on the form's associated deposit record, or create a reference.
    # For now, we'll track it by updating the form's associated booking's deposit record.
    try:
        db = client if client is not None else _get_supabase_client()

        # Get form to find booking_id
        form_result = (
            db.table("guest_checkin_forms").select("booking_id, tenant_id")
            .eq("id", form_id).limit(1).execute()
        )
        form_rows = form_result.data or []
        if not form_rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Form '{form_id}' not found."})

        booking_id = form_rows[0].get("booking_id")

        # Update deposit record if exists
        db.table("guest_deposit_records").update({"signature_url": signature_url})\
            .eq("tenant_id", tenant_id).eq("booking_id", booking_id).execute()

        return JSONResponse(status_code=200, content={
            "form_id": form_id, "signature_saved": True,
        })
    except Exception as exc:
        logger.exception("save signature error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 612 — Submit & complete form
# ---------------------------------------------------------------------------

@router.post(
    "/checkin-forms/{form_id}/submit",
    summary="Submit and complete the check-in form (Phase 612)",
    responses={200: {}, 400: {}, 409: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def submit_form(
    form_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        body = {}

    try:
        db = client if client is not None else _get_supabase_client()

        # Get form
        form_result = (
            db.table("guest_checkin_forms").select("*")
            .eq("id", form_id).limit(1).execute()
        )
        form_rows = form_result.data or []
        if not form_rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Form '{form_id}' not found."})

        form = form_rows[0]
        if form.get("form_status") == "completed":
            return JSONResponse(status_code=200, content={
                "form_id": form_id, "already_completed": True, **form,
            })

        # Validate: at least 1 guest with name
        guests_result = (
            db.table("guest_checkin_guests").select("*")
            .eq("form_id", form_id).execute()
        )
        guests = guests_result.data or []

        validation_errors: List[str] = []
        if not guests:
            validation_errors.append("At least one guest is required.")

        has_photo = any(g.get("passport_photo_url") for g in guests)
        if guests and not has_photo:
            validation_errors.append("At least one guest must have a passport/ID photo.")

        # Check deposit if required (body.force=true bypasses)
        force = body.get("force", False)

        if validation_errors and not force:
            return JSONResponse(status_code=409, content={
                "form_id": form_id, "validation_errors": validation_errors,
                "hint": "Use force=true to bypass validation (manager override).",
            })

        # Complete the form
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        db.table("guest_checkin_forms").update({
            "form_status": "completed",
            "submitted_at": now,
            "worker_id": body.get("worker_id"),
        }).eq("id", form_id).execute()

        # PII-safe response — status indicators only, NEVER raw URLs
        passport_count = sum(1 for g in guests if g.get("passport_photo_url"))
        return JSONResponse(status_code=200, content={
            "form_id": form_id, "form_status": "completed",
            "submitted_at": now, "guest_count": len(guests),
            "passport_photo_count": passport_count,
            "passport_photos_captured": passport_count > 0,
            "validation_bypassed": bool(force and validation_errors),
        })
    except Exception as exc:
        logger.exception("submit form error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 613 — QR code generation
# ---------------------------------------------------------------------------

@router.post(
    "/bookings/{booking_id}/generate-qr",
    summary="Generate QR token for guest portal (Phase 613)",
    responses={201: {}, 400: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def generate_qr(
    booking_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        body = {}

    property_id = str(body.get("property_id") or "").strip()
    generated_by = str(body.get("generated_by") or "").strip()

    token = _generate_short_token(12)
    portal_url = f"https://app.domaniqo.com/guest/{token}"

    row = {
        "tenant_id": tenant_id, "booking_id": booking_id,
        "property_id": property_id, "token": token,
        "generated_by": generated_by, "portal_url": portal_url,
    }

    try:
        db = client if client is not None else _get_supabase_client()

        # Check if QR already exists
        existing = (
            db.table("guest_qr_tokens").select("*")
            .eq("tenant_id", tenant_id).eq("booking_id", booking_id)
            .limit(1).execute()
        )
        if (existing.data or []):
            qr = existing.data[0]
            return JSONResponse(status_code=200, content={
                **qr, "already_exists": True,
            })

        result = db.table("guest_qr_tokens").insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
        return JSONResponse(status_code=201, content={
            **rows[0], "already_exists": False,
        })
    except Exception as exc:
        logger.exception("generate QR error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 615 — Pre-arrival guest self-service
# ---------------------------------------------------------------------------

@router.get(
    "/guest/pre-arrival/{token}",
    summary="Guest pre-arrival form view (Phase 615)",
    responses={200: {}, 404: {}, 500: {}},
)
async def pre_arrival_view(token: str, client: Optional[Any] = None) -> JSONResponse:
    """Public endpoint — token-gated, no JWT."""
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("guest_qr_tokens").select("*")
            .eq("token", token).limit(1).execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": "Invalid or expired token."})

        qr = rows[0]
        booking_id = qr.get("booking_id")
        tenant_id = qr.get("tenant_id")

        # Fetch form if exists
        form_result = (
            db.table("guest_checkin_forms").select("id, form_status, guest_type, form_language")
            .eq("tenant_id", tenant_id).eq("booking_id", booking_id)
            .limit(1).execute()
        )
        form = (form_result.data or [None])[0]

        return JSONResponse(status_code=200, content={
            "booking_id": booking_id, "property_id": qr.get("property_id"),
            "form": form, "token_valid": True,
        })
    except Exception as exc:
        logger.exception("pre-arrival view error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.post(
    "/guest/pre-arrival/{token}",
    summary="Guest pre-arrival form submit (Phase 615)",
    responses={200: {}, 400: {}, 404: {}, 500: {}},
)
async def pre_arrival_submit(token: str, body: Dict[str, Any], client: Optional[Any] = None) -> JSONResponse:
    """Public endpoint — token-gated, no JWT. Saves partial form data."""
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a JSON object."})
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("guest_qr_tokens").select("*")
            .eq("token", token).limit(1).execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": "Invalid or expired token."})

        qr = rows[0]
        booking_id = qr.get("booking_id")
        tenant_id = qr.get("tenant_id")

        # Get or create form
        form_result = (
            db.table("guest_checkin_forms").select("id")
            .eq("tenant_id", tenant_id).eq("booking_id", booking_id)
            .limit(1).execute()
        )
        form_rows = form_result.data or []

        if form_rows:
            form_id = form_rows[0]["id"]
            # Update form status to partial
            db.table("guest_checkin_forms").update({
                "form_status": "partial", "filled_by": "guest_pre_arrival",
            }).eq("id", form_id).execute()
        else:
            # Create new form
            new_form = {
                "tenant_id": tenant_id, "booking_id": booking_id,
                "property_id": qr.get("property_id", ""),
                "form_status": "partial", "filled_by": "guest_pre_arrival",
                "guest_type": body.get("guest_type", "tourist"),
                "form_language": body.get("form_language", "en"),
            }
            insert_result = db.table("guest_checkin_forms").insert(new_form).execute()
            form_id = (insert_result.data or [{}])[0].get("id")

        # Add/update guest data
        guest_data = body.get("guest")
        if guest_data and isinstance(guest_data, dict) and form_id:
            full_name = str(guest_data.get("full_name") or "").strip()
            if full_name:
                guest_row = {
                    "form_id": form_id, "full_name": full_name,
                    "guest_number": 1, "is_primary": True,
                    "nationality": guest_data.get("nationality"),
                    "document_type": guest_data.get("document_type"),
                    "document_number": guest_data.get("document_number"),
                    "phone": guest_data.get("phone"),
                    "email": guest_data.get("email"),
                }
                db.table("guest_checkin_guests").insert(guest_row).execute()

        return JSONResponse(status_code=200, content={
            "booking_id": booking_id, "form_id": form_id,
            "form_status": "partial", "saved": True,
        })
    except Exception as exc:
        logger.exception("pre-arrival submit error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
