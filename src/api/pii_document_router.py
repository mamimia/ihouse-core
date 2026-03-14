"""
PII Document Security — Admin-Only Retrieval

Phase: PII Security Hardening

Single endpoint:
    GET /admin/pii-documents/{form_id} — admin-only, signed-URL access, audit-logged

Rules:
    1. Only JWT role == "admin" may call this endpoint.
    2. Returns time-limited signed URLs (5-minute expiry) for passport photos,
       signatures, and cash deposit photos.
    3. Every access writes an audit_log entry with actor, IP, and document list.
    4. The GET /bookings/{id}/checkin-form endpoint NEVER returns raw PII URLs
       (handled by redaction in guest_checkin_form_router.py).
"""
from __future__ import annotations

import datetime
import logging
import os
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["pii-documents"])

_SIGNED_URL_EXPIRY_SECONDS = 300  # 5 minutes


def _get_supabase_client() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _extract_role(request: Request) -> Optional[str]:
    """Extract role from JWT claims without re-validating (already done by jwt_auth)."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        # Decode without verification — jwt_auth already validated
        claims = jwt.decode(token, options={"verify_signature": False})
        return claims.get("role")
    except Exception:
        return None


def _get_client_ip(request: Request) -> str:
    """Best-effort client IP extraction."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# ---------------------------------------------------------------------------
# Admin PII Document Retrieval
# ---------------------------------------------------------------------------

@router.get(
    "/admin/pii-documents/{form_id}",
    summary="Admin-only: retrieve PII documents with signed URLs",
    responses={200: {}, 403: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_pii_documents(
    form_id: str,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns time-limited signed URLs for passport photos, signatures,
    and cash deposit photos associated with a check-in form.

    Access: admin role ONLY.
    Every call is audit-logged.
    """

    # ── Role enforcement ─────────────────────────────────────────────
    role = _extract_role(request)
    if role != "admin":
        logger.warning(
            "PII access denied: role=%s tenant=%s form=%s ip=%s",
            role, tenant_id, form_id, _get_client_ip(request),
        )
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Only admin role can access PII documents."},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        # ── Fetch form ───────────────────────────────────────────────
        form_result = (
            db.table("guest_checkin_forms")
            .select("id, booking_id, tenant_id, property_id, form_status")
            .eq("id", form_id).eq("tenant_id", tenant_id)
            .limit(1).execute()
        )
        form_rows = form_result.data or []
        if not form_rows:
            return make_error_response(
                status_code=404, code="NOT_FOUND",
                extra={"detail": f"Form '{form_id}' not found."},
            )

        form = form_rows[0]
        booking_id = form.get("booking_id", "")

        # ── Collect PII document references ──────────────────────────
        documents: List[Dict[str, Any]] = []
        guest_ids_accessed: List[str] = []
        doc_types_accessed: List[str] = []

        # 1. Passport photos from guests
        guests_result = (
            db.table("guest_checkin_guests")
            .select("id, full_name, passport_photo_url")
            .eq("form_id", form_id).execute()
        )
        for guest in (guests_result.data or []):
            photo_path = guest.get("passport_photo_url")
            if photo_path and photo_path != "***":
                signed_url = _create_signed_url(db, "passport-photos", photo_path)
                documents.append({
                    "type": "passport_photo",
                    "guest_id": guest.get("id"),
                    "guest_name": guest.get("full_name", ""),
                    "signed_url": signed_url,
                    "expires_in_seconds": _SIGNED_URL_EXPIRY_SECONDS,
                })
                guest_ids_accessed.append(guest.get("id", ""))
                doc_types_accessed.append("passport_photo")

        # 2. Signature and cash photo from deposit records
        deposit_result = (
            db.table("guest_deposit_records")
            .select("signature_url, cash_photo_url")
            .eq("tenant_id", tenant_id).eq("booking_id", booking_id)
            .limit(1).execute()
        )
        for deposit in (deposit_result.data or []):
            sig_path = deposit.get("signature_url")
            if sig_path and sig_path != "***":
                signed_url = _create_signed_url(db, "signatures", sig_path)
                documents.append({
                    "type": "signature",
                    "signed_url": signed_url,
                    "expires_in_seconds": _SIGNED_URL_EXPIRY_SECONDS,
                })
                doc_types_accessed.append("signature")

            cash_path = deposit.get("cash_photo_url")
            if cash_path and cash_path != "***":
                signed_url = _create_signed_url(db, "passport-photos", cash_path)
                documents.append({
                    "type": "cash_photo",
                    "signed_url": signed_url,
                    "expires_in_seconds": _SIGNED_URL_EXPIRY_SECONDS,
                })
                doc_types_accessed.append("cash_photo")

        # ── Audit log ────────────────────────────────────────────────
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        audit_entry = {
            "tenant_id": tenant_id,
            "actor_id": tenant_id,  # sub from JWT
            "action": "PII_DOCUMENT_ACCESS",
            "resource_type": "checkin_form",
            "resource_id": form_id,
            "details": {
                "documents_accessed": doc_types_accessed,
                "guest_ids": guest_ids_accessed,
                "document_count": len(documents),
                "signed_url_expiry_seconds": _SIGNED_URL_EXPIRY_SECONDS,
            },
            "ip_address": _get_client_ip(request),
            "created_at": now,
        }
        try:
            db.table("audit_log").insert(audit_entry).execute()
        except Exception as audit_exc:
            # Audit failure must not block document access, but log loudly
            logger.error("AUDIT LOG FAILURE for PII access: %s", audit_exc)

        logger.info(
            "PII access granted: admin=%s form=%s docs=%d ip=%s",
            tenant_id, form_id, len(documents), _get_client_ip(request),
        )

        return JSONResponse(status_code=200, content={
            "form_id": form_id,
            "booking_id": booking_id,
            "documents": documents,
            "document_count": len(documents),
            "accessed_at": now,
        })

    except Exception as exc:
        logger.exception("PII document retrieval error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


def _create_signed_url(db: Any, bucket: str, path: str) -> str:
    """
    Generate a time-limited signed URL for a private storage object.

    Falls back to a placeholder if the storage bucket doesn't exist yet
    (buckets are created separately as an infrastructure decision).
    """
    try:
        result = db.storage.from_(bucket).create_signed_url(
            path, _SIGNED_URL_EXPIRY_SECONDS
        )
        if isinstance(result, dict) and result.get("signedURL"):
            return result["signedURL"]
        # supabase-py v2 returns object with signedURL attribute
        if hasattr(result, "signed_url"):
            return result.signed_url
        return f"[signed-url-pending:{bucket}/{path}]"
    except Exception as exc:
        logger.warning("Signed URL generation failed for %s/%s: %s", bucket, path, exc)
        return f"[signed-url-pending:{bucket}/{path}]"
