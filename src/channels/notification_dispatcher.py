"""
Phase 168 — Push Notification Foundation
Phase 196 — Per-Worker Channel Architecture (patch)

Notification dispatcher: routes push messages to the correct channel
(LINE, WhatsApp, Telegram, FCM, email, or SMS) based on the user's
registered notification_channels.

This module is PURE infrastructure — it does not define SLA logic or task
trigger decisions. Those live in sla_engine.py and line_escalation.py.

Architecture:
    dispatch_notification(db, tenant_id, user_id, message) → DispatchResult
        1. Looks up active notification_channels for (tenant_id, user_id).
        2. Attempts delivery via each registered channel in order.
        3. Returns a DispatchResult summarising which channels were attempted
           and which succeeded.

Per-worker channel preference:
    Each worker has their own channel registered in notification_channels.
    Worker A → channel_type="line"      → LINE only
    Worker B → channel_type="whatsapp"  → WhatsApp only
    Worker C → channel_type="telegram"  → Telegram only (future)
    Worker D → channel_type="sms"       → SMS only (tier-2 escalation)
    No global fallback chain — each worker gets their preferred channel.

Escalation tiers (SLA engine responsibility, not this module):
    Tier 1 — in-app (always first)
    Tier 2 — preferred external channel (line / whatsapp / telegram)
    Tier 3 — SMS or email (higher SLA threshold, future phases)

Invariants:
    - NEVER raises. All exceptions caught and reported in DispatchResult.
    - Tenant isolation: only channels matching tenant_id are considered.
    - If no active channels found, DispatchResult.sent=False, channels=[].
    - A single failed channel does not abort other channels (fail-isolated).
    - dispatch_notification fallback: if DB lookup fails, returns empty result.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Channel type constants
# ---------------------------------------------------------------------------

# Tier 1 — Preferred external channels (per-worker, registered at onboarding)
CHANNEL_LINE     = "line"       # LINE Messaging API — dominant in Thailand/JP
CHANNEL_WHATSAPP = "whatsapp"   # WhatsApp Cloud API — dominant in SEA/EU markets
CHANNEL_TELEGRAM = "telegram"   # Telegram Bot API — future phase

# Tier 1 — App/device push
CHANNEL_FCM   = "fcm"           # Firebase Cloud Messaging
CHANNEL_EMAIL = "email"         # Email — low-latency fallback

# Tier 2 — High-threshold escalation (SMS requires longer unresponsive window)
CHANNEL_SMS = "sms"             # Direct SMS — future phase, last-resort escalation

_ALL_CHANNELS = {
    CHANNEL_LINE, CHANNEL_WHATSAPP, CHANNEL_TELEGRAM,
    CHANNEL_FCM, CHANNEL_EMAIL, CHANNEL_SMS,
}

# Default dispatch order when a user has multiple channels registered.
# The SLA engine decides WHICH tier to invoke — this is just the ordering
# within a dispatch call for a given user.
_CHANNEL_PRIORITY = [
    CHANNEL_LINE, CHANNEL_WHATSAPP, CHANNEL_TELEGRAM,  # preferred external
    CHANNEL_FCM, CHANNEL_EMAIL,                         # app / email
    CHANNEL_SMS,                                        # tier-2 last-resort
]


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
        channel_type: 'line' | 'whatsapp' | 'telegram' | 'fcm' | 'email' | 'sms'
        channel_id:   The channel token/identifier (LINE user_id, WhatsApp number, etc.)
        success:      True if delivery was accepted without error.
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


def _default_whatsapp_adapter(channel_id: str, message: NotificationMessage) -> ChannelAttempt:
    """
    WhatsApp Cloud API adapter stub (Phase 196).

    In production: HTTP POST to graph.facebook.com/v19.0/{phone_number_id}/messages
    with Authorization: Bearer {IHOUSE_WHATSAPP_TOKEN}.
    Stub returns success=True; tests inject mocks via `adapters` parameter.
    """
    text = f"{message.title}\n{message.body}"
    logger.info("WhatsApp dispatch to number=%s text_len=%d", channel_id, len(text))
    return ChannelAttempt(
        channel_type=CHANNEL_WHATSAPP,
        channel_id=channel_id,
        success=True,
    )


def _default_telegram_adapter(channel_id: str, message: NotificationMessage) -> ChannelAttempt:
    """
    Telegram Bot API adapter stub (future phase).

    In production: POST to api.telegram.org/bot{TOKEN}/sendMessage.
    Stub — infrastructure reserved for when Telegram support is wired.
    """
    logger.info("Telegram dispatch to chat_id=%s (stub)", channel_id)
    return ChannelAttempt(
        channel_type=CHANNEL_TELEGRAM,
        channel_id=channel_id,
        success=True,
    )


def _default_sms_adapter(channel_id: str, message: NotificationMessage) -> ChannelAttempt:
    """
    SMS adapter stub — tier-2 last-resort escalation (future phase).

    In production: Twilio / AWS SNS. Only triggered after longer unresponsive
    window than tier-1 channels. Stub reserved for future SLA tier wiring.
    """
    logger.info("SMS dispatch to number=%s (stub)", channel_id)
    return ChannelAttempt(
        channel_type=CHANNEL_SMS,
        channel_id=channel_id,
        success=True,
    )


_DEFAULT_ADAPTERS: dict[str, Callable[[str, NotificationMessage], ChannelAttempt]] = {
    CHANNEL_LINE:     _default_line_adapter,
    CHANNEL_WHATSAPP: _default_whatsapp_adapter,
    CHANNEL_TELEGRAM: _default_telegram_adapter,
    CHANNEL_FCM:      _default_fcm_adapter,
    CHANNEL_EMAIL:    _default_email_adapter,
    CHANNEL_SMS:      _default_sms_adapter,
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
    Dispatch a notification to all active channels registered for the user.

    Each worker has their own preferred channel registered in notification_channels.
    This function dispatches to whatever that user has registered — no global
    fallback chain. Worker A gets LINE, Worker B gets WhatsApp, Worker C gets
    Telegram, based solely on what is in notification_channels for their user_id.

    Channels are tried in priority order if the user has multiple registered.
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
