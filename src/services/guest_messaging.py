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
    Resolve the primary OM's user_id for a property's guest conversations.

    This is the canonical routing function for Phase 1048.
    Called at message insert time — result stored as assigned_om_id.

    IMPORTANT: we store user_id (not tenant_id) in assigned_om_id.
    In this system all staff members share the same tenant_id.
    user_id is the per-person identifier that distinguishes individuals.

    Resolution order:
        1. staff_property_assignments WHERE property_id = X
           JOIN tenant_permissions ON user_id = user_id WHERE role='manager'
           ORDER BY priority ASC LIMIT 1 (lowest priority = primary OM)
        2. tenant_permissions WHERE role='admin' LIMIT 1 (admin fallback)
        3. tenant_id from token context (absolute last resort)

    Args:
        db:          Supabase client (service role).
        property_id: The property to resolve the OM for.
        tenant_id:   The operator's tenant_id (last-resort fallback value only).

    Returns:
        user_id of the resolved owner — never empty string, never None.
    """
    # --- 1. Primary: OM with lowest priority assigned to this property ---
    try:
        # Fetch all assignments for this property, ordered by priority
        assignments = (
            db.table("staff_property_assignments")
            .select("user_id, priority")
            .eq("property_id", property_id)
            .order("priority", desc=False)
            .execute()
        )
        if assignments.data:
            for row in assignments.data:
                uid = row.get("user_id")
                if not uid:
                    continue
                # Verify this user has role='manager' in tenant_permissions
                try:
                    perm = (
                        db.table("tenant_permissions")
                        .select("user_id, role")
                        .eq("user_id", uid)
                        .eq("role", "manager")
                        .limit(1)
                        .execute()
                    )
                    if perm.data:
                        logger.info(
                            "resolve_conversation_owner: primary OM user_id=%r (priority=%d) "
                            "for property %r",
                            uid,
                            row.get("priority", 999),
                            property_id,
                        )
                        return uid
                except Exception:
                    continue
    except Exception as exc:
        logger.warning(
            "resolve_conversation_owner: OM lookup failed for property %r: %s",
            property_id,
            exc,
        )

    # --- 2. Fallback: any user with role='admin' in this tenant ---
    try:
        admin_res = (
            db.table("tenant_permissions")
            .select("user_id, display_name")
            .eq("tenant_id", tenant_id)
            .eq("role", "admin")
            .limit(1)
            .execute()
        )
        if admin_res.data:
            uid = admin_res.data[0].get("user_id", "")
            display = admin_res.data[0].get("display_name", "admin")
            if uid:
                logger.warning(
                    "resolve_conversation_owner: no OM for property %r — "
                    "using admin user_id=%r (%s)",
                    property_id,
                    uid,
                    display,
                )
                return uid
    except Exception as exc:
        logger.warning(
            "resolve_conversation_owner: admin fallback failed: %s", exc
        )

    # --- 3. Last resort: return tenant_id as a string marker ---
    # This is a degraded state — inbox scoping will not work correctly.
    logger.warning(
        "resolve_conversation_owner: all lookups failed for property %r — "
        "using tenant_id %r as last-resort owner marker",
        property_id,
        tenant_id,
    )
    return tenant_id

