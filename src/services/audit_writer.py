"""
Phase 189 — Audit Event Writer

Best-effort, non-blocking writer for audit_events table.
Pattern mirrors dead_letter.py: every exception is caught, logged to stderr,
and silently swallowed. The caller's request path is never affected.

Usage:
    from services.audit_writer import write_audit_event
    write_audit_event(
        tenant_id="t1", actor_id="user_abc",
        action="TASK_ACKNOWLEDGED",
        entity_type="task", entity_id="task-id-001",
        payload={"from_status": "PENDING", "to_status": "ACKNOWLEDGED"},
        client=db,          # optional — uses env vars if None
    )
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def write_audit_event(
    tenant_id: str,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: Optional[Dict[str, Any]] = None,
    client: Optional[Any] = None,
) -> None:
    """
    Insert a single row into audit_events.

    This is best-effort — any exception is caught and logged but never
    re-raised. The caller's normal response flow is always preserved.

    Args:
        tenant_id:    JWT sub-derived tenant identifier.
        actor_id:     JWT sub of the acting user (same as tenant_id for now;
                      Phase 190 will wire a proper user_id claim).
        action:       Action name, e.g. "TASK_ACKNOWLEDGED", "BOOKING_FLAGS_UPDATED".
        entity_type:  "task" | "booking" (for index routing).
        entity_id:    task_id or booking_id — unique identifier of the mutated entity.
        payload:      Optional dict with contextual snapshot (old/new state, etc.).
        client:       Optional Supabase client (injected in tests; created from env if None).
    """
    try:
        db = client if client is not None else _get_supabase_client()
        db.table("audit_events").insert({
            "tenant_id":   tenant_id,
            "actor_id":    actor_id,
            "action":      action,
            "entity_type": entity_type,
            "entity_id":   entity_id,
            "payload":     payload or {},
        }).execute()
    except Exception as exc:  # noqa: BLE001
        print(
            f"[audit_writer] WARN: failed to write audit event "
            f"(action={action!r} entity={entity_type}/{entity_id!r}): {exc}",
            file=sys.stderr,
        )
        logger.warning(
            "audit_writer: failed to write audit event action=%s entity=%s/%s: %s",
            action, entity_type, entity_id, exc,
        )
