"""
Phase 760 — User↔Tenant Bridge Service
Phase 862 (Canonical Auth P5) — Removed legacy defaults
=========================================

Bridges Supabase Auth users (UUID-based) to iHouse tenant_id scheme.

On signup: identity is created in Supabase Auth only (Phase 862 P1).
           Tenant provisioning requires explicit admin invite or approval.
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

# Phase 862 (Canonical Auth P5): legacy defaults REMOVED.
# Previously: DEFAULT_TENANT_ID = "tenant_e2e_amended"
# Previously: DEFAULT_SIGNUP_ROLE = "manager"
# All provisioning must now supply explicit tenant_id and role.
# These sentinel values exist ONLY for backward-compatible imports.
DEFAULT_TENANT_ID = None  # type: ignore[assignment]
DEFAULT_SIGNUP_ROLE = None  # type: ignore[assignment]


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
    tenant_id: str,
    role: str,
    permissions: Optional[dict] = None,
) -> Optional[dict]:
    """
    Create a tenant_permissions row for a Supabase Auth user.

    Phase 862 (Canonical Auth P5): tenant_id and role are now REQUIRED.
    No defaults — callers must supply explicit values from the invite,
    bootstrap, or approval flow.

    Args:
        db:           Supabase client.
        user_id:      Supabase Auth UUID.
        tenant_id:    Target tenant (REQUIRED).
        role:         User role (REQUIRED).
        permissions:  Optional JSONB capabilities.

    Returns:
        The created row dict, or None on failure. Never raises.

    Raises:
        ValueError: if tenant_id or role is empty/None.
    """
    if not tenant_id or not tenant_id.strip():
        raise ValueError("tenant_id is required — no default tenant allowed (Phase 862 P5)")
    if not role or not role.strip():
        raise ValueError("role is required — no default role allowed (Phase 862 P5)")

    now = datetime.now(tz=timezone.utc).isoformat()

    row = {
        "tenant_id":   tenant_id.strip(),
        "user_id":     user_id,
        "role":        role.strip().lower(),
        "is_active":   True,  # Phase 857: always reactivate on provision (audit D8)
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
            user_id, tenant_id, role,
        )
        return saved
    except Exception as exc:
        logger.warning(
            "tenant_bridge: failed to provision user=%s → tenant=%s: %s",
            user_id, tenant_id, exc,
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
