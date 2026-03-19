"""
Phase 760 — User↔Tenant Bridge Service
=========================================

Bridges Supabase Auth users (UUID-based) to iHouse tenant_id scheme.

On signup: auto-provisions tenant_permissions row for the new user.
On signin: looks up the user's tenant_id and role from tenant_permissions.

This ensures that Supabase Auth UUIDs are transparently mapped to the
existing iHouse tenant isolation model so all existing routes keep working.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# The default tenant_id for new users when no specific mapping exists.
# In a multi-tenant system this would be looked up from the org,
# but for iHouse V1 there is a single primary tenant.
DEFAULT_TENANT_ID = "tenant_e2e_amended"

# Default role for newly created users (admin bootstrap is separate)
DEFAULT_SIGNUP_ROLE = "manager"


def _get_db() -> Any:
    """Get Supabase client with service_role key."""
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)


def provision_user_tenant(
    db: Any,
    user_id: str,
    *,
    tenant_id: Optional[str] = None,
    role: Optional[str] = None,
    permissions: Optional[dict] = None,
) -> Optional[dict]:
    """
    Create a tenant_permissions row for a new Supabase Auth user.

    This bridges the Supabase Auth UUID → iHouse tenant_id scheme.
    Called automatically on /auth/signup.

    Args:
        db:           Supabase client.
        user_id:      Supabase Auth UUID.
        tenant_id:    Target tenant (defaults to DEFAULT_TENANT_ID).
        role:         User role (defaults to DEFAULT_SIGNUP_ROLE).
        permissions:  Optional JSONB capabilities.

    Returns:
        The created row dict, or None on failure. Never raises.
    """
    resolved_tenant = tenant_id or DEFAULT_TENANT_ID
    resolved_role = role or DEFAULT_SIGNUP_ROLE
    now = datetime.now(tz=timezone.utc).isoformat()

    row = {
        "tenant_id":   resolved_tenant,
        "user_id":     user_id,
        "role":        resolved_role,
        "permissions": permissions or {},
        "created_at":  now,
        "updated_at":  now,
    }

    try:
        result = (
            db.table("tenant_permissions")
            .upsert(row, on_conflict="tenant_id,user_id")
            .execute()
        )
        saved = (result.data or [{}])[0]
        logger.info(
            "tenant_bridge: provisioned user=%s → tenant=%s role=%s",
            user_id, resolved_tenant, resolved_role,
        )
        return saved
    except Exception as exc:
        logger.warning(
            "tenant_bridge: failed to provision user=%s → tenant=%s: %s",
            user_id, resolved_tenant, exc,
        )
        return None


def lookup_user_tenant(db: Any, user_id: str) -> Optional[dict]:
    """
    Look up the tenant mapping for a Supabase Auth user.

    Args:
        db:       Supabase client.
        user_id:  Supabase Auth UUID.

    Returns:
        Dict with {tenant_id, role, permissions} or None if not found.
        Never raises.
    """
    try:
        result = (
            db.table("tenant_permissions")
            .select("tenant_id, role, permissions, is_active, language")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if rows:
            return rows[0]
        return None
    except Exception as exc:
        logger.warning(
            "tenant_bridge: failed to look up tenant for user=%s: %s",
            user_id, exc,
        )
        return None
