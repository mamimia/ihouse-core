"""
Phase 1023 — Delegated Authority: Extended Capability Model
===========================================================

Extends Phase 862 P31 with a full fine-grained capability taxonomy.
Backward-compatible: existing Phase 862 coarse keys (financial, staffing, etc.)
are kept in ALL_CAPABILITIES so existing guards continue to work unchanged.

Phase 1023 adds 22 fine-grained keys across 5 groups:
    booking_exceptions  — booking flags and approval actions
    staff_management    — roster, assignment, and worker lifecycle
    property_operations — task takeover, reassign, schedule, status
    internal_settlement — deposit and settlement lifecycle
    financial_visibility — revenue, statements, export (read-only)

Storage in tenant_permissions.permissions JSONB:
    { "capabilities": { "booking_approve_early_co": true, "financial": true } }

Values are plain booleans. Property scoping (Phase 1023-D) will extend
these to {"granted": bool, "property_ids": [...]} — parser handles both shapes.

Admin always has all capabilities implicitly (enforced in capability_guard.py).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Phase 862 legacy coarse capabilities (kept for backward compat) ──
_LEGACY_CAPABILITIES: frozenset[str] = frozenset({
    "financial",
    "staffing",
    "properties",
    "bookings",
    "maintenance",
    "settings",
    "intake",
})

# ── Phase 1023 fine-grained capability groups ──
# Each group is: { "label": str, "capabilities": [ (key, description), ... ] }
CAPABILITY_GROUPS: list[dict] = [
    {
        "group": "booking_exceptions",
        "label": "Booking Exceptions",
        "capabilities": [
            ("booking_flag_vip",           "Flag bookings as VIP"),
            ("booking_flag_dispute",       "Flag bookings as disputed"),
            ("booking_approve_early_co",   "Approve early checkout"),
            ("booking_approve_self_ci",    "Approve self check-in"),
            ("booking_create_manual",      "Create manual bookings"),
            ("booking_exception_notes",    "Add operator notes to bookings"),
        ],
    },
    {
        "group": "staff_management",
        "label": "Staff Management",
        "capabilities": [
            ("staff_view_roster",           "View staff roster & contact details"),
            ("staff_manage_assignments",    "Assign / unassign staff to properties"),
            ("staff_approve_availability",  "Approve / reject availability requests"),
            ("staff_create_worker",         "Create new worker accounts (invite)"),
            ("staff_deactivate_worker",     "Archive / deactivate worker accounts"),
        ],
    },
    {
        "group": "property_operations",
        "label": "Property Operations",
        "capabilities": [
            ("ops_task_takeover",           "Take over worker tasks"),
            ("ops_task_reassign",           "Reassign tasks between workers"),
            ("ops_schedule_tasks",          "Create ad-hoc operational tasks"),
            ("ops_view_cleaning_reports",   "View cleaning completion reports & photos"),
            ("ops_set_property_status",     "Set property operational status"),
        ],
    },
    {
        "group": "internal_settlement",
        "label": "Internal Settlement",
        "capabilities": [
            ("settlement_view_deposits",       "View deposit collection records"),
            ("settlement_finalize",            "Finalize checkout settlements"),
            ("settlement_approve_deductions",  "Approve damage deductions"),
            ("settlement_void",                "Void a finalized settlement"),
        ],
    },
    {
        "group": "financial_visibility",
        "label": "Financial Visibility",
        "capabilities": [
            ("financial_view_revenue",     "View revenue & occupancy metrics"),
            ("financial_view_owner_stmt",  "View owner statements"),
            ("financial_export",           "Export financial data"),
        ],
    },
]

# Flat set of all fine-grained Phase 1023 keys
_FINE_CAPABILITIES: frozenset[str] = frozenset(
    key
    for group in CAPABILITY_GROUPS
    for key, _ in group["capabilities"]
)

# Union: Phase 862 legacy + Phase 1023 fine-grained
ALL_CAPABILITIES: frozenset[str] = _LEGACY_CAPABILITIES | _FINE_CAPABILITIES

# Conservative defaults for a newly delegated manager (least-privilege)
DEFAULT_MANAGER_CAPABILITIES: dict[str, bool] = {}


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_cap_value(v: Any) -> bool:
    """
    Parse a single capability value from the JSONB blob.

    Phase 862 format: plain bool  → True/False
    Phase 1023-D format (future): {"granted": bool, "property_ids": [...]}

    This parser handles both. Property-scoped format is accepted but
    property_ids filtering is not enforced until Phase 1023-D.
    """
    if isinstance(v, bool):
        return v
    if isinstance(v, dict):
        return bool(v.get("granted", False))
    return bool(v)


def get_delegated_capabilities(permissions: Optional[dict]) -> dict[str, bool]:
    """
    Extract delegated capabilities from a permissions JSONB blob.

    Returns { capability_key: True/False } for all known capabilities.
    Unknown keys are silently ignored.
    Handles both Phase 862 (plain bool) and Phase 1023-D (dict) value shapes.
    """
    if not permissions or not isinstance(permissions, dict):
        return {}

    caps = permissions.get("capabilities", {})
    if not isinstance(caps, dict):
        return {}

    return {
        k: _parse_cap_value(v)
        for k, v in caps.items()
        if k in ALL_CAPABILITIES
    }


def has_capability(permissions: Optional[dict], capability: str) -> bool:
    """
    Check if a specific capability is delegated.

    Phase 1023: supports both flat bool and dict value shapes.
    Admin bypass is NOT done here — that is enforced in capability_guard.py.
    """
    caps = get_delegated_capabilities(permissions)
    return caps.get(capability, False)


def get_grouped_capabilities(permissions: Optional[dict]) -> list[dict]:
    """
    Return the full capability taxonomy with current grant state for a manager.

    Used by the Admin UI to render the Delegated Authority tab.

    Returns:
        [
            {
                "group": "booking_exceptions",
                "label": "Booking Exceptions",
                "capabilities": [
                    {
                        "key": "booking_approve_early_co",
                        "label": "Approve early checkout",
                        "granted": True,
                    },
                    ...
                ]
            },
            ...
        ]
    """
    current = get_delegated_capabilities(permissions)
    result = []
    for group in CAPABILITY_GROUPS:
        caps_out = [
            {
                "key": key,
                "label": label,
                "granted": current.get(key, False),
            }
            for key, label in group["capabilities"]
        ]
        result.append({
            "group": group["group"],
            "label": group["label"],
            "capabilities": caps_out,
        })
    return result


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def set_capabilities(
    db: Any,
    tenant_id: str,
    user_id: str,
    capabilities: dict[str, bool],
    admin_user_id: str = "",
    write_audit: bool = True,
) -> dict:
    """
    Set delegated capabilities for a manager.

    Args:
        db:             Supabase client.
        tenant_id:      Target tenant.
        user_id:        Target user (must have role=manager in this tenant).
        capabilities:   Dict of capability_key → True/False.
        admin_user_id:  User ID of the admin performing this action (for audit).
        write_audit:    If True, writes audit_events rows for changed capabilities.

    Returns:
        {"ok": True, "capabilities": {all current caps}, "audit_events_written": N}

    Raises:
        ValueError: if user is not a manager in this tenant.
        RuntimeError: on DB failure.
    """
    # Validate: only known keys accepted
    validated: dict[str, bool] = {}
    for k, v in capabilities.items():
        if k in ALL_CAPABILITIES:
            validated[k] = bool(v)
        else:
            logger.warning("set_capabilities: unknown capability '%s' ignored", k)

    if not validated:
        return {"ok": True, "capabilities": {}, "audit_events_written": 0}

    try:
        # Fetch current state
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

        # Merge new values into existing caps
        current_perms = row.get("permissions") or {}
        if not isinstance(current_perms, dict):
            current_perms = {}
        current_caps = current_perms.get("capabilities", {})

        # Track what actually changed (for audit)
        changes: list[dict] = []
        for k, new_val in validated.items():
            old_val = _parse_cap_value(current_caps.get(k, False))
            if old_val != new_val:
                changes.append({
                    "capability": k,
                    "old": old_val,
                    "new": new_val,
                })
            current_caps[k] = new_val

        current_perms["capabilities"] = current_caps

        # Persist
        db.table("tenant_permissions").update({
            "permissions": current_perms,
        }).eq("tenant_id", tenant_id).eq("user_id", user_id).execute()

        logger.info(
            "delegated_capabilities: updated caps for user=%s tenant=%s changes=%s",
            user_id, tenant_id, changes,
        )

        # Write audit_events
        audit_count = 0
        if write_audit and changes:
            audit_count = _write_capability_audit_events(
                db=db,
                tenant_id=tenant_id,
                manager_user_id=user_id,
                admin_user_id=admin_user_id,
                changes=changes,
            )

        return {
            "ok": True,
            "capabilities": current_caps,
            "audit_events_written": audit_count,
        }

    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to set capabilities: {exc}") from exc


def set_section_capabilities(
    db: Any,
    tenant_id: str,
    user_id: str,
    section: str,
    capabilities: dict[str, bool],
    admin_user_id: str = "",
) -> dict:
    """
    Atomically update all capabilities in a named section.

    The section name must match a CAPABILITY_GROUPS[*]["group"] value.
    Only keys belonging to that section are accepted; others are ignored
    with a warning (prevents cross-section pollution).

    This is the preferred write path from the Admin UI — one PATCH per group.
    """
    # Validate section name and get allowed keys for that section
    allowed_keys: set[str] = set()
    for group in CAPABILITY_GROUPS:
        if group["group"] == section:
            allowed_keys = {key for key, _ in group["capabilities"]}
            break

    if not allowed_keys:
        raise ValueError(f"Unknown section '{section}'")

    # Filter to only keys in this section
    section_caps: dict[str, bool] = {}
    for k, v in capabilities.items():
        if k in allowed_keys:
            section_caps[k] = bool(v)
        else:
            logger.warning(
                "set_section_capabilities: key '%s' not in section '%s', ignored",
                k, section,
            )

    return set_capabilities(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        capabilities=section_caps,
        admin_user_id=admin_user_id,
        write_audit=True,
    )


# ---------------------------------------------------------------------------
# Audit writer
# ---------------------------------------------------------------------------

def _write_capability_audit_events(
    db: Any,
    tenant_id: str,
    manager_user_id: str,
    admin_user_id: str,
    changes: list[dict],
) -> int:
    """
    Write audit_events rows for each capability change.

    Action names:
        MANAGER_CAPABILITY_GRANTED  — new_val = True
        MANAGER_CAPABILITY_REVOKED  — new_val = False

    Returns the number of rows successfully written.
    """
    import uuid as _uuid
    from datetime import datetime, timezone

    written = 0
    for change in changes:
        action = (
            "MANAGER_CAPABILITY_GRANTED"
            if change["new"]
            else "MANAGER_CAPABILITY_REVOKED"
        )
        payload = {
            "capability": change["capability"],
            "granted": change["new"],
            "previous_granted": change["old"],
            "changed_by_admin_id": admin_user_id,
            "manager_user_id": manager_user_id,
        }
        try:
            db.table("audit_events").insert({
                "tenant_id": tenant_id,
                "actor_id": admin_user_id or "system",
                "action": action,
                "entity_type": "manager_permission",
                "entity_id": manager_user_id,
                "payload": payload,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
            written += 1
        except Exception as exc:
            # Best-effort: log but do not fail the capability write
            logger.warning(
                "delegated_capabilities: audit write failed for %s capability=%s: %s",
                action, change["capability"], exc,
            )
    return written
