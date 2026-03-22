"""
Phase 862 P17 — Submitter → Owner State Machine
==================================================

Defines allowed state transitions for intake requests and
the approval function that provisions owner membership.

States:
    draft           → pending_review
    pending_review  → approved | rejected | expired
    approved        → owner_provisioned
    rejected        → (terminal)
    expired         → (terminal)
    owner_provisioned → (terminal)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── State transition map ──
# Each key maps to a set of allowed next states.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft":              {"pending_review"},
    "pending_review":     {"approved", "rejected", "expired"},
    "approved":           {"owner_provisioned"},
    # Terminal states — no transitions out
    "rejected":           set(),
    "expired":            set(),
    "owner_provisioned":  set(),
}

ALL_STATES = frozenset(ALLOWED_TRANSITIONS.keys())


def can_transition(current: str, target: str) -> bool:
    """Check if a transition from current → target is allowed."""
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    return target in allowed


def transition_intake(
    db: Any,
    intake_id: str,
    *,
    current_status: str,
    target_status: str,
    admin_user_id: Optional[str] = None,
) -> dict:
    """
    Transition an intake request from current_status to target_status.

    Args:
        db:             Supabase client.
        intake_id:      UUID of the intake request.
        current_status: Expected current status (for safety).
        target_status:  Desired new status.
        admin_user_id:  UUID of the admin performing the action (for audit).

    Returns:
        {"ok": True, "status": target_status} on success.

    Raises:
        ValueError: if the transition is not allowed.
        RuntimeError: if the DB update fails.
    """
    if not can_transition(current_status, target_status):
        raise ValueError(
            f"Invalid transition: '{current_status}' → '{target_status}'. "
            f"Allowed: {ALLOWED_TRANSITIONS.get(current_status, set())}"
        )

    now = datetime.now(tz=timezone.utc).isoformat()
    update = {"status": target_status, "updated_at": now}

    if admin_user_id:
        update["admin_notes"] = f"Transitioned by admin {admin_user_id} at {now}"

    try:
        db.table("intake_requests").update(update).eq("id", intake_id).execute()
        logger.info(
            "submitter_states: %s → %s for intake=%s (admin=%s)",
            current_status, target_status, intake_id, admin_user_id,
        )
        return {"ok": True, "status": target_status}
    except Exception as exc:
        raise RuntimeError(f"DB update failed for intake {intake_id}: {exc}") from exc


def approve_intake(
    db: Any,
    intake_id: str,
    *,
    admin_user_id: str,
    tenant_id: str,
) -> dict:
    """
    Approve an intake request and provision the submitter as an owner.

    Steps:
    1. Verify the intake is in 'pending_review' or 'approved' state
    2. Transition to 'approved' (if pending_review)
    3. Provision tenant_permissions with role='owner'
    4. Transition to 'owner_provisioned'

    Args:
        db:             Supabase client.
        intake_id:      UUID of the intake request.
        admin_user_id:  UUID of the admin approving.
        tenant_id:      Tenant to provision the owner into.

    Returns:
        {"ok": True, "status": "owner_provisioned", "user_id": ..., "tenant_id": ...}

    Raises:
        ValueError: if intake not found, no linked user, or invalid state.
        RuntimeError: on DB failure.
    """
    # Fetch the intake request
    result = (
        db.table("intake_requests")
        .select("id, user_id, status, email")
        .eq("id", intake_id)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if not rows:
        raise ValueError(f"Intake request {intake_id} not found.")

    intake = rows[0]
    current_status = intake.get("status", "")
    user_id = intake.get("user_id")

    if not user_id:
        raise ValueError(
            f"Intake {intake_id} has no linked user_id. "
            "Cannot provision owner without an authenticated identity."
        )

    # Step 1: transition to approved (if not already)
    if current_status == "pending_review":
        transition_intake(
            db, intake_id,
            current_status="pending_review",
            target_status="approved",
            admin_user_id=admin_user_id,
        )
    elif current_status != "approved":
        raise ValueError(
            f"Cannot approve intake {intake_id}: current status is '{current_status}'. "
            "Must be 'pending_review' or 'approved'."
        )

    # Step 2: provision tenant_permissions as owner
    from services.tenant_bridge import provision_user_tenant
    provision_result = provision_user_tenant(
        db, user_id,
        tenant_id=tenant_id,
        role="owner",
    )
    if not provision_result:
        raise RuntimeError(f"Failed to provision owner membership for user {user_id}")

    # Step 3: transition to owner_provisioned
    transition_intake(
        db, intake_id,
        current_status="approved",
        target_status="owner_provisioned",
        admin_user_id=admin_user_id,
    )

    logger.info(
        "submitter_states: intake=%s approved and provisioned as owner user=%s tenant=%s",
        intake_id, user_id, tenant_id,
    )

    return {
        "ok": True,
        "status": "owner_provisioned",
        "user_id": user_id,
        "tenant_id": tenant_id,
    }
