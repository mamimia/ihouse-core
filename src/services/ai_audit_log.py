"""
Phase 230 — AI Audit Log

Best-effort, non-blocking writer for the ai_audit_log table.

Every AI copilot endpoint calls log_ai_interaction() at the end of its
response path. A logging failure NEVER affects the caller — all exceptions
are caught and written to stderr (same pattern as audit_writer.py).

Usage:
    from services.ai_audit_log import log_ai_interaction
    log_ai_interaction(
        tenant_id="t1",
        endpoint="POST /ai/copilot/morning-briefing",
        request_type="morning_briefing",
        input_summary="language=en",
        output_summary="generated_by=heuristic, action_items=2",
        generated_by="heuristic",
        client=db,        # optional — created from env if None
    )
"""
from __future__ import annotations

import os
import sys
from typing import Any, Optional


def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def log_ai_interaction(
    tenant_id: str,
    endpoint: str,
    request_type: str,
    input_summary: str = "",
    output_summary: str = "",
    generated_by: str = "heuristic",
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    language: Optional[str] = None,
    client: Optional[Any] = None,
) -> None:
    """
    Insert a single row into ai_audit_log.

    Best-effort — any exception is caught and logged to stderr but never
    re-raised. The caller's response path is always preserved.

    Args:
        tenant_id:      JWT sub-derived tenant identifier.
        endpoint:       Full endpoint path, e.g. 'POST /ai/copilot/morning-briefing'.
        request_type:   Short slug, e.g. 'morning_briefing', 'task_recommendations'.
        input_summary:  Human-readable summary of request params (no PII).
        output_summary: Human-readable summary of what was returned.
        generated_by:   'llm' | 'heuristic'.
        entity_type:    Optional: 'booking', 'task', 'property'.
        entity_id:      Optional: ID of the primary entity involved.
        language:       Optional: language code if applicable.
        client:         Optional Supabase client (injected in tests).
    """
    try:
        db = client if client is not None else _get_supabase_client()
        row: dict[str, Any] = {
            "tenant_id":      tenant_id,
            "endpoint":       endpoint,
            "request_type":   request_type,
            "input_summary":  input_summary[:500],   # cap to avoid large payloads
            "output_summary": output_summary[:500],
            "generated_by":   generated_by,
        }
        if entity_type is not None:
            row["entity_type"] = entity_type
        if entity_id is not None:
            row["entity_id"] = entity_id
        if language is not None:
            row["language"] = language
        db.table("ai_audit_log").insert(row).execute()
    except Exception as exc:  # noqa: BLE001
        print(
            f"[ai_audit_log] WARN: failed to write audit log "
            f"(endpoint={endpoint!r} tenant={tenant_id!r}): {exc}",
            file=sys.stderr,
        )
