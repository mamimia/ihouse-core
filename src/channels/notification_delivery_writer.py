"""
Phase 183 — Notification Delivery Status Writer

Persists every ChannelAttempt from a DispatchResult to the
`notification_delivery_log` table for operational observability.

Usage:
    from channels.notification_delivery_writer import write_delivery_log
    from channels.notification_dispatcher import dispatch_notification

    result = dispatch_notification(db, tenant_id, user_id, message)
    write_delivery_log(
        db=db,
        result=result,
        tenant_id=tenant_id,
        task_id=task_id,
        trigger_reason=reason,
    )

Design:
  - One DB row per ChannelAttempt (not per DispatchResult).
    A single dispatch may fan out to LINE + FCM → two rows.
  - status = "sent"   if ChannelAttempt.success is True.
    status = "failed" if ChannelAttempt.success is False.
  - Best-effort: never raises, never blocks the caller.
  - notification_delivery_id is a UUID v4 generated per row.
  - All rows for the same dispatch share the same dispatched_at timestamp
    (set by the DB default — no explicit value passed).

Invariants:
  - NEVER raises — any DB write failure is logged as WARNING and swallowed.
  - Tenant isolation: tenant_id is always written per-row.
  - If DispatchResult.channels is empty (no active channels), writes 0 rows.
  - DB write errors are logged with WARNING level.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from channels.notification_dispatcher import DispatchResult

logger = logging.getLogger(__name__)


def write_delivery_log(
    *,
    db: Any,
    result: DispatchResult,
    tenant_id: str,
    task_id: Optional[str] = None,
    trigger_reason: Optional[str] = None,
) -> int:
    """
    Write one row per ChannelAttempt in result.channels to notification_delivery_log.

    Args:
        db:             Supabase client (or any object with .table().insert().execute()).
        result:         DispatchResult returned by dispatch_notification().
        tenant_id:      Tenant scope (written to every row for isolation).
        task_id:        Optional. The task that triggered this notification.
        trigger_reason: Optional. Human-readable trigger name (e.g. "ACK_SLA_BREACH").

    Returns:
        Number of rows successfully written. 0 on complete failure.
    """
    if not result.channels:
        return 0

    written: int = 0
    for attempt in result.channels:
        row = {
            "notification_delivery_id": str(uuid.uuid4()),
            "tenant_id":                tenant_id,
            "user_id":                  result.user_id,
            "task_id":                  task_id,
            "trigger_reason":           trigger_reason,
            "channel_type":             attempt.channel_type,
            "channel_id":               attempt.channel_id,
            "status":                   "sent" if attempt.success else "failed",
            "error_message":            attempt.error if not attempt.success else None,
        }
        try:
            db.table("notification_delivery_log").insert(row).execute()
            written += 1
        except Exception as exc:
            logger.warning(
                "notification_delivery_writer: DB insert failed for user=%s "
                "channel=%s tenant=%s: %s",
                result.user_id, attempt.channel_type, tenant_id, exc,
            )

    logger.debug(
        "notification_delivery_writer: wrote %d/%d delivery log rows for user=%s task=%s",
        written, len(result.channels), result.user_id, task_id,
    )
    return written
