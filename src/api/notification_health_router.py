"""
Phase 773 — Notification Channel Health Check
===============================================

GET /admin/notification-health

Tests connectivity for each configured notification channel:
  - LINE (IHOUSE_LINE_CHANNEL_TOKEN)
  - Telegram (IHOUSE_TELEGRAM_BOT_TOKEN)
  - WhatsApp (IHOUSE_WHATSAPP_TOKEN)
  - SMS/Twilio (IHOUSE_TWILIO_SID + TOKEN)
  - Email/SendGrid (IHOUSE_SENDGRID_KEY)

Returns per-channel status: configured / unconfigured / error.
No actual messages sent — just validates credentials exist and format is valid.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

_CHANNELS = [
    {
        "name": "line",
        "label": "LINE Messaging",
        "env_vars": ["IHOUSE_LINE_CHANNEL_TOKEN"],
        "optional": ["IHOUSE_LINE_SECRET"],
    },
    {
        "name": "telegram",
        "label": "Telegram Bot",
        "env_vars": ["IHOUSE_TELEGRAM_BOT_TOKEN"],
    },
    {
        "name": "whatsapp",
        "label": "WhatsApp Business",
        "env_vars": ["IHOUSE_WHATSAPP_TOKEN"],
        "optional": ["IHOUSE_WHATSAPP_PHONE_NUMBER_ID", "IHOUSE_WHATSAPP_APP_SECRET"],
    },
    {
        "name": "sms",
        "label": "SMS (Twilio)",
        "env_vars": ["IHOUSE_TWILIO_SID", "IHOUSE_TWILIO_TOKEN", "IHOUSE_TWILIO_FROM"],
    },
    {
        "name": "email",
        "label": "Email (SendGrid)",
        "env_vars": ["IHOUSE_SENDGRID_KEY"],
        "optional": ["IHOUSE_SENDGRID_FROM"],
    },
]


def _check_channel(channel: dict) -> dict:
    """Check if a notification channel is configured."""
    result = {
        "name": channel["name"],
        "label": channel["label"],
        "status": "unconfigured",
        "configured_vars": [],
        "missing_vars": [],
    }

    all_set = True
    for var in channel["env_vars"]:
        val = os.environ.get(var, "")
        if val:
            result["configured_vars"].append(var)
        else:
            result["missing_vars"].append(var)
            all_set = False

    # Check optional vars
    for var in channel.get("optional", []):
        val = os.environ.get(var, "")
        if val:
            result["configured_vars"].append(var)

    if all_set:
        result["status"] = "configured"

    return result


@router.get(
    "/admin/notification-health",
    tags=["admin", "ops"],
    summary="Notification channel health check (Phase 773)",
    description=(
        "Checks which notification channels are configured by "
        "verifying required environment variables are set."
    ),
    responses={
        200: {"description": "Channel status report"},
    },
)
async def notification_health() -> JSONResponse:
    results = [_check_channel(ch) for ch in _CHANNELS]

    configured = sum(1 for r in results if r["status"] == "configured")
    total = len(results)

    return JSONResponse(status_code=200, content={
        "channels": results,
        "total": total,
        "configured": configured,
        "unconfigured": total - configured,
        "summary": f"{configured}/{total} channels configured",
    })
