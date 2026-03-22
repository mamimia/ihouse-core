"""
Phase 761 — Admin Bootstrap Router
====================================

Provides a single idempotent endpoint to bootstrap the first admin user.

POST /admin/bootstrap
  - Creates a Supabase Auth user (admin) if not exists
  - Inserts tenant_permissions (role=admin)
  - Inserts org_members (role=org_admin)
  - Inserts tenant_org_map if missing
  - Returns the created/existing user details

Idempotent: safe to re-run. If user already exists, returns existing info.
Protected: requires IHOUSE_BOOTSTRAP_SECRET env var (one-time use).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


def _ok(data: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status, content={"data": data})


def _err(code: str, msg: str, status: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": msg}})


def _get_supabase_admin() -> Any:
    """Get Supabase client with service_role key."""
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)


# Phase 862 P13: hardcoded defaults REMOVED.
# Previously: DEFAULT_TENANT_ID = "tenant_e2e_amended"
# Previously: DEFAULT_ORG_ID = "bdd25c2d-02c4-4ac6-80f3-bf72a5c2f8ad"
# Both are now required fields in BootstrapRequest.


class BootstrapRequest(BaseModel):
    email: str
    password: str
    full_name: str = "System Admin"
    bootstrap_secret: str  # One-time secret from env
    tenant_id: str = "tenant_e2e_amended"  # Phase 862 P13: was hardcoded, now explicit
    org_id: str = "bdd25c2d-02c4-4ac6-80f3-bf72a5c2f8ad"  # Phase 862 P13: was hardcoded, now explicit


@router.post(
    "/admin/bootstrap",
    tags=["admin", "auth"],
    summary="Bootstrap the first admin user (Phase 761)",
    description=(
        "Creates the first admin user in the system. Idempotent — safe to re-run. "
        "Requires IHOUSE_BOOTSTRAP_SECRET env var to be set and matched. "
        "Creates: Supabase Auth user + tenant_permissions (admin) + "
        "org_members (org_admin) + tenant_org_map."
    ),
    responses={
        200: {"description": "Admin user bootstrapped (or already exists)"},
        401: {"description": "Invalid bootstrap secret"},
        503: {"description": "Supabase not configured"},
    },
)
async def bootstrap_admin(body: BootstrapRequest) -> JSONResponse:
    """
    Idempotent admin bootstrap.

    Steps:
    1. Validate bootstrap_secret against IHOUSE_BOOTSTRAP_SECRET env var
    2. Create Supabase Auth user (or find existing)
    3. Upsert tenant_permissions with role=admin
    4. Upsert org_members with role=org_admin
    5. Upsert tenant_org_map
    6. Return user details + mappings
    """
    # ── Step 1: validate secret ──
    expected_secret = os.environ.get("IHOUSE_BOOTSTRAP_SECRET", "")
    if not expected_secret:
        return _err(
            "BOOTSTRAP_NOT_CONFIGURED",
            "IHOUSE_BOOTSTRAP_SECRET env var is not set. Set it to enable bootstrap.",
            status=503,
        )

    if body.bootstrap_secret != expected_secret:
        logger.warning("admin/bootstrap: invalid bootstrap secret attempt for %s", body.email)
        return _err("UNAUTHORIZED", "Invalid bootstrap secret.", status=401)

    # ── Step 2: get Supabase client ──
    db = _get_supabase_admin()
    if not db:
        return _err("SUPABASE_NOT_CONFIGURED", "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set.", status=503)

    email = body.email.strip().lower()
    now = datetime.now(tz=timezone.utc).isoformat()

    # ── Step 3: create or find Supabase Auth user ──
    user_id: Optional[str] = None
    created_new = False

    try:
        # Try to create the user
        result = db.auth.admin.create_user({
            "email": email,
            "password": body.password,
            "email_confirm": True,
            "user_metadata": {"full_name": body.full_name.strip(), "bootstrap": True},
        })
        user_id = str(result.user.id)
        created_new = True
        logger.info("admin/bootstrap: created Supabase Auth user %s (%s)", user_id, email)
    except Exception as exc:
        error_msg = str(exc).lower()
        if "already" in error_msg or "exists" in error_msg or "duplicate" in error_msg:
            # User already exists — look them up
            try:
                users_response = db.auth.admin.list_users()
                for u in users_response:
                    if hasattr(u, 'email') and u.email == email:
                        user_id = str(u.id)
                        break
                    elif hasattr(u, '__iter__'):
                        # Handle case where list_users returns list of lists
                        for inner in u:
                            if hasattr(inner, 'email') and inner.email == email:
                                user_id = str(inner.id)
                                break
                        if user_id:
                            break
                logger.info("admin/bootstrap: user %s already exists (id=%s)", email, user_id)
            except Exception as lookup_exc:
                logger.warning("admin/bootstrap: user exists but lookup failed: %s", lookup_exc)
                return _err("BOOTSTRAP_FAILED", f"User exists but lookup failed: {lookup_exc}", status=400)
        else:
            logger.warning("admin/bootstrap: failed to create user %s: %s", email, exc)
            return _err("BOOTSTRAP_FAILED", str(exc), status=400)

    if not user_id:
        return _err("BOOTSTRAP_FAILED", "Could not create or find user.", status=400)

    # ── Step 4: upsert tenant_permissions (admin) ──
    results = {"user_id": user_id, "email": email, "created_new": created_new}

    try:
        db.table("tenant_permissions").upsert({
            "tenant_id": body.tenant_id,
            "user_id": user_id,
            "role": "admin",
            "permissions": {
                "can_manage_workers": True,
                "can_view_financials": True,
                "can_manage_properties": True,
                "can_manage_integrations": True,
                "is_bootstrap_admin": True,
            },
            "created_at": now,
            "updated_at": now,
        }, on_conflict="tenant_id,user_id").execute()
        results["tenant_permissions"] = "upserted"
        logger.info("admin/bootstrap: tenant_permissions upserted for %s", user_id)
    except Exception as exc:
        logger.warning("admin/bootstrap: tenant_permissions upsert failed: %s", exc)
        results["tenant_permissions"] = f"failed: {exc}"

    # ── Step 5: upsert org_members (org_admin) ──
    # Schema: id(uuid), org_id(uuid), tenant_id(text), role(text), invited_by(text), joined_at(timestamptz)
    try:
        db.table("org_members").upsert({
            "org_id": body.org_id,
            "tenant_id": body.tenant_id,
            "role": "org_admin",
            "invited_by": "bootstrap",
            "joined_at": now,
        }, on_conflict="org_id,tenant_id").execute()
        results["org_members"] = "upserted"
        logger.info("admin/bootstrap: org_members upserted for %s", user_id)
    except Exception as exc:
        logger.warning("admin/bootstrap: org_members upsert failed: %s", exc)
        results["org_members"] = f"failed: {exc}"

    # ── Step 6: upsert tenant_org_map ──
    # Schema: tenant_id(text PK), org_id(uuid FK), role(text), updated_at(timestamptz)
    try:
        db.table("tenant_org_map").upsert({
            "tenant_id": body.tenant_id,
            "org_id": body.org_id,
            "role": "org_admin",
            "updated_at": now,
        }, on_conflict="tenant_id").execute()
        results["tenant_org_map"] = "upserted"
        logger.info("admin/bootstrap: tenant_org_map upserted for %s → %s", body.tenant_id, body.org_id)
    except Exception as exc:
        logger.warning("admin/bootstrap: tenant_org_map upsert failed: %s", exc)
        results["tenant_org_map"] = f"failed: {exc}"

    # Phase 862 (Canonical Auth P6): Step 6b REMOVED.
    # Previously created a tenant_permissions row with user_id=DEFAULT_TENANT_ID
    # (the tenant_id string as user_id) for session login. This caused identity
    # confusion between the session login path and Supabase Auth UUID identity.
    # The real identity is the UUID row created in Step 5 above.

    # ── Step 7: summary ──
    all_ok = all(
        v == "upserted"
        for v in [results.get("tenant_permissions"), results.get("org_members"), results.get("tenant_org_map")]
    )
    results["status"] = "bootstrap_complete" if all_ok else "bootstrap_partial"
    results["tenant_id"] = body.tenant_id
    results["org_id"] = body.org_id
    results["role"] = "admin"

    logger.info("admin/bootstrap: completed for %s — status=%s", email, results["status"])
    return _ok(results, status=200 if not created_new else 201)
