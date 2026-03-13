"""
Phase 500 — Webhook Retry Mechanism

Provides automatic retry for failed webhook deliveries.
Failed webhooks go to a retry queue with exponential backoff.
Max retries: 5 (delays: 30s, 2m, 8m, 30m, 2h).

Works with the DLQ (Dead Letter Queue) — after max retries,
moves to DLQ for manual inspection.
"""
from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ihouse.webhook_retry")

MAX_RETRIES = 5
BASE_DELAY_SECONDS = 30  # 30s → 2m → 8m → 30m → 2h


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _calculate_delay(attempt: int) -> int:
    """Exponential backoff: base_delay * 4^attempt."""
    return BASE_DELAY_SECONDS * (4 ** min(attempt, MAX_RETRIES - 1))


def enqueue_retry(
    db: Any,
    tenant_id: str,
    webhook_url: str,
    payload: Dict[str, Any],
    event_type: str,
    attempt: int = 0,
    error_message: str = "",
) -> Dict[str, Any]:
    """
    Enqueue a failed webhook for retry.

    If max retries exceeded, moves to DLQ.

    Returns:
        Result dict.
    """
    if attempt >= MAX_RETRIES:
        # Move to DLQ
        try:
            db.table("webhook_dlq").insert({
                "tenant_id": tenant_id,
                "webhook_url": webhook_url,
                "payload_json": payload,
                "event_type": event_type,
                "attempts": attempt,
                "last_error": error_message,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
            return {"status": "moved_to_dlq", "attempts": attempt}
        except Exception as exc:
            logger.warning("webhook_dlq insert failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    delay_seconds = _calculate_delay(attempt)
    next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)

    try:
        db.table("webhook_retry_queue").insert({
            "tenant_id": tenant_id,
            "webhook_url": webhook_url,
            "payload_json": payload,
            "event_type": event_type,
            "attempt": attempt + 1,
            "next_attempt_at": next_attempt_at.isoformat(),
            "last_error": error_message,
        }).execute()
        return {
            "status": "queued",
            "attempt": attempt + 1,
            "next_attempt_at": next_attempt_at.isoformat(),
            "delay_seconds": delay_seconds,
        }
    except Exception as exc:
        logger.warning("webhook_retry_queue insert failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def process_retry_queue(
    *,
    dry_run: bool = False,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Process pending webhook retries.

    Picks up items from webhook_retry_queue where next_attempt_at <= now,
    dispatches them, and handles success/failure.
    """
    import requests

    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()

    try:
        result = (
            db.table("webhook_retry_queue")
            .select("*")
            .lte("next_attempt_at", now)
            .limit(limit)
            .execute()
        )
        pending = result.data or []
    except Exception as exc:
        return {"status": "error", "error": str(exc)}

    stats = {
        "total_pending": len(pending),
        "succeeded": 0,
        "failed": 0,
        "re_queued": 0,
        "moved_to_dlq": 0,
        "dry_run": dry_run,
    }

    for item in pending:
        if dry_run:
            stats["re_queued"] += 1
            continue

        try:
            response = requests.post(
                item["webhook_url"],
                json=item["payload_json"],
                timeout=10,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code < 400:
                stats["succeeded"] += 1
                # Remove from retry queue
                try:
                    db.table("webhook_retry_queue").delete().eq("id", item["id"]).execute()
                except Exception:
                    pass
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")

        except Exception as exc:
            retry_result = enqueue_retry(
                db=db,
                tenant_id=item.get("tenant_id", ""),
                webhook_url=item["webhook_url"],
                payload=item["payload_json"],
                event_type=item.get("event_type", ""),
                attempt=item.get("attempt", 0),
                error_message=str(exc)[:500],
            )

            if retry_result.get("status") == "moved_to_dlq":
                stats["moved_to_dlq"] += 1
            else:
                stats["re_queued"] += 1
                stats["failed"] += 1

            # Remove original from queue
            try:
                db.table("webhook_retry_queue").delete().eq("id", item["id"]).execute()
            except Exception:
                pass

    return stats
