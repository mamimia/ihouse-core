"""
Phase 144 — Outbound Sync Log Writer

Best-effort, append-only persistence of every ExecutionResult into the
`outbound_sync_log` Supabase table.

Design principles:
  - Never raises — any Supabase error is logged as WARNING and swallowed.
  - Best-effort only; outbound sync success/failure is NOT blocked by DB writes.
  - Append-only — this module only inserts, never updates.
  - Disabled when IHOUSE_SYNC_LOG_DISABLED=true (test opt-out without Supabase).
  - Accepts optional `client` parameter for testability (same pattern as task_writer.py).

Called by: services/outbound_executor.py after every action result.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_supabase_client() -> Any:
    """Lazy import of the Supabase client — avoids import-time errors if creds absent."""
    from core.supabase_state_store import SyncPostgrestClient
    return SyncPostgrestClient()


def write_sync_result(
    *,
    booking_id:  str,
    tenant_id:   str,
    provider:    str,
    external_id: str,
    strategy:    str,
    status:      str,
    http_status: Optional[int],
    message:     str,
    client:      Any = None,
) -> bool:
    """
    Persist one ExecutionResult row to ``outbound_sync_log``.

    Returns True on success, False on any error (best-effort).

    Disabled when ``IHOUSE_SYNC_LOG_DISABLED=true``.

    Parameters
    ----------
    booking_id  : str
    tenant_id   : str
    provider    : str
    external_id : str
    strategy    : str — 'api_first' | 'ical_fallback' | 'skip'
    status      : str — 'ok' | 'failed' | 'dry_run' | 'skipped'
    http_status : int | None
    message     : str
    client      : optional Supabase client for testing (avoids real network calls)
    """
    if os.environ.get("IHOUSE_SYNC_LOG_DISABLED", "false").lower() == "true":
        logger.debug(
            "sync_log_writer: disabled via IHOUSE_SYNC_LOG_DISABLED — skipping write "
            "(booking_id=%s provider=%s status=%s)",
            booking_id, provider, status,
        )
        return True  # treat as success in test/staging mode

    try:
        db = client or _get_supabase_client()

        row = {
            "booking_id":  booking_id,
            "tenant_id":   tenant_id,
            "provider":    provider,
            "external_id": external_id,
            "strategy":    strategy,
            "status":      status,
            "http_status": http_status,
            "message":     (message or "")[:2000],  # guard oversized messages
        }

        resp = db.table("outbound_sync_log").insert(row).execute()

        # Supabase client raises on PGRST errors, but guard defensively
        if hasattr(resp, "error") and resp.error:
            logger.warning(
                "sync_log_writer Supabase error: booking_id=%s provider=%s: %s",
                booking_id, provider, resp.error,
            )
            return False

        logger.debug(
            "sync_log_writer: written booking_id=%s provider=%s status=%s",
            booking_id, provider, status,
        )
        return True

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "sync_log_writer exception (best-effort, swallowed): "
            "booking_id=%s provider=%s: %s",
            booking_id, provider, exc,
        )
        return False
