"""
Phase 503 — Notification Preference Center

Manages per-user notification preferences and channel settings.
Users can opt-in/out per notification type and set quiet hours.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ihouse.notification_prefs")


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


# Available notification types
NOTIFICATION_TYPES = [
    "booking_created",
    "booking_canceled",
    "booking_amended",
    "task_assigned",
    "task_escalated",
    "guest_feedback",
    "financial_report",
    "conflict_alert",
    "pre_arrival",
    "system_alert",
]


def get_preferences(
    db: Any,
    tenant_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """
    Get notification preferences for a user.

    Returns current settings or defaults if none exist.
    """
    try:
        result = (
            db.table("notification_preferences")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .execute()
        )
        prefs = result.data or []
    except Exception as exc:
        logger.warning("get_preferences failed: %s", exc)
        prefs = []

    if prefs:
        return prefs[0]

    # Return defaults
    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "enabled_types": NOTIFICATION_TYPES,  # all enabled by default
        "quiet_hours_start": None,
        "quiet_hours_end": None,
        "preferred_channel": "email",
    }


def update_preferences(
    db: Any,
    tenant_id: str,
    user_id: str,
    enabled_types: Optional[List[str]] = None,
    quiet_hours_start: Optional[str] = None,
    quiet_hours_end: Optional[str] = None,
    preferred_channel: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update notification preferences for a user.
    """
    row: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if enabled_types is not None:
        # Validate types
        invalid = [t for t in enabled_types if t not in NOTIFICATION_TYPES]
        if invalid:
            return {"error": f"Invalid notification types: {invalid}"}
        row["enabled_types"] = enabled_types

    if quiet_hours_start is not None:
        row["quiet_hours_start"] = quiet_hours_start
    if quiet_hours_end is not None:
        row["quiet_hours_end"] = quiet_hours_end
    if preferred_channel is not None:
        if preferred_channel not in ("email", "sms", "whatsapp", "line"):
            return {"error": f"Invalid channel: {preferred_channel}"}
        row["preferred_channel"] = preferred_channel

    try:
        result = db.table("notification_preferences").upsert(
            row,
            on_conflict="tenant_id,user_id",
        ).execute()
        return result.data[0] if result.data else row
    except Exception as exc:
        logger.warning("update_preferences failed: %s", exc)
        return {"error": str(exc)}


def should_notify(
    db: Any,
    tenant_id: str,
    user_id: str,
    notification_type: str,
) -> bool:
    """
    Check if a user should receive a specific notification type.
    Considers enabled_types and quiet hours.
    """
    prefs = get_preferences(db, tenant_id, user_id)

    enabled = prefs.get("enabled_types", NOTIFICATION_TYPES)
    if notification_type not in enabled:
        return False

    # Check quiet hours
    quiet_start = prefs.get("quiet_hours_start")
    quiet_end = prefs.get("quiet_hours_end")
    if quiet_start and quiet_end:
        now_time = datetime.now(timezone.utc).strftime("%H:%M")
        if quiet_start <= now_time <= quiet_end:
            return False

    return True
