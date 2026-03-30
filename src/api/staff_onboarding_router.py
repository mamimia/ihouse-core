"""
Phase 844 — Staff Self-Onboarding API (Refactored to use Canonical Access Tokens)

End-to-End Flow:
1. Admin generates an onboarding token (POST /admin/staff-onboarding/invite)
2. Worker opens public link and submits details (POST /staff-onboarding/submit/{token})
3. Admin fetches pending requests (GET /admin/staff-onboarding)
4. Admin approves request (POST /admin/staff-onboarding/{id}/approve)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response
from services.access_token_service import (
    TokenType,
    issue_access_token,
    record_token,
    verify_access_token,
    validate_and_consume,
    _hash_token,
)

logger = logging.getLogger(__name__)

router = APIRouter()

def _get_db() -> Any:
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


from typing import Optional

class CreateOnboardingInviteRequest(BaseModel):
    email: Optional[str] = Field(None, description="Email to invite (can be used to track, optional)")
    intended_role: str = Field("worker", description="The role we intend to give them upon approval")
    intended_language: str = Field("th", description="The default language for the onboarding app")
    preselected_roles: list[str] = Field(default_factory=list, description="Worker roles preselected by admin")


@router.post(
    "/admin/staff-onboarding/invite",
    tags=["admin"],
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def create_onboarding_invite(
    body: CreateOnboardingInviteRequest,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    db = _get_db()

    # Phase 856B: token_type is now STAFF_ONBOARD (not INVITE) so Pipeline B
    # tokens are distinct from Pipeline A tokens at the DB level.
    try:
        import time
        import jwt
        secret = os.environ.get("IHOUSE_ACCESS_TOKEN_SECRET", "dev-secret")
        now = int(time.time())
        exp = now + (7 * 86400)
        claims = {
            "iss": "ihouse-core",
            "aud": "ihouse-tenant",
            "typ": "staff_onboard",   # Phase 856B: was 'invite' — now separated
            "sub": tenant_id,
            "ent": tenant_id,
            "iat": now,
            "exp": exp,
        }
        if body.email:
            claims["eml"] = body.email

        token = jwt.encode(claims, secret, algorithm="HS256")

        record = record_token(
            tenant_id=tenant_id,
            token_type=TokenType.STAFF_ONBOARD,   # Phase 856B: was INVITE
            entity_id=tenant_id,
            raw_token=token,
            exp=exp,
            email=body.email,
            metadata={
                "intended_role": body.intended_role,
                "intended_language": body.intended_language,
                "preselected_roles": body.preselected_roles,
                "status": "pending_submission"
            },
            db=db,
        )

        return JSONResponse(status_code=201, content={
            "token": token,
            "invite_url": f"/staff/apply?token={token}"
        })
    except Exception as exc:
        logger.exception("Failed to create onboarding invite: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get(
    "/staff-onboarding/validate/{token}",
    tags=["public"],
)
async def validate_onboarding(token: str) -> JSONResponse:
    db = _get_db()
    import time
    import jwt
    secret = os.environ.get("IHOUSE_ACCESS_TOKEN_SECRET", "dev-secret")
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"], audience="ihouse-tenant")
        # Phase 857 (audit C3): only accept staff_onboard tokens — legacy invite
        # tokens must go through Pipeline A, not the staff onboarding form.
        if claims.get("typ") != "staff_onboard":
            return JSONResponse(status_code=401, content={"valid": False, "error": "INVALID_TYPE"})
    except Exception:
        return JSONResponse(status_code=401, content={"valid": False, "error": "INVALID_TOKEN"})

    h = _hash_token(token)
    res = db.table("access_tokens").select("id, metadata, used_at, revoked_at").eq("token_hash", h).limit(1).execute()
    data = res.data or []
    if not data:
        return JSONResponse(status_code=404, content={"valid": False, "error": "NOT_FOUND"})
    
    row = data[0]
    # Phase 857 (audit C9): distinguish rejection from generic revoke/use
    if row.get("revoked_at"):
        row_meta = row.get("metadata") or {}
        if row_meta.get("status") == "rejected":
            return JSONResponse(status_code=410, content={
                "valid": False,
                "error": "APPLICATION_REJECTED",
                "message": "Your application was reviewed and was not approved at this time."
            })
        return JSONResponse(status_code=400, content={"valid": False, "error": "TOKEN_REVOKED"})
    if row.get("used_at"):
        return JSONResponse(status_code=400, content={"valid": False, "error": "ALREADY_USED"})
        
    meta = row.get("metadata") or {}
    if meta.get("status") != "pending_submission":
        return JSONResponse(status_code=400, content={"valid": False, "error": "ALREADY_SUBMITTED"})
    return JSONResponse(status_code=200, content={
        "valid": True, 
        "email": claims.get("eml"),
        "language": meta.get("intended_language", "th"),
        "worker_roles": meta.get("preselected_roles", [])
    })


from fastapi import UploadFile, File
from api.property_photos_router import _process_image, _ALLOWED_CONTENT_TYPES, _MAX_UPLOAD_BYTES, _TARGET_BYTES, _MAX_DIMENSION, _get_storage_public_url

@router.post(
    "/staff-onboarding/upload-photo/{token}",
    tags=["public"],
)
async def upload_onboarding_photo(token: str, file: UploadFile = File(...)) -> JSONResponse:
    db = _get_db()
    h = _hash_token(token)
    res = db.table("access_tokens").select("id, metadata, used_at, revoked_at").eq("token_hash", h).limit(1).execute()
    data = res.data or []
    if not data:
        return JSONResponse(status_code=404, content={"error": "NOT_FOUND"})
    
    row = data[0]
    if row.get("used_at") or row.get("revoked_at"):
        return JSONResponse(status_code=400, content={"error": "ALREADY_USED_OR_REVOKED"})
        
    content_type = getattr(file, "content_type", "") or ""
    if content_type == "image/jpg":
        content_type = "image/jpeg"

    if content_type not in _ALLOWED_CONTENT_TYPES:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR, extra={"detail": "Unsupported file type."})

    img_data = await file.read()
    if len(img_data) > _MAX_UPLOAD_BYTES:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR, extra={"detail": "Image is too large. Max 15MB."})

    try:
        # Use existing server compression
        full_data, ext = _process_image(img_data, _MAX_DIMENSION, _TARGET_BYTES)
    except Exception as exc:
        logger.exception("Onboarding processing error: %s", exc)
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR, extra={"detail": "Could not process image."})

    import uuid, time
    ts = int(time.time())
    uid = uuid.uuid4().hex[:8]
    full_path = f"staff_onboarding/{ts}_{uid}.{ext}"

    try:
        # INV-MEDIA-02: Staff files go to staff-documents (private), never property-photos (public)
        db.storage.from_("staff-documents").upload(
            path=full_path, file=full_data,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )
        # staff-documents is private — generate a long-lived signed URL (7 days)
        signed = db.storage.from_("staff-documents").create_signed_url(full_path, 7 * 86400)
        signed_url = signed.get("signedURL", "") if isinstance(signed, dict) else getattr(signed, "signed_url", "")
        # Also store the storage path for future URL regeneration
        base = os.environ["SUPABASE_URL"].rstrip("/")
        # Return both: the signed URL for immediate display, and the storage path for DB reference
        return JSONResponse(status_code=200, content={
            "url": signed_url,
            "storage_path": f"staff-documents/{full_path}",
        })
    except Exception as exc:
        logger.exception("Onboarding photo upload error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR, extra={"detail": str(exc)})


class OnboardingSubmitRequest(BaseModel):
    email: Optional[str] = None
    full_name: str
    first_name: str = ""
    last_name: str = ""
    display_name: str = ""  # nickname / preferred name
    phone: str = ""
    language: str = "en"
    emergency_contact: str = ""
    photo_url: str = ""
    comm_preference: Dict[str, Any] = Field(default_factory=dict)
    worker_roles: list[str] = Field(default_factory=list)

@router.post(
    "/staff-onboarding/submit/{token}",
    tags=["public"],
)
async def submit_onboarding(token: str, body: OnboardingSubmitRequest) -> JSONResponse:
    db = _get_db()
    h = _hash_token(token)
    res = db.table("access_tokens").select("id, metadata, used_at, revoked_at").eq("token_hash", h).limit(1).execute()
    data = res.data or []
    if not data:
        return JSONResponse(status_code=404, content={"error": "NOT_FOUND"})
        
    row = data[0]
    if row.get("used_at") or row.get("revoked_at"):
        return JSONResponse(status_code=400, content={"error": "ALREADY_USED_OR_REVOKED"})

    meta = row.get("metadata") or {}
    if meta.get("status") != "pending_submission":
        return JSONResponse(status_code=400, content={"error": "ALREADY_SUBMITTED"})

    # Phase 856B: validate email is resolvable before accepting submission.
    # Fail fast here — not at admin approval time (which was a bad UX surprise).
    resolved_email = (body.email or "").strip() or (row.get("email") or "").strip()
    if not resolved_email:
        return JSONResponse(status_code=400, content={
            "error": "EMAIL_REQUIRED",
            "message": "An email address is required to complete your application.",
        })
        
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        
        # update metadata
        meta["status"] = "pending_confirm"
        meta["submitted_at"] = now
        meta["worker_data"] = {
            "email": body.email,
            "full_name": body.full_name or f"{body.first_name} {body.last_name}".strip(),
            "first_name": body.first_name,
            "last_name": body.last_name,
            "display_name": body.display_name.strip() or "",  # nickname only
            "phone": body.phone,
            "language": body.language,
            "emergency_contact": body.emergency_contact,
            "photo_url": body.photo_url,
            "comm_preference": body.comm_preference,
            "worker_roles": body.worker_roles
        }
        
        update_data = {"metadata": meta}
        if body.email and not row.get("email"):
            update_data["email"] = body.email
            
        db.table("access_tokens").update(update_data).eq("id", row["id"]).execute()
        
        return JSONResponse(status_code=200, content={"status": "submitted_for_review"})
    except Exception as exc:
        logger.exception("Failed to submit onboarding: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get(
    "/admin/staff-onboarding",
    tags=["admin"],
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_pending_onboarding(tenant_id: str = Depends(jwt_auth)) -> JSONResponse:
    db = _get_db()
    try:
        # Phase 857 (audit C3): only query STAFF_ONBOARD tokens.
        # Legacy invite tokens are Pipeline A — they never appear in this queue.
        res = (
            db.table("access_tokens")
            .select("id, email, created_at, metadata")
            .eq("entity_id", tenant_id)
            .eq("token_type", "staff_onboard")
            .is_("used_at", "null")
            .is_("revoked_at", "null")
            .execute()
        )
        rows = res.data or []
        pending = [r for r in rows if r.get("metadata", {}).get("status") == "pending_confirm"]
        
        return JSONResponse(status_code=200, content={"requests": pending})
    except Exception as exc:
        logger.exception("Failed to fetch pending onboarding: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


class ApproveOnboardingRequest(BaseModel):
    role: str = "worker"
    worker_roles: list[str] = Field(default_factory=list)  # empty = use submitted roles from form
    frontend_url: Optional[str] = Field(None, description="Frontend origin URL for auth redirect")


def _extract_action_link(link_res: Any) -> str:
    """Robustly extract action_link from any shape of Supabase generate_link response."""
    candidates = [
        link_res,
        getattr(link_res, "user", None),
        getattr(link_res, "properties", None),
        getattr(link_res, "data", None),
    ]
    for obj in candidates:
        if obj is None:
            continue
        if isinstance(obj, dict) and obj.get("action_link"):
            return obj["action_link"]
        if hasattr(obj, "action_link") and getattr(obj, "action_link"):
            return getattr(obj, "action_link")
        # try nested .properties
        props = getattr(obj, "properties", None)
        if props:
            if isinstance(props, dict) and props.get("action_link"):
                return props["action_link"]
            if hasattr(props, "action_link") and getattr(props, "action_link"):
                return getattr(props, "action_link")
    return ""

from fastapi import Request


def _resolve_frontend_url(body_url: Optional[str], origin_header: Optional[str]) -> str:
    """
    Phase 947f: Canonical frontend URL resolver for invite / link generation.
    
    Priority:
    1. IHOUSE_FRONTEND_URL env var (authoritative — set per environment on Railway)
    2. body.frontend_url from the admin browser (window.location.origin)
    3. Origin header from the request
    4. NEXT_PUBLIC_APP_URL env var
    5. Explicit error — never silently fall back to localhost in a staging/prod env.
    
    The historic fallback to hard-coded 'http://localhost:3000' was the root cause
    of the malformed Site URL in invite emails.
    """
    env_canonical = (
        os.environ.get("IHOUSE_FRONTEND_URL") or          # Railway: set this per env
        os.environ.get("NEXT_PUBLIC_APP_URL")              # Legacy alias
    )
    candidates = [
        env_canonical,
        body_url,
        origin_header,
    ]
    for candidate in candidates:
        url = (candidate or "").strip().rstrip("/")
        if url and url.startswith("http"):
            return url
    # If running in a non-production environment (e.g., local Docker), allow localhost
    env = os.environ.get("IHOUSE_ENV", "development")
    if env in ("development", "local"):
        return "http://localhost:3000"
    # Staging/production: never inject localhost — raise so the caller knows
    raise ValueError(
        "Cannot resolve frontend URL for invite email generation. "
        "Set IHOUSE_FRONTEND_URL (e.g. https://domaniqo-staging.vercel.app) "
        "in the Railway environment config."
    )


@router.post(
    "/admin/staff-onboarding/{request_id}/approve",
    tags=["admin"],
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def approve_onboarding(
    request_id: str,
    body: ApproveOnboardingRequest,
    req: Request,
    tenant_id: str = Depends(jwt_auth)
) -> JSONResponse:
    db = _get_db()
    res = db.table("access_tokens").select("*").eq("id", request_id).eq("entity_id", tenant_id).limit(1).execute()
    data = res.data or []
    if not data:
        return make_error_response(status_code=404, code="NOT_FOUND")
        
    row = data[0]
    meta = row.get("metadata") or {}
    if meta.get("status") != "pending_confirm":
        return make_error_response(status_code=400, code="INVALID_STATUS", extra={"detail": "Can only approve pending requests."})
        
    wdata = meta.get("worker_data", {})
        
    try:
        from supabase import create_client
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        admin_client = create_client(url, key)
        
        # 1. Invite the user so they can set their password
        email = row.get("email") or wdata.get("email")
        if not email:
            return make_error_response(status_code=400, code="VALIDATION_ERROR", extra={"detail": "Missing email for invited user. Worker must provide an email."})

        try:
            resolved_front = _resolve_frontend_url(body.frontend_url, req.headers.get("origin"))
            frontend_url = resolved_front
            user_id: Optional[str] = None
            delivery_method = "unknown"
            action_link = ""

            # Step 1: Try invite (creates user + sends branded email for new users)
            try:
                auth_res = admin_client.auth.admin.invite_user_by_email(
                    email,
                    options={
                        "data": {
                            "full_name": wdata.get("full_name", ""),
                            "force_reset": True,
                        },
                        "redirect_to": f"{frontend_url}/auth/callback"
                    }
                )
                user_id = auth_res.user.id
                delivery_method = "email_invite_sent"
                logger.info("staff-onboarding/approve: invite sent to %s (new user)", email)
            except Exception as invite_exc:
                if "already" in str(invite_exc).lower() or "exists" in str(invite_exc).lower():
                    logger.info("staff-onboarding/approve: user %s already exists — generating magic link", email)
                    delivery_method = "existing_user_magic_link"
                else:
                    raise invite_exc

            # Step 2: Always generate a magic link regardless (fallback + always return to admin)
            try:
                link_res = admin_client.auth.admin.generate_link(
                    {"type": "magiclink", "email": email,
                     "options": {"redirect_to": f"{frontend_url}/auth/callback"}}
                )
                if user_id is None:
                    user_id = link_res.user.id
                action_link = _extract_action_link(link_res)
                if delivery_method == "existing_user_magic_link" and not action_link:
                    delivery_method = "magic_link_generation_failed"
            except Exception as link_exc:
                logger.warning("staff-onboarding/approve: generate_link failed for %s: %s", email, link_exc)
                if user_id is None:
                    raise link_exc

            # Step 3: Always set force_reset on the user metadata
            if user_id:
                try:
                    resolved_user = admin_client.auth.admin.get_user_by_id(user_id).user
                    existing_meta = resolved_user.user_metadata or {}
                    existing_meta["force_reset"] = True
                    admin_client.auth.admin.update_user_by_id(user_id, {"user_metadata": existing_meta})

                    # ── Phase 947: Write-path identity guard ──────────────────
                    # Verify the Supabase auth account we just resolved has the SAME
                    # email as the onboarding form. This prevents the exact class of
                    # mismatch where user_id points to a different person's auth record.
                    resolved_auth_email = (getattr(resolved_user, "email", None) or "").lower().strip()
                    onboarding_email = email.lower().strip()
                    if resolved_auth_email and resolved_auth_email != onboarding_email:
                        logger.critical(
                            "Phase 947 IDENTITY_MISMATCH_AT_APPROVAL blocked provisioning: "
                            "user_id=%s resolved_auth_email=%s onboarding_email=%s tenant=%s",
                            user_id, resolved_auth_email, onboarding_email, tenant_id,
                        )
                        return make_error_response(
                            status_code=409,
                            code="IDENTITY_MISMATCH_AT_APPROVAL",
                            extra={
                                "detail": (
                                    f"Identity mismatch detected at approval time. "
                                    f"The Supabase auth account for user_id={user_id} has email "
                                    f"'{resolved_auth_email}', but the onboarding form was submitted "
                                    f"for '{onboarding_email}'. Provisioning blocked to prevent "
                                    f"a broken worker identity linkage."
                                ),
                                "user_id": user_id,
                                "auth_email": resolved_auth_email,
                                "onboarding_email": onboarding_email,
                            },
                        )
                    # ── End write-path identity guard ────────────────────────
                except Exception as meta_exc:
                    logger.warning("staff-onboarding/approve: could not set force_reset for %s: %s", user_id, meta_exc)

        except Exception as e:
            if "rate limit" in str(e).lower():
                return make_error_response(
                    status_code=429,
                    code="RATE_LIMIT",
                    extra={"detail": f"Supabase email rate limit exceeded for {email}. Please wait ~60 minutes or use a different email for testing."}
                )
            raise e
        
        # 2. Provision permissions with all the rich data
        # Phase 1026 Fix — Role integrity: intended_role is the source of truth.
        # Priority: body.role (explicit admin override) > meta.intended_role > fallback 'worker'
        role = body.role or meta.get("intended_role", "worker")
        wroles = list(body.worker_roles or wdata.get("worker_roles", []) or [])

        # Phase 1026 Fix H2 — Normalize combined checkin/checkout string.
        # The invite UI may store "checkin/checkout" as a single preselected_roles value.
        # Expand it to the canonical two-element form that the JWT builder and staff card require.
        if "checkin/checkout" in wroles:
            wroles = [r for r in wroles if r != "checkin/checkout"]
            if "checkin" not in wroles:
                wroles.append("checkin")
            if "checkout" not in wroles:
                wroles.append("checkout")

        # Phase 1026 Fix H3 — Manager role integrity.
        # If intended_role is 'manager', the person is NOT a worker.
        # Write role='manager', worker_roles=[], worker_role=None.
        # Do NOT inherit worker sub-roles from the form (op_manager, etc.) — those are erroneous.
        if role == "manager":
            wroles = []

        # Phase 1026 Fix H1 — Write worker_role (singular) for worker types.
        # For combined checkin+checkout, canonical primary is 'checkin' (first alphabetically
        # and 'checkin_checkout' is detected by auth_login_router from the pair, not this field).
        # For manager, worker_role is None by design.
        if role == "worker" and wroles:
            resolved_worker_role: Optional[str] = wroles[0]
        else:
            resolved_worker_role = None

        # Extract PII/compliance fields from comm_preference into dedicated columns
        comm_pref = dict(wdata.get("comm_preference") or {})
        date_of_birth = comm_pref.pop("date_of_birth", None)
        id_photo_url = comm_pref.pop("id_photo_url", None)
        id_number = comm_pref.pop("id_number", None)
        id_expiry_date = comm_pref.pop("id_expiry_date", None)
        work_permit_photo_url = comm_pref.pop("work_permit_photo_url", None)
        work_permit_number = comm_pref.pop("work_permit_number", None)
        work_permit_expiry_date = comm_pref.pop("work_permit_expiry_date", None)
        preferred_channel = comm_pref.pop("preferred_channel", None)
        preferred_name = comm_pref.pop("preferred_name", None)  # nickname
        # Keep telegram/line/whatsapp/email in comm_pref, store preferred_name back cleaned
        if preferred_name:
            comm_pref["preferred_name"] = preferred_name
        if preferred_channel:
            comm_pref["preferred_channel"] = preferred_channel

        # Phase 1025 Fix B (corrected): Derive document status from submitted data.
        # NEVER hardcode 'missing' — that silently overwrites real submitted data.
        # Use 'submitted' (not 'valid') — the canonical UI status enum is:
        #   missing | submitted | verified | expiring_soon | expired
        # A newly approved worker has SUBMITTED documents; an admin can upgrade to
        # 'verified' after manual review. 'valid' is not in the UI enum.
        id_doc_status = "submitted" if id_number else "missing"
        work_permit_status = "submitted" if work_permit_number else "missing"
        # Write the derived statuses into comm_pref so the Documents tab reads them
        comm_pref["id_doc_status"] = id_doc_status
        comm_pref["work_permit_status"] = work_permit_status
        logger.info(
            "staff-onboarding/approve: doc status derived id_doc=%s work_permit=%s user_id=%s",
            id_doc_status, work_permit_status, user_id,
        )

        # Primary name for the staff card = real full name, not nickname
        full_name = wdata.get("full_name") or (
            f"{wdata.get('first_name', '')} {wdata.get('last_name', '')}".strip()
        )

        perm_row = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": role,
            "worker_roles": wroles,
            "worker_role": resolved_worker_role,   # Phase 1026 Fix H1: singular primary sub-role
            "is_active": True,
            "display_name": full_name,          # primary: real full name
            "phone": wdata.get("phone", ""),
            "language": wdata.get("language", "en"),
            "photo_url": wdata.get("photo_url", ""),
            "emergency_contact": wdata.get("emergency_contact", ""),
            "address": "",
            "comm_preference": comm_pref,
            "created_at": "now()",
            "updated_at": "now()"
        }
        logger.info(
            "staff-onboarding/approve: role=%s worker_roles=%s worker_role=%s user_id=%s",
            role, wroles, resolved_worker_role, user_id,
        )
        # Phase 857 (audit C8): add dedicated PII columns if migration has been applied
        if date_of_birth:
            perm_row["date_of_birth"] = date_of_birth
        if id_photo_url:
            perm_row["id_photo_url"] = id_photo_url
        if id_number:
            perm_row["id_number"] = id_number
        if id_expiry_date:
            perm_row["id_expiry_date"] = id_expiry_date
        if work_permit_photo_url:
            perm_row["work_permit_photo_url"] = work_permit_photo_url
        if work_permit_number:
            perm_row["work_permit_number"] = work_permit_number
        if work_permit_expiry_date:
            perm_row["work_permit_expiry_date"] = work_permit_expiry_date

        # Phase 1025 Fix D (partial atomicity): permissions upsert runs before token mark.
        # If this write fails, the token remains in pending_confirm so admin can retry.
        # If auth provisioning succeeded but this fails, log PARTIAL_APPROVAL_FAILURE.
        try:
            admin_client.table("tenant_permissions").upsert(
                perm_row, on_conflict="tenant_id,user_id"
            ).execute()
        except Exception as perm_exc:
            logger.critical(
                "PARTIAL_APPROVAL_FAILURE: auth user provisioned but permissions upsert failed. "
                "user_id=%s tenant=%s email=%s error=%s — manual cleanup may be required.",
                user_id, tenant_id, email, perm_exc,
            )
            raise perm_exc
        
        # 3. Mark token as used
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        meta["status"] = "approved"
        db.table("access_tokens").update({"used_at": now, "metadata": meta}).eq("id", request_id).execute()
        
        return JSONResponse(status_code=200, content={
            "status": "approved",
            "user_id": user_id,
            "delivery_method": delivery_method,
            "email": email,
            # Always include magic_link — admin UI can surface it as a copy-able fallback
            "magic_link": action_link,
        })
    except Exception as exc:
        logger.exception("Failed to approve onboarding: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.post(
    "/admin/staff-onboarding/{request_id}/reject",
    tags=["admin"],
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def reject_onboarding(request_id: str, tenant_id: str = Depends(jwt_auth)) -> JSONResponse:
    db = _get_db()
    res = db.table("access_tokens").select("id, metadata").eq("id", request_id).eq("entity_id", tenant_id).execute()
    if not res.data:
         return make_error_response(status_code=404, code="NOT_FOUND")
         
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    meta = res.data[0].get("metadata") or {}
    meta["status"] = "rejected"
         
    db.table("access_tokens").update({"metadata": meta, "revoked_at": now}).eq("id", request_id).execute()
    return JSONResponse(status_code=200, content={"status": "rejected"})


class ResendAccessRequest(BaseModel):
    channel: str = Field("email", description="Delivery channel: email, whatsapp, sms, telegram, line")
    frontend_url: Optional[str] = Field(None, description="Frontend origin URL for auth redirect")


@router.post(
    "/admin/staff/{user_id}/resend-access",
    tags=["admin"],
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def resend_access(
    user_id: str,
    body: ResendAccessRequest,
    req: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """Resend/send first-access link for an approved staff member."""
    db = _get_db()

    # Look up the staff member
    res = db.table("tenant_permissions").select("*").eq("tenant_id", tenant_id).eq("user_id", user_id).limit(1).execute()
    if not res.data:
        return make_error_response(status_code=404, code="NOT_FOUND", extra={"detail": "Staff member not found."})

    perm = res.data[0]
    comm = perm.get("comm_preference") or {}

    # For email delivery, use Supabase's built-in invite/magic-link mechanism
    if body.channel == "email":
        # Resolve email from Supabase Auth user
        from supabase import create_client
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        admin_client = create_client(url, key)

        try:
            user = admin_client.auth.admin.get_user_by_id(user_id)
            email = user.user.email
            if not email:
                return make_error_response(status_code=400, code="NO_EMAIL", extra={"detail": "User has no email on file."})

            # ── Phase 947: Identity Preflight Check ──────────────────────────
            # Guard: the auth account's email MUST match the worker's comm_preference email.
            # If they diverge, the access link will be bound to the wrong identity.
            # Block generation immediately with an explicit, admin-facing error.
            comm_email = (comm.get("email") or "").lower().strip()
            auth_email = email.lower().strip()
            if comm_email and auth_email != comm_email:
                logger.error(
                    "Phase 947 IDENTITY_MISMATCH blocked access link: user_id=%s "
                    "auth_email=%s comm_email=%s tenant=%s",
                    user_id, auth_email, comm_email, tenant_id,
                )
                return make_error_response(
                    status_code=409,
                    code="IDENTITY_MISMATCH",
                    extra={
                        "detail": (
                            f"Identity mismatch: the linked auth account ({auth_email}) does not match "
                            f"the worker's communication email ({comm_email}). "
                            "The worker identity must be repaired before an access link can be generated."
                        ),
                        "auth_email": auth_email,
                        "comm_email": comm_email,
                        "user_id": user_id,
                    },
                )
            # ── End Identity Preflight ───────────────────────────────────────

            resolved_front = _resolve_frontend_url(body.frontend_url, req.headers.get("origin"))
            frontend_url = resolved_front
            try:
                auth_res = admin_client.auth.admin.invite_user_by_email(
                    email,
                    options={
                        "data": {
                            "full_name": perm.get("display_name", ""),
                            "force_reset": True,
                        },
                        "redirect_to": f"{frontend_url}/auth/callback"
                    }
                )
                delivery_method = "email_invite"
                action_link = _extract_action_link(auth_res)
            except Exception as inv_exc:
                if "already" in str(inv_exc).lower() or "exists" in str(inv_exc).lower():
                    link_res = admin_client.auth.admin.generate_link(
                        {"type": "magiclink", "email": email,
                         "options": {"redirect_to": f"{frontend_url}/auth/callback"}}
                    )
                    delivery_method = "magic_link_resent"
                    action_link = _extract_action_link(link_res)
                else:
                    raise inv_exc

            # Ensure force_reset is set
            import time
            existing_meta = user.user.user_metadata or {}
            existing_meta["force_reset"] = True
            existing_meta["access_link_sent_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            existing_meta.pop("access_link_opened_at", None)
            
            admin_client.auth.admin.update_user_by_id(user_id, {
                "user_metadata": existing_meta
            })

            return JSONResponse(status_code=200, content={
                "status": "sent",
                "channel": "email",
                "email": email,
                "delivery_method": delivery_method,
                "magic_link": action_link,
            })
        except Exception as exc:
            logger.exception("Failed to resend access via email: %s", exc)
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
    else:
        # For non-email channels, generate a magic link and return it for admin to send manually
        from supabase import create_client
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        admin_client = create_client(url, key)

        try:
            user = admin_client.auth.admin.get_user_by_id(user_id)
            email = user.user.email
            if not email:
                return make_error_response(status_code=400, code="NO_EMAIL", extra={"detail": "User has no email on file."})

            resolved_front = _resolve_frontend_url(body.frontend_url, req.headers.get("origin"))
            frontend_url = resolved_front
            link_res = admin_client.auth.admin.generate_link(
                {"type": "magiclink", "email": email,
                 "options": {"redirect_to": f"{frontend_url}/auth/callback"}}
            )

            # Ensure force_reset
            import time
            existing_meta = user.user.user_metadata or {}
            existing_meta["force_reset"] = True
            existing_meta["access_link_sent_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            existing_meta.pop("access_link_opened_at", None)
            
            admin_client.auth.admin.update_user_by_id(user_id, {
                "user_metadata": existing_meta
            })

            # Construct the link using the shared robust extractor
            action_link = _extract_action_link(link_res)

            return JSONResponse(status_code=200, content={
                "status": "link_generated",
                "channel": body.channel,
                "email": email,
                "delivery_method": "manual_copy",
                "magic_link": action_link,
                "message": f"Copy this link and send it to the worker via {body.channel}.",
            })
        except Exception as exc:
            logger.exception("Failed to generate resend link: %s", exc)
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get(
    "/admin/staff/{user_id}/status",
    tags=["admin"],
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_staff_status(
    user_id: str,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """Fetch real-time activation status from Supabase Auth and DB."""
    db = _get_db()
    
    # 1. Verify existence in tenant
    res = db.table("tenant_permissions").select("user_id").eq("tenant_id", tenant_id).eq("user_id", user_id).limit(1).execute()
    if not res.data:
        return make_error_response(status_code=404, code="NOT_FOUND", extra={"detail": "Staff member not found."})
        
    try:
        from supabase import create_client
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        admin_client = create_client(url, key)
        
        try:
            user = admin_client.auth.admin.get_user_by_id(user_id)
        except Exception:
            return JSONResponse(status_code=200, content={
                "user_id": user_id,
                "force_reset": None,
                "last_sign_in_at": None,
                "invited_at": None,
                "access_link_sent_at": None,
                "access_link_opened_at": None
            })
            
        u = user.user
        
        meta = u.user_metadata or {}
        force_reset = meta.get("force_reset", False)
        auth_email = getattr(u, "email", None)

        # ── Datetime serialization: Supabase SDK returns datetime objects, ──
        # ── not strings. JSONResponse cannot serialize datetime, so we must ──
        # ── convert explicitly. This was the root cause of the silent 500.  ──
        def _to_str(val):
            """Convert a datetime (or any) to ISO string, or return as-is if already str/None."""
            if val is None:
                return None
            if hasattr(val, "isoformat"):
                return val.isoformat()
            return str(val)

        last_sign_in = _to_str(getattr(u, "last_sign_in_at", None))
        invited_at   = _to_str(getattr(u, "updated_at", None))  # approximate

        # Phase 947: Fetch comm_preference email from tenant_permissions for identity chain
        perm_res = db.table("tenant_permissions").select("comm_preference").eq("tenant_id", tenant_id).eq("user_id", user_id).limit(1).execute()
        comm_email = None
        identity_mismatch = False
        if perm_res.data:
            comm = perm_res.data[0].get("comm_preference") or {}
            comm_email = comm.get("email")
            if comm_email and auth_email:
                identity_mismatch = comm_email.lower().strip() != auth_email.lower().strip()
        
        return JSONResponse(status_code=200, content={
            "user_id": user_id,
            "force_reset": force_reset,
            "last_sign_in_at": last_sign_in,
            "invited_at": invited_at,
            "access_link_sent_at": meta.get("access_link_sent_at"),
            "access_link_opened_at": meta.get("access_link_opened_at"),
            # Phase 947: Identity chain — auth_email, comm_email, and mismatch flag
            "auth_email": auth_email,
            "comm_email": comm_email,
            "identity_mismatch": identity_mismatch,
        })
    except Exception as exc:
        logger.exception("Failed to fetch staff status for %s: %s", user_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ── Phase 947d: Identity Repair Endpoint ─────────────────────────────────────

class RepairEmailRequest(BaseModel):
    confirmed: bool = Field(False, description="Must be True to execute the repair. Acts as a safety check.")


@router.post(
    "/admin/staff/{user_id}/repair-email",
    tags=["admin"],
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def repair_worker_email(
    user_id: str,
    body: RepairEmailRequest,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 947d: Repair an auth email typo for a worker.

    Safe for: cases where auth_email ≠ comm_preference.email but the user_id
    linkage is correct (same person, wrong email in auth.users).

    NOT safe for: Tiki Toto-type cases where user_id points to a different person.
    The endpoint classifies the mismatch before acting and rejects deep mismatches.

    On success: updates auth.users email + writes to identity_repair_log.
    """
    if not body.confirmed:
        return make_error_response(
            status_code=400,
            code="CONFIRMATION_REQUIRED",
            extra={"detail": "Set confirmed=true to execute the repair."},
        )

    db = _get_db()

    # 1. Load the worker from tenant_permissions
    perm_res = db.table("tenant_permissions").select("comm_preference, display_name").eq("tenant_id", tenant_id).eq("user_id", user_id).limit(1).execute()
    if not perm_res.data:
        return make_error_response(status_code=404, code="NOT_FOUND", extra={"detail": "Staff member not found."})

    comm = perm_res.data[0].get("comm_preference") or {}
    comm_email = (comm.get("email") or "").strip()
    if not comm_email:
        return make_error_response(status_code=400, code="NO_COMM_EMAIL", extra={"detail": "Worker has no comm_preference.email to repair to."})

    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    try:
        admin_client = create_client(url, key)
        user = admin_client.auth.admin.get_user_by_id(user_id).user
        auth_email = (getattr(user, "email", None) or "").strip()

        if not auth_email:
            return make_error_response(status_code=400, code="NO_AUTH_EMAIL", extra={"detail": "Auth account has no email to repair from."})

        if auth_email.lower() == comm_email.lower():
            return JSONResponse(status_code=200, content={
                "status": "already_correct",
                "message": "Auth email already matches comm_preference email. No repair needed.",
                "auth_email": auth_email,
                "comm_email": comm_email,
            })

        # ── Safety classification: is this an email-typo case or a deep (wrong-person) mismatch? ──
        # Policy:
        #   - edit_distance(auth_local, comm_local) == 0  → identical, trivial (domain-only fix)
        #   - edit_distance <= 3                          → small typo, admin-initiated correction → ALLOW
        #   - edit_distance >  3                          → likely different people → BLOCK as deep mismatch
        # This lets an admin fix 'jonh@gmail.com' → 'john@gmail.com' while still blocking
        # Tiki-Toto-class linkages where the auth account genuinely belongs to another person.
        def _levenshtein(a: str, b: str) -> int:
            """Classic DP Levenshtein distance."""
            if a == b:
                return 0
            if not a:
                return len(b)
            if not b:
                return len(a)
            prev = list(range(len(b) + 1))
            for i, ca in enumerate(a):
                curr = [i + 1]
                for j, cb in enumerate(b):
                    curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if ca == cb else 1)))
                prev = curr
            return prev[-1]

        auth_local  = auth_email.split("@")[0].lower().strip()
        comm_local  = comm_email.split("@")[0].lower().strip()
        auth_domain = auth_email.split("@")[-1].lower().strip() if "@" in auth_email else ""
        comm_domain = comm_email.split("@")[-1].lower().strip() if "@" in comm_email else ""

        edit_dist = _levenshtein(auth_local, comm_local)
        is_deep_mismatch = edit_dist > 3  # different people threshold

        if is_deep_mismatch:
            logger.error(
                "Phase 947d: repair-email BLOCKED — deep mismatch (edit_dist=%d): user_id=%s "
                "auth_email=%s comm_email=%s tenant=%s",
                edit_dist, user_id, auth_email, comm_email, tenant_id,
            )
            return make_error_response(
                status_code=409,
                code="DEEP_IDENTITY_MISMATCH",
                extra={
                    "detail": (
                        f"This mismatch cannot be automatically repaired. "
                        f"The auth account email '{auth_email}' appears to belong to a different person "
                        f"than the comm email '{comm_email}' (name edit distance: {edit_dist}). "
                        "If you are certain this is the same person, contact your system administrator "
                        "to manually update the auth account."
                    ),
                    "auth_email": auth_email,
                    "comm_email": comm_email,
                    "edit_distance": edit_dist,
                    "mismatch_class": "deep_mismatch",
                },
            )

        mismatch_class = "email_typo" if auth_local == comm_local else "username_typo"
        if auth_domain == comm_domain:
            mismatch_class = "case_or_whitespace"

        # ── Perform the repair ──
        import time
        admin_client.auth.admin.update_user_by_id(user_id, {"email": comm_email})

        # ── Write to audit log ──
        try:
            db.table("identity_repair_log").insert({
                "tenant_id": tenant_id,
                "user_id_from": user_id,
                "user_id_to": user_id,        # same user_id — this is an email-only repair
                "auth_email_from": auth_email,
                "auth_email_to": comm_email,
                "repaired_by": tenant_id,     # admin's tenant JWT identity
                "repair_method": "api/repair-email",
                "notes": f"Email typo repair: '{auth_email}' → '{comm_email}' (class: {mismatch_class})",
            }).execute()
        except Exception as log_exc:
            logger.warning("Phase 947d: could not write identity_repair_log: %s", log_exc)

        logger.info(
            "Phase 947d: email repair applied: user_id=%s %s -> %s (class: %s)",
            user_id, auth_email, comm_email, mismatch_class,
        )

        return JSONResponse(status_code=200, content={
            "status": "repaired",
            "user_id": user_id,
            "auth_email_before": auth_email,
            "auth_email_after": comm_email,
            "mismatch_class": mismatch_class,
            "message": f"Auth email updated from '{auth_email}' to '{comm_email}'. Identity mismatch is resolved.",
        })

    except Exception as exc:
        logger.exception("Phase 947d: repair-email failed for user_id=%s: %s", user_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
