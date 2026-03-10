"""
Phase 177 — SLA→Dispatcher Bridge

Connects the output of sla_engine.evaluate() (EscalationResult.actions)
to notification_dispatcher.dispatch_notification().

Architecture:
    dispatch_escalations(db, tenant_id, actions, adapters=None)
        For each EscalationAction:
          1. Resolve target users from tenant_permissions
             (target="ops"   → role IN ('worker', 'manager'))
             (target="admin" → role = 'admin')
          2. Build a NotificationMessage from the action fields
          3. Call dispatch_notification for each resolved user
        Returns list[BridgeResult] — one per action.

Invariants:
    - sla_engine.py is NOT modified (remains pure/no-side-effects).
    - notification_dispatcher.py is NOT modified.
    - Best-effort: all exceptions swallowed, never raises.
    - Tenant isolation: only tenant_permissions rows for tenant_id are used.
    - A failed dispatch for one user does not block other users.
    - If actions list is empty → returns [] immediately.
    - If no users resolved for a target → BridgeResult.dispatched_to=[], results=[].
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from channels.notification_dispatcher import (
    ChannelAttempt,
    DispatchResult,
    NotificationMessage,
    dispatch_notification,
)
from channels.notification_delivery_writer import write_delivery_log  # Phase 183
from tasks.sla_engine import EscalationAction

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Target role mapping
# ---------------------------------------------------------------------------

_OPS_ROLES   = {"worker", "manager"}
_ADMIN_ROLES = {"admin"}


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

@dataclass
class BridgeResult:
    """Result of dispatching one EscalationAction to all resolved users."""
    action_type: str           # "notify_ops" | "notify_admin"
    reason: str                # trigger name, e.g. "ACK_SLA_BREACH"
    task_id: str
    dispatched_to: List[str]   # user_ids attempted
    results: List[DispatchResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_users(db: Any, tenant_id: str, target: str) -> List[str]:
    """
    Fetch user_ids from tenant_permissions whose role matches the target.

    target="ops"   → role IN ('worker', 'manager')
    target="admin" → role = 'admin'

    Returns [] on any DB error (best-effort).
    """
    if target == "ops":
        roles = list(_OPS_ROLES)
    elif target == "admin":
        roles = list(_ADMIN_ROLES)
    else:
        logger.warning("sla_dispatch_bridge: unknown target='%s'", target)
        return []

    try:
        result = (
            db.table("tenant_permissions")
            .select("user_id")
            .eq("tenant_id", tenant_id)
            .in_("role", roles)
            .execute()
        )
        return [row["user_id"] for row in (result.data or []) if row.get("user_id")]
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "sla_dispatch_bridge: tenant_permissions lookup failed for target=%s: %s",
            target, exc,
        )
        return []


def _build_message(action: EscalationAction) -> NotificationMessage:
    """Build a NotificationMessage from an EscalationAction."""
    return NotificationMessage(
        title=f"[{action.reason}] Task {action.task_id}",
        body=(
            f"Property: {action.property_id} — "
            f"SLA breach: {action.reason}"
        ),
        data={
            "task_id":     action.task_id,
            "property_id": action.property_id,
            "reason":      action.reason,
            "request_id":  action.request_id,
        },
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def dispatch_escalations(
    db: Any,
    tenant_id: str,
    actions: List[EscalationAction],
    adapters: Optional[
        dict[str, Callable[[str, NotificationMessage], ChannelAttempt]]
    ] = None,
) -> List[BridgeResult]:
    """
    Dispatch all EscalationActions to their resolved target users.

    For each action:
      1. Resolves user_ids via tenant_permissions (role-based).
      2. Builds a NotificationMessage.
      3. Calls dispatch_notification for each user (fail-isolated).
      4. Returns a BridgeResult summarising what was dispatched.

    Args:
        db:        Supabase client (or mock for testing).
        tenant_id: Tenant scope.
        actions:   List of EscalationAction from sla_engine.evaluate().
        adapters:  Optional channel adapters — forwarded to dispatch_notification
                   for dependency injection in tests.

    Returns:
        List[BridgeResult], one entry per action.
        Empty list if actions is empty.

    Never raises.
    """
    if not actions:
        return []

    bridge_results: List[BridgeResult] = []

    for action in actions:
        user_ids: List[str] = []
        dispatch_results: List[DispatchResult] = []

        try:
            message = _build_message(action)
            user_ids = _resolve_users(db, tenant_id, action.target)

            for user_id in user_ids:
                try:
                    result = dispatch_notification(
                        db=db,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        message=message,
                        adapters=adapters,
                    )
                    dispatch_results.append(result)
                    # Phase 183: persist delivery status (best-effort)
                    try:
                        write_delivery_log(
                            db=db,
                            result=result,
                            tenant_id=tenant_id,
                            task_id=action.task_id,
                            trigger_reason=action.reason,
                        )
                    except Exception:  # noqa: BLE001
                        pass  # log write failure must never block dispatch
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "sla_dispatch_bridge: dispatch failed for user=%s action=%s: %s",
                        user_id, action.action_type, exc,
                    )
                    dispatch_results.append(
                        DispatchResult(sent=False, user_id=user_id, channels=[])
                    )

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "sla_dispatch_bridge: unexpected error for action=%s: %s",
                action.action_type, exc,
            )

        bridge_results.append(BridgeResult(
            action_type=action.action_type,
            reason=action.reason,
            task_id=action.task_id,
            dispatched_to=user_ids,
            results=dispatch_results,
        ))

    return bridge_results
