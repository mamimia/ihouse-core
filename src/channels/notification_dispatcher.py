"""
Phase 168 — Push Notification Foundation

Notification dispatcher: routes push messages to the correct channel
(LINE, FCM, or email) based on the user's registered notification_channels.

This module is PURE infrastructure — it does not define SLA logic or task
trigger decisions. Those live in sla_engine.py and line_escalation.py.

Architecture:
    dispatch_notification(db, tenant_id, user_id, message) → DispatchResult
        1. Looks up active notification_channels for (tenant_id, user_id).
        2. Attempts delivery via each active channel in priority order:
              line → fcm → email
        3. Returns a DispatchResult summarising which channels were attempted
           and which succeeded.

Channel priority order: LINE > FCM > email
    LINE: wraps channels/line_escalation.py payload building.
          HTTP dispatch is a best-effort stub in tests (injected via LineAdapter).
    FCM:  stub — infrastructure reserved for Phase 168+.
    email: stub — infrastructure reserved for Phase 168+.

Invariants:
    - NEVER raises. All exceptions caught and reported in DispatchResult.
    - Tenant isolation: only channels matching tenant_id are considered.
    - If no active channels found, DispatchResult.sent=False, channels=[].
    - A single failed channel does not abort other channels (fail-isolated).
    - dispatch_notification fallback: if DB lookup fails, returns empty result.

Message format:
    NotificationMessage(
        title: str,
        body: str,
        data: dict   ← arbitrary payload forwarded to FCM/LINE
    )
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Channel type constants
# ---------------------------------------------------------------------------

CHANNEL_LINE  = "line"
CHANNEL_FCM   = "fcm"
CHANNEL_EMAIL = "email"

_ALL_CHANNELS = {CHANNEL_LINE, CHANNEL_FCM, CHANNEL_EMAIL}

# Priority order for multi-channel delivery
_CHANNEL_PRIORITY = [CHANNEL_LINE, CHANNEL_FCM, CHANNEL_EMAIL]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NotificationMessage:
    """
    Uniform notification payload, channel-agnostic.

    Args:
        title: Short headline (used in LINE text and FCM notification title).
        body:  Full message body.
        data:  Arbitrary key/value payload (forwarded to FCM data envelope,
               echoed in LINE text if present).
    """
    title: str
    body:  str
    data:  dict = field(default_factory=dict)


@dataclass
class ChannelAttempt:
    """
    Records a single channel dispatch attempt.

    Args:
        channel_type: 'line' | 'fcm' | 'email'
        channel_id:   The channel token/identifier (LINE user_id, FCM token, email)
        success:      True if deliver was accepted without error.
        error:        Error message on failure, else None.
    """
    channel_type: str
    channel_id: str
    success: bool
    error: Optional[str] = None


@dataclass
class DispatchResult:
    """
    Aggregate result of a dispatch_notification call.

    Args:
        sent:     True if at least one channel accepted the message.
        channels: List of ChannelAttempt for every channel tried.
        user_id:  The target user.
    """
    sent: bool
    user_id: str
    channels: list[ChannelAttempt] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Channel adapters (injectable for testing)
# ---------------------------------------------------------------------------

def _default_line_adapter(channel_id: str, message: NotificationMessage) -> ChannelAttempt:
    """
    Production LINE adapter stub.

    In production this would call the LINE Messaging API (pushMessage).
    Here it builds the payload using line_escalation.format_line_text-style
    logic and returns a success stub so the infrastructure wiring is
    confirmed without requiring live credentials.

    Tests inject a mock adapter via the `adapters` parameter.
    """
    # Build a text payload using the message fields
    text = f"{message.title}\n{message.body}"
    logger.info("LINE dispatch to channel_id=%s text_len=%d", channel_id, len(text))
    # Stub: always succeeds in the absence of a real HTTP client.
    # Production would call httpx.post(LINE_PUSH_URL, json={...}).
    return ChannelAttempt(
        channel_type=CHANNEL_LINE,
        channel_id=channel_id,
        success=True,
    )


def _default_fcm_adapter(channel_id: str, message: NotificationMessage) -> ChannelAttempt:
    """FCM stub — reserved for Phase 168+ wiring."""
    logger.info("FCM dispatch to token=%s (stub)", channel_id)
    return ChannelAttempt(
        channel_type=CHANNEL_FCM,
        channel_id=channel_id,
        success=True,
    )


def _default_email_adapter(channel_id: str, message: NotificationMessage) -> ChannelAttempt:
    """Email stub — reserved for Phase 168+ wiring."""
    logger.info("Email dispatch to=%s (stub)", channel_id)
    return ChannelAttempt(
        channel_type=CHANNEL_EMAIL,
        channel_id=channel_id,
        success=True,
    )


_DEFAULT_ADAPTERS: dict[str, Callable[[str, NotificationMessage], ChannelAttempt]] = {
    CHANNEL_LINE:  _default_line_adapter,
    CHANNEL_FCM:   _default_fcm_adapter,
    CHANNEL_EMAIL: _default_email_adapter,
}


# ---------------------------------------------------------------------------
# Channel lookup
# ---------------------------------------------------------------------------

def _lookup_channels(db: Any, tenant_id: str, user_id: str) -> list[dict]:
    """
    Fetch all active notification_channels rows for (tenant_id, user_id).

    Returns empty list on any error (best-effort).
    """
    try:
        result = (
            db.table("notification_channels")
            .select("channel_type, channel_id")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .eq("active", True)
            .execute()
        )
        return result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("notification_channels lookup failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Register / deregister helpers (used by a future channels router)
# ---------------------------------------------------------------------------

def register_channel(
    db: Any,
    tenant_id: str,
    user_id: str,
    channel_type: str,
    channel_id: str,
) -> dict:
    """
    Upsert a notification channel for the user.

    On conflict (tenant_id, user_id, channel_type): updates channel_id and
    sets active=True.

    Returns the upserted row summary dict.
    Raises ValueError on invalid channel_type.
    """
    if channel_type not in _ALL_CHANNELS:
        raise ValueError(
            f"Invalid channel_type '{channel_type}'. "
            f"Must be one of: {', '.join(sorted(_ALL_CHANNELS))}"
        )

    row = {
        "tenant_id":    tenant_id,
        "user_id":      user_id,
        "channel_type": channel_type,
        "channel_id":   channel_id,
        "active":       True,
    }
    db.table("notification_channels") \
        .upsert(row, on_conflict="tenant_id,user_id,channel_type") \
        .execute()

    return {
        "status":       "registered",
        "tenant_id":    tenant_id,
        "user_id":      user_id,
        "channel_type": channel_type,
        "channel_id":   channel_id,
    }


def deregister_channel(
    db: Any,
    tenant_id: str,
    user_id: str,
    channel_type: str,
) -> dict:
    """
    Set active=False for the user's channel of the given type.

    Idempotent: if no row exists, returns status='not_found'.
    """
    if channel_type not in _ALL_CHANNELS:
        raise ValueError(
            f"Invalid channel_type '{channel_type}'. "
            f"Must be one of: {', '.join(sorted(_ALL_CHANNELS))}"
        )
    db.table("notification_channels") \
        .update({"active": False}) \
        .eq("tenant_id", tenant_id) \
        .eq("user_id", user_id) \
        .eq("channel_type", channel_type) \
        .execute()
    return {
        "status":       "deregistered",
        "tenant_id":    tenant_id,
        "user_id":      user_id,
        "channel_type": channel_type,
    }


# ---------------------------------------------------------------------------
# Core dispatcher
# ---------------------------------------------------------------------------

def dispatch_notification(
    db: Any,
    tenant_id: str,
    user_id: str,
    message: NotificationMessage,
    adapters: Optional[dict[str, Callable[[str, NotificationMessage], ChannelAttempt]]] = None,
) -> DispatchResult:
    """
    Dispatch a notification to all active channels for the user.

    Channels are tried in priority order: LINE → FCM → email.
    A failure on one channel does not abort others (fail-isolated).

    Args:
        db:        Supabase client.
        tenant_id: Tenant scope.
        user_id:   Target user.
        message:   NotificationMessage to deliver.
        adapters:  Optional dict of channel_type → adapter callable.
                   Defaults to _DEFAULT_ADAPTERS. Injectable for testing.

    Returns:
        DispatchResult: sent=True if at least one channel succeeded.
    """
    effective_adapters = adapters if adapters is not None else _DEFAULT_ADAPTERS

    channels = _lookup_channels(db, tenant_id, user_id)
    if not channels:
        logger.info(
            "dispatch_notification: no active channels for tenant=%s user=%s",
            tenant_id, user_id,
        )
        return DispatchResult(sent=False, user_id=user_id, channels=[])

    # Build a map of {channel_type: channel_id} from the DB rows
    channel_map: dict[str, str] = {
        row["channel_type"]: row["channel_id"]
        for row in channels
        if row.get("channel_type") in _ALL_CHANNELS
    }

    attempts: list[ChannelAttempt] = []

    # Dispatch in priority order
    for ch_type in _CHANNEL_PRIORITY:
        ch_id = channel_map.get(ch_type)
        if ch_id is None:
            continue  # user has no channel of this type

        adapter = effective_adapters.get(ch_type)
        if adapter is None:
            logger.warning("No adapter registered for channel_type=%s", ch_type)
            attempts.append(ChannelAttempt(
                channel_type=ch_type,
                channel_id=ch_id,
                success=False,
                error="No adapter registered",
            ))
            continue

        try:
            attempt = adapter(ch_id, message)
            attempts.append(attempt)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Channel adapter %s raised for user=%s: %s", ch_type, user_id, exc
            )
            attempts.append(ChannelAttempt(
                channel_type=ch_type,
                channel_id=ch_id,
                success=False,
                error=str(exc),
            ))

    sent = any(a.success for a in attempts)
    return DispatchResult(sent=sent, user_id=user_id, channels=attempts)
