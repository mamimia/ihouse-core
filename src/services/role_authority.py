"""
Phase 759 — Role Authority Service
====================================

Canonical role lookup from tenant_permissions table.

Auth endpoints MUST use this module to determine the role for a JWT,
instead of accepting a self-declared role from the request body.

Design:
    - lookup_role(db, tenant_id, user_id) → str | None
    - Returns the role from tenant_permissions for the given (tenant_id, user_id).
    - Returns None if no record exists (caller should decide: reject or assign default).
    - Never raises.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default role for users with no tenant_permissions record
# This is a safe fallback — "manager" grants operational access but not admin.
DEFAULT_ROLE_IF_MISSING = "manager"


def lookup_role(db: Any, tenant_id: str, user_id: str) -> Optional[str]:
    """
    Look up the canonical role for a user from tenant_permissions.

    Args:
        db:        Supabase client instance.
        tenant_id: Tenant scope.
        user_id:   The user identifier (JWT sub or Supabase UUID).

    Returns:
        Role string if found, None if no record exists.
        Never raises.
    """
    try:
        result = (
            db.table("tenant_permissions")
            .select("role")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if rows:
            role = rows[0].get("role")
            if role:
                return str(role).strip().lower()
        return None
    except Exception:  # noqa: BLE001
        logger.warning(
            "role_authority: failed to look up role for tenant=%s user=%s",
            tenant_id, user_id,
        )
        return None


def resolve_role(
    db: Any,
    tenant_id: str,
    user_id: str,
    requested_role: Optional[str] = None,
) -> str:
    """
    Resolve the authoritative role for a user.

    Priority:
        1. DB role from tenant_permissions (always wins)
        2. If no DB record: use DEFAULT_ROLE_IF_MISSING

    If the caller supplied a requested_role and it differs from the DB role,
    a warning is logged (the DB role still wins).

    Returns:
        The resolved role string.
    """
    db_role = lookup_role(db, tenant_id, user_id)

    if db_role:
        if requested_role and requested_role.strip().lower() != db_role:
            logger.warning(
                "role_authority: requested_role='%s' ignored — "
                "DB role='%s' for tenant=%s user=%s",
                requested_role, db_role, tenant_id, user_id,
            )
        return db_role

    # No DB record — Phase 831: prefer requested_role, fall back to default
    resolved = (requested_role.strip().lower() if requested_role else DEFAULT_ROLE_IF_MISSING)
    logger.info(
        "role_authority: no tenant_permissions record for tenant=%s user=%s, "
        "using %s role '%s'",
        tenant_id, user_id,
        "requested" if requested_role else "default",
        resolved,
    )
    return resolved
