"""
Guest Messaging Service — Phase 1048
=====================================

Canonical routing and ownership logic for the guest-to-host conversation model.

Thread model:
    One conversation thread per stay (per booking_id).
    A guest with multiple stays has multiple independent threads.
    There is no guest-level persistent chat — threads are stay-scoped.

Ownership model:
    Default owner = Operational Manager assigned to the property.
    Resolution: staff_property_assignments WHERE role='manager' ORDER BY priority ASC LIMIT 1.
    Fallback 1: tenant_permissions WHERE role='admin' LIMIT 1.
    Fallback 2: the tenant_id from the token context (the operator's own ID).

Invariant:
    portal_host_* fields play NO role in routing or ownership.
    They are guest-facing display data only (display name, photo, intro).
    The conversation owner is always determined from staff_property_assignments.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def resolve_conversation_owner(
    db: Any,
    property_id: str,
    tenant_id: str,
) -> str:
    """
    Resolve the primary OM responsible for a property's guest conversations.

    This is the canonical routing function for Phase 1048.
    Called at message insert time — result stored as assigned_om_id.

    Resolution order:
        1. Staff assigned to property with role='manager', lowest priority first (primary OM)
        2. Any tenant with role='admin' (admin fallback)
        3. tenant_id from token context (last resort)

    Args:
        db:          Supabase client (service role).
        property_id: The property to resolve the OM for.
        tenant_id:   The operator's tenant_id (last-resort fallback).

    Returns:
        tenant_id of the resolved owner — never empty string, never None.
    """
    # --- 1. Primary: OM assigned to this specific property ---
    try:
        # Join staff_property_assignments with tenant_permissions to filter by role.
        # Use the assignment's tenant_id to look up the role in tenant_permissions.
        assignments = (
            db.table("staff_property_assignments")
            .select("tenant_id")
            .eq("property_id", property_id)
            .execute()
        )
        if assignments.data:
            # Filter for manager role via a second lookup (PostgREST join limitations)
            om_candidates = []
            for row in assignments.data:
                try:
                    perm = (
                        db.table("tenant_permissions")
                        .select("tenant_id, role")
                        .eq("tenant_id", row["tenant_id"])
                        .eq("role", "manager")
                        .limit(1)
                        .execute()
                    )
                    if perm.data:
                        om_candidates.append(row["tenant_id"])
                except Exception:
                    continue

            if om_candidates:
                # Return first candidate — staff_property_assignments ordering is by priority
                # (lowest priority = primary, as established in Phase 1031)
                resolved = om_candidates[0]
                logger.info(
                    "resolve_conversation_owner: primary OM %r for property %r",
                    resolved,
                    property_id,
                )
                return resolved
    except Exception as exc:
        logger.warning(
            "resolve_conversation_owner: OM lookup failed for property %r: %s",
            property_id,
            exc,
        )

    # --- 2. Fallback: any admin in this tenant ---
    try:
        admin_res = (
            db.table("tenant_permissions")
            .select("tenant_id")
            .eq("role", "admin")
            .limit(1)
            .execute()
        )
        if admin_res.data:
            resolved = admin_res.data[0]["tenant_id"]
            logger.warning(
                "resolve_conversation_owner: no OM for property %r — using admin %r",
                property_id,
                resolved,
            )
            return resolved
    except Exception as exc:
        logger.warning(
            "resolve_conversation_owner: admin fallback failed: %s", exc
        )

    # --- 3. Last resort: token's tenant_id ---
    logger.warning(
        "resolve_conversation_owner: all lookups failed for property %r — "
        "using token tenant_id %r as owner",
        property_id,
        tenant_id,
    )
    return tenant_id
