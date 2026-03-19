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
    
    # We define a custom string for token_type, or re-use INVITE. 
    # For separation, we use "staff_onboard" literal string, even if TokenType enum doesn't strictly have it,
    # but verify_access_token checks against the enum or string.
    try:
        # We will use "staff_onboard" as token type. 
        # issue_access_token usually takes an Enum but we can pass string if we bypass type checks or we just use a string.
        # Let's just use the string literal 'staff_onboard'
        import time
        import jwt
        secret = os.environ.get("IHOUSE_ACCESS_TOKEN_SECRET", "dev-secret")
        now = int(time.time())
        exp = now + (7 * 86400)
        claims = {
            "iss": "ihouse-core",
            "aud": "ihouse-tenant",
            "typ": "invite",
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
            token_type=TokenType.INVITE,
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
        if claims.get("typ") != "invite":
            return JSONResponse(status_code=401, content={"valid": False, "error": "INVALID_TYPE"})
    except Exception:
        return JSONResponse(status_code=401, content={"valid": False, "error": "INVALID_TOKEN"})

    h = _hash_token(token)
    res = db.table("access_tokens").select("id, metadata, used_at, revoked_at").eq("token_hash", h).limit(1).execute()
    data = res.data or []
    if not data:
        return JSONResponse(status_code=404, content={"valid": False, "error": "NOT_FOUND"})
    
    row = data[0]
    if row.get("used_at") or row.get("revoked_at"):
        return JSONResponse(status_code=400, content={"valid": False, "error": "ALREADY_USED_OR_REVOKED"})
        
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
        db.storage.from_("property-photos").upload(
            path=full_path, file=full_data,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )
        full_url = _get_storage_public_url(full_path)
        return JSONResponse(status_code=200, content={"url": full_url})
    except Exception as exc:
        logger.exception("Onboarding photo upload error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR, extra={"detail": str(exc)})


class OnboardingSubmitRequest(BaseModel):
    email: Optional[str] = None
    full_name: str
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
        
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        
        # update metadata
        meta["status"] = "pending_confirm"
        meta["submitted_at"] = now
        meta["worker_data"] = {
            "email": body.email,
            "full_name": body.full_name,
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
        res = db.table("access_tokens").select("id, email, created_at, metadata").eq("entity_id", tenant_id).eq("token_type", "invite").is_("used_at", "null").is_("revoked_at", "null").execute()
        rows = res.data or []
        pending = [r for r in rows if r.get("metadata", {}).get("status") == "pending_confirm"]
        
        return JSONResponse(status_code=200, content={"requests": pending})
    except Exception as exc:
        logger.exception("Failed to fetch pending onboarding: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


class ApproveOnboardingRequest(BaseModel):
    role: str = "worker"
    worker_roles: list[str] = ["CLEANER"]

@router.post(
    "/admin/staff-onboarding/{request_id}/approve",
    tags=["admin"],
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def approve_onboarding(
    request_id: str,
    body: ApproveOnboardingRequest,
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
            # Generate a magic link. This creates the user if they don't exist.
            frontend_url = os.environ.get("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
            auth_res = admin_client.auth.admin.generate_link(
                {"type": "magiclink", "email": email, "data": {"full_name": wdata.get("full_name", ""), "phone": wdata.get("phone", "")},
                 "options": {"redirect_to": f"{frontend_url}/auth/callback"}}
            )
            user_id = auth_res.user.id
            magic_link = auth_res.properties.action_link
            
            # If the user was just created, force them to set a password on next login
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            is_new = (now - auth_res.user.created_at).total_seconds() < 60
            if is_new:
                existing_meta = auth_res.user.user_metadata or {}
                existing_meta["force_reset"] = True
                admin_client.auth.admin.update_user_by_id(user_id, {
                    "user_metadata": existing_meta
                })
            
        except Exception as e:
            if "rate limit" in str(e).lower():
                return make_error_response(
                    status_code=429, 
                    code="RATE_LIMIT", 
                    extra={"detail": f"Supabase email rate limit exceeded for {email}. Please wait ~60 minutes or use a different email for testing."}
                )
            raise e
        
        # 2. Provision permissions with all the rich data
        role = body.role or meta.get("intended_role", "worker")
        wroles = body.worker_roles or wdata.get("worker_roles", [])
        
        admin_client.table("tenant_permissions").upsert({
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": role,
            "worker_roles": wroles,
            "is_active": True,
            "display_name": wdata.get("full_name", ""),
            "phone": wdata.get("phone", ""),
            "language": wdata.get("language", "en"),
            "photo_url": wdata.get("photo_url", ""),
            "emergency_contact": wdata.get("emergency_contact", ""),
            "address": "",
            "comm_preference": wdata.get("comm_preference", {}),
            "created_at": "now()",
            "updated_at": "now()"
        }, on_conflict="tenant_id,user_id").execute()
        
        # 3. Mark token as used
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        meta["status"] = "approved"
        db.table("access_tokens").update({"used_at": now, "metadata": meta}).eq("id", request_id).execute()
        
        return JSONResponse(status_code=200, content={"status": "approved", "user_id": user_id, "magic_link": locals().get("magic_link")})
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
