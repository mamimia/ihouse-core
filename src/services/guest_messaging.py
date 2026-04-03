"""
Guest Messaging Service — Phase 1048
=====================================

Canonical routing and ownership logic for the guest-to-host conversation model.

Thread model:
    One conversation thread per stay (per booking_id).
    A guest with multiple stays has multiple independent threads.
    There is no guest-level persistent chat — threads are stay-scoped.

Ownership model — current (Phase 1048 scaffold):
    The `assigned_om_id` field on `guest_chat_messages` is a TEMPORARY routing
    scaffold, not the permanent long-term ownership model.

    It exists to give inbox queries a scoping anchor while the broader conversation
    model is built out (Phases 1049–1056). The value may be an OM's tenant_id,
    an admin's tenant_id, or the operator's own tenant_id — it is not OM-only.

    The canonical long-term ownership record will be the
    `guest_conversation_assignments` table (Phase 1054), which:
    - Records every ownership transfer with full audit trail
    - Supports any staff role (OM, admin, concierge, named staff)
    - Is the source of truth for who is responsible for a thread

    When Phase 1054 is built, both `assigned_om_id` (for query efficiency)
    AND `guest_conversation_assignments` (for canonical truth) will be updated
    on every reassignment.

Resolution order (current — Phase 1048):
    1. Staff assigned to property with role='manager' (primary OM, lowest priority)
    2. Any tenant with role='admin' (admin fallback)
    3. tenant_id from token context (last resort)

portal_host_* invariant:
    portal_host_name, portal_host_photo_url, portal_host_intro play NO role here.
    They are guest-facing display data only (Phase 1047B).
    Never use them for routing, ownership, or audit.
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
