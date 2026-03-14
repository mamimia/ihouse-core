"""
Phase 774 — System Status Aggregator
======================================

GET /admin/system-status

Single monitoring endpoint that aggregates all health checks:
  - /health (core)
  - /readiness (DB connectivity)
  - Storage bucket status
  - Notification channel status
  - Environment configuration

Returns a unified system status for external monitoring tools
(UptimeRobot, Datadog, etc.) to poll.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_db() -> Any:
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)


def _check_db() -> dict:
    """Quick DB connectivity check."""
    db = _get_db()
    if not db:
        return {"status": "unconfigured", "latency_ms": None}
    try:
        import time
        start = time.monotonic()
        db.table("organizations").select("id").limit(1).execute()
        latency = round((time.monotonic() - start) * 1000)
        return {"status": "ok", "latency_ms": latency}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "latency_ms": None}


def _check_storage() -> dict:
    """Check storage buckets exist."""
    db = _get_db()
    if not db:
        return {"status": "unconfigured", "bucket_count": 0}
    try:
        buckets = db.storage.list_buckets()
        return {"status": "ok", "bucket_count": len(buckets)}
    except Exception as exc:
        return {"status": "error", "error": str(exc), "bucket_count": 0}


def _check_env() -> dict:
    """Check critical env vars."""
    critical_vars = [
        "SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY",
        "IHOUSE_JWT_SECRET",
    ]
    missing = [v for v in critical_vars if not os.environ.get(v)]
    is_dev = os.environ.get("IHOUSE_DEV_MODE", "").lower() == "true"

    return {
        "status": "ok" if (not missing or is_dev) else "critical",
        "env": os.environ.get("IHOUSE_ENV", "development"),
        "dev_mode": is_dev,
        "missing_critical": missing,
    }


def _check_notifications() -> dict:
    """Count configured notification channels."""
    channels = {
        "line": bool(os.environ.get("IHOUSE_LINE_CHANNEL_TOKEN")),
        "telegram": bool(os.environ.get("IHOUSE_TELEGRAM_BOT_TOKEN")),
        "whatsapp": bool(os.environ.get("IHOUSE_WHATSAPP_TOKEN")),
        "sms": bool(os.environ.get("IHOUSE_TWILIO_SID") and os.environ.get("IHOUSE_TWILIO_TOKEN")),
        "email": bool(os.environ.get("IHOUSE_SENDGRID_KEY")),
    }
    configured = sum(1 for v in channels.values() if v)
    return {"configured": configured, "total": len(channels), "channels": channels}


@router.get(
    "/admin/system-status",
    tags=["admin", "ops", "monitoring"],
    summary="Unified system status (Phase 774)",
    description=(
        "Aggregates all health checks into one endpoint for external monitoring. "
        "Returns database, storage, notifications, and environment status."
    ),
    responses={
        200: {"description": "System status report"},
    },
)
async def system_status() -> JSONResponse:
    ts = datetime.now(tz=timezone.utc).isoformat()

    db_status = _check_db()
    storage_status = _check_storage()
    env_status = _check_env()
    notif_status = _check_notifications()

    # Overall health
    components = [db_status["status"], storage_status["status"], env_status["status"]]
    if all(s == "ok" for s in components):
        overall = "healthy"
    elif any(s == "critical" or s == "error" for s in components):
        overall = "degraded"
    else:
        overall = "partial"

    return JSONResponse(status_code=200, content={
        "status": overall,
        "timestamp": ts,
        "version": os.environ.get("BUILD_VERSION", "dev"),
        "components": {
            "database": db_status,
            "storage": storage_status,
            "environment": env_status,
            "notifications": notif_status,
        },
    })
