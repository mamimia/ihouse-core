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

# ── Phase 1023-C: Plain-language capability descriptions ──
# Each capability is: (key, label, description, power_type)
# power_type: "view" | "approve" | "edit" | "execute"
# description: plain-language explanation understandable by non-technical admins.
CAPABILITY_GROUPS: list[dict] = [
    {
        "group": "booking_exceptions",
        "label": "Booking Exceptions",
        "capabilities": [
            (
                "booking_flag_vip",
                "Flag bookings as VIP",
                "The manager can mark a guest booking as VIP, which triggers priority "
                "handling across the operational surface (housekeeping priority, task urgency). "
                "Does not change rates or communicate anything to the guest directly. "
                "Admin can always unflag.",
                "edit",
            ),
            (
                "booking_flag_dispute",
                "Flag bookings as disputed",
                "The manager can flag a booking as disputed — for example, if a guest "
                "raised a payment or damage claim. This is a visibility and triage flag only. "
                "It does not automatically issue a refund, deduction, or message to the guest. "
                "Only admins can resolve disputes.",
                "edit",
            ),
            (
                "booking_approve_early_co",
                "Approve early checkout",
                "The manager can approve a guest's request to check out earlier than "
                "the originally booked departure date. This may affect cleaning schedules. "
                "Does not automatically issue a partial refund — financial adjustments "
                "remain an admin action.",
                "approve",
            ),
            (
                "booking_approve_self_ci",
                "Approve self check-in",
                "The manager can approve a guest to self-check-in (e.g. via a keybox or "
                "smart lock) without a staff-assisted check-in walk-through. "
                "Only applies to properties set up for self-check-in. "
                "The manager cannot create or modify the access codes themselves.",
                "approve",
            ),
            (
                "booking_create_manual",
                "Create manual bookings",
                "The manager can create a manual booking directly in the system — "
                "for example, for a direct guest who is not arriving through an OTA. "
                "Admin should review all manual bookings for rate accuracy. "
                "The manager cannot modify OTA-sourced bookings.",
                "execute",
            ),
            (
                "booking_exception_notes",
                "Add operator notes to bookings",
                "The manager can write internal notes on any booking — "
                "for example, guest preferences, handover instructions, or issue logs. "
                "Notes are visible to admin and other staff but are never sent to guests. "
                "The manager cannot delete existing notes.",
                "edit",
            ),
        ],
    },
    {
        "group": "staff_management",
        "label": "Staff Management",
        "capabilities": [
            (
                "staff_view_roster",
                "View staff roster & contact details",
                "The manager can view the full list of staff members, their roles, "
                "assigned properties, and contact details (phone, LINE). "
                "Read-only — the manager cannot create or modify staff profiles.",
                "view",
            ),
            (
                "staff_manage_assignments",
                "Assign / unassign staff to properties",
                "The manager can assign or remove a worker from a property. "
                "This affects which tasks the worker receives and appears in their schedule. "
                "Does not create or delete the worker's account — only the assignment relationship.",
                "edit",
            ),
            (
                "staff_approve_availability",
                "Approve / reject availability requests",
                "The manager can approve or reject a worker's request to mark themselves "
                "unavailable for a specific date or period. "
                "Does not allow the manager to set availability on behalf of a worker — "
                "only to respond to worker-initiated requests.",
                "approve",
            ),
            (
                "staff_create_worker",
                "Create new worker accounts (invite)",
                "The manager can invite a new worker and create their basic staff profile. "
                "The manager cannot set pay rates, compliance document status, or sensitive "
                "employment fields — those remain admin-only. "
                "New accounts are created with the least-privilege worker role.",
                "execute",
            ),
            (
                "staff_deactivate_worker",
                "Archive / deactivate worker accounts",
                "The manager can deactivate a worker's account, removing their access to "
                "the platform and preventing new task assignments. "
                "Existing completed tasks and history are preserved. "
                "Account deletion is admin-only and cannot be delegated.",
                "execute",
            ),
        ],
    },
    {
        "group": "property_operations",
        "label": "Property Operations",
        "capabilities": [
            (
                "ops_task_takeover",
                "Take over worker tasks",
                "The manager can claim an in-progress or unacknowledged task and execute "
                "it themselves (or mark it done) — for example, if a worker is absent. "
                "This creates an audit record showing the manager completed the task. "
                "The original worker is notified of the reassignment.",
                "execute",
            ),
            (
                "ops_task_reassign",
                "Reassign tasks between workers",
                "The manager can move an upcoming or in-progress task from one worker "
                "to another. Only workers assigned to that property can receive the task. "
                "Does not allow the manager to create new task types — only reassign existing ones.",
                "edit",
            ),
            (
                "ops_schedule_tasks",
                "Create ad-hoc operational tasks",
                "The manager can schedule additional one-off tasks — for example, an "
                "unplanned deep clean or a maintenance inspection. "
                "These are not automatically billed or charged to guests. "
                "Recurring task schedules remain an admin configuration.",
                "execute",
            ),
            (
                "ops_view_cleaning_reports",
                "View cleaning completion reports & photos",
                "The manager can view the photo evidence and completion checklist "
                "submitted by cleaners after each task. "
                "Read-only — the manager cannot edit or delete submitted reports.",
                "view",
            ),
            (
                "ops_set_property_status",
                "Set property operational status",
                "The manager can change a property's operational status — for example, "
                "marking it temporarily offline for maintenance, or returning it to active. "
                "This affects what bookings can be made and may block OTA sync. "
                "Admin is notified whenever this status changes.",
                "edit",
            ),
        ],
    },
    {
        "group": "internal_settlement",
        "label": "Internal Settlement",
        "capabilities": [
            (
                "settlement_view_deposits",
                "View deposit collection records",
                "The manager can see which guests have paid a security deposit, "
                "the amount collected, and the collection method. "
                "Cannot collect, modify, or release deposits — view only.",
                "view",
            ),
            (
                "settlement_finalize",
                "Finalize checkout settlements",
                "The manager can mark a checkout settlement as complete after confirming "
                "the room condition and deposit return. "
                "This is a key operational handoff step. "
                "Finalized settlements cannot be reversed without admin action.",
                "execute",
            ),
            (
                "settlement_approve_deductions",
                "Approve damage deductions",
                "The manager can approve a proposed deduction from a guest's deposit — "
                "for example, for damaged items or extended stays. "
                "The deduction amount is set by the admin or system; the manager "
                "approves whether to apply it. Does not give the manager power to "
                "set deduction amounts independently.",
                "approve",
            ),
            (
                "settlement_void",
                "Void a finalized settlement",
                "The manager can void a settlement that was incorrectly finalized, "
                "returning it to a pending state for correction. "
                "All voids are logged with the manager's identity and reason. "
                "This is a high-trust action and should only be granted to senior managers.",
                "execute",
            ),
        ],
    },
    {
        "group": "financial_visibility",
        "label": "Financial Visibility",
        "capabilities": [
            (
                "financial_view_revenue",
                "View revenue & occupancy metrics",
                "The manager can view property revenue summaries and occupancy data — "
                "for operational planning only. "
                "Cannot see individual owner payouts, net rates, or OTA commission breakdowns. "
                "No export access is included.",
                "view",
            ),
            (
                "financial_view_owner_stmt",
                "View owner statements",
                "The manager can view the owner-facing settlement statements for any "
                "property. This is sensitive — it shows net payouts and deductions. "
                "Grant this only to managers who need to liaise directly with property owners. "
                "Read-only — cannot modify or send statements.",
                "view",
            ),
            (
                "financial_export",
                "Export financial data",
                "The manager can export financial reports (CSV/Excel) for reporting purposes. "
                "Exported data may contain sensitive revenue and payout information. "
                "All exports are logged. Does not grant access to payment credentials "
                "or the ability to initiate transfers.",
                "view",
            ),
        ],
    },
]

# Flat set of all fine-grained Phase 1023 keys
_FINE_CAPABILITIES: frozenset[str] = frozenset(
    key
    for group in CAPABILITY_GROUPS
    for key, *_ in group["capabilities"]
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
    Phase 1023-C: now includes description and power_type per capability.

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
                        "description": "...",
                        "power_type": "approve",
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
                "key": entry[0],
                "label": entry[1],
                "description": entry[2],
                "power_type": entry[3],
                "granted": current.get(entry[0], False),
            }
            for entry in group["capabilities"]
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
            allowed_keys = {entry[0] for entry in group["capabilities"]}
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

    # Build a label lookup map from the taxonomy
    _label_map: dict[str, str] = {
        entry[0]: entry[1]
        for group in CAPABILITY_GROUPS
        for entry in group["capabilities"]
    }

    written = 0
    for change in changes:
        action = (
            "MANAGER_CAPABILITY_GRANTED"
            if change["new"]
            else "MANAGER_CAPABILITY_REVOKED"
        )
        cap_key = change["capability"]
        payload = {
            "capability": cap_key,
            "capability_label": _label_map.get(cap_key, cap_key),  # Phase 1023-C: human label
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
