"""
Phase 862 P31 — Operational Manager Delegated Capability Model
================================================================

Defines the capability model for operational managers.
An admin can delegate specific capabilities to each manager independently.

Capabilities are stored in the `permissions` JSONB column of `tenant_permissions`.
A manager's effective access = base manager access + delegated capabilities.

Capability categories:
    financial    — view/export financial reports, owner statements
    staffing     — invite/deactivate workers, manage schedules
    properties   — edit property details, manage listings
    bookings     — modify bookings, handle cancellations
    maintenance  — approve maintenance requests, assign priorities
    settings     — edit tenant settings (names, configs)
    intake       — review and approve intake requests

Each capability is a boolean. Missing = not delegated.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── All known delegatable capabilities ──
ALL_CAPABILITIES: frozenset[str] = frozenset({
    "financial",
    "staffing",
    "properties",
    "bookings",
    "maintenance",
    "settings",
    "intake",
})

# Default capabilities for a new manager (conservative — admin can expand)
DEFAULT_MANAGER_CAPABILITIES: dict[str, bool] = {
    "bookings": True,
    "maintenance": True,
}


def get_delegated_capabilities(permissions: Optional[dict]) -> dict[str, bool]:
    """
    Extract delegated capabilities from a permissions JSONB blob.

    Returns a dict of capability_name → True/False.
    Only known capabilities are included; unknown keys are ignored.
    """
    if not permissions or not isinstance(permissions, dict):
        return {}

    caps = permissions.get("capabilities", {})
    if not isinstance(caps, dict):
        return {}

    return {
        k: bool(v)
        for k, v in caps.items()
        if k in ALL_CAPABILITIES
    }


def has_capability(permissions: Optional[dict], capability: str) -> bool:
    """Check if a specific capability is delegated."""
    caps = get_delegated_capabilities(permissions)
    return caps.get(capability, False)


def set_capabilities(
    db: Any,
    tenant_id: str,
    user_id: str,
    capabilities: dict[str, bool],
) -> dict:
    """
    Set delegated capabilities for a manager.

    Args:
        db:           Supabase client.
        tenant_id:    Target tenant.
        user_id:      Target user (must have role=manager in this tenant).
        capabilities: Dict of capability_name → True/False.

    Returns:
        {"ok": True, "capabilities": {effective caps}} on success.

    Raises:
        ValueError: if user is not a manager in this tenant.
        RuntimeError: on DB failure.
    """
    # Validate capabilities
    validated = {}
    for k, v in capabilities.items():
        if k in ALL_CAPABILITIES:
            validated[k] = bool(v)
        else:
            logger.warning("set_capabilities: unknown capability '%s' ignored", k)

    # Fetch current permissions
    try:
        result = (
            db.table("tenant_permissions")
            .select("role, permissions")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            raise ValueError(f"User {user_id} not found in tenant {tenant_id}")

        row = rows[0]
        role = row.get("role", "")
        if role != "manager":
            raise ValueError(
                f"User {user_id} has role '{role}' — "
                "capability delegation is only for managers."
            )

        # Merge into existing permissions
        current_perms = row.get("permissions") or {}
        if not isinstance(current_perms, dict):
            current_perms = {}
        current_caps = current_perms.get("capabilities", {})
        current_caps.update(validated)
        current_perms["capabilities"] = current_caps

        # Update
        db.table("tenant_permissions").update({
            "permissions": current_perms,
        }).eq("tenant_id", tenant_id).eq("user_id", user_id).execute()

        logger.info(
            "delegated_capabilities: updated caps for user=%s tenant=%s: %s",
            user_id, tenant_id, validated,
        )
        return {"ok": True, "capabilities": current_caps}

    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to set capabilities: {exc}") from exc
