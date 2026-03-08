from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment,misc]

try:
    from postgrest.exceptions import APIError
except ImportError:  # pragma: no cover
    APIError = Exception  # type: ignore[assignment,misc]

# Skill dispatch table — maps event_type to the corresponding skill run function
_SKILL_REGISTRY: Dict[str, Any] = {}


def _get_skill_registry() -> Dict[str, Any]:
    """Lazy-load skill registry to avoid import cycles at module level."""
    if not _SKILL_REGISTRY:
        from core.skills.booking_created.skill import run as booking_created_run
        from core.skills.booking_canceled.skill import run as booking_canceled_run
        _SKILL_REGISTRY["BOOKING_CREATED"] = booking_created_run
        _SKILL_REGISTRY["BOOKING_CANCELED"] = booking_canceled_run
    return _SKILL_REGISTRY


# Statuses that indicate a previous replay was already successful
_ALREADY_APPLIED_STATUSES = frozenset({
    "APPLIED",
    "ALREADY_APPLIED",
    "ALREADY_EXISTS",
    "ALREADY_EXISTS_BUSINESS",
})


def replay_dlq_row(row_id: int) -> Dict[str, Any]:
    """
    Replay a single row from ota_dead_letter through the canonical ingest pipeline.

    Flow:
    1. Read row from ota_dead_letter
    2. If already successfully replayed → return idempotent result (no re-processing)
    3. Determine skill from event_type
    4. Re-run skill on envelope_json payload
    5. Call apply_envelope(envelope_json_with_new_idempotency, emitted)
    6. Write replayed_at, replay_result, replay_trace_id back to the row
    7. Return result dict

    This function always goes through apply_envelope.
    It never bypasses the canonical apply gate.
    It never reads booking_state directly.
    It never mutates canonical state outside of apply_envelope.

    Returns a dict with keys:
      - row_id: int
      - replay_result: str
      - replay_trace_id: str (the new idempotency key used for the replay)
      - already_replayed: bool (True if this was an idempotent no-op)
      - apply_result: dict or None (the raw apply_envelope response)
    """
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set for DLQ replay")

    if create_client is None:  # pragma: no cover
        raise EnvironmentError("supabase-py is not installed")

    client = create_client(url, key)

    # --- Step 1: Read the DLQ row ---
    rows = client.table("ota_dead_letter").select("*").eq("id", row_id).execute()
    if not rows.data:
        raise ValueError(f"DLQ row {row_id} not found")
    row = rows.data[0]

    # --- Step 2: Idempotency guard ---
    if row.get("replay_result") in _ALREADY_APPLIED_STATUSES:
        return {
            "row_id": row_id,
            "replay_result": row["replay_result"],
            "replay_trace_id": row.get("replay_trace_id"),
            "already_replayed": True,
            "apply_result": None,
        }

    # --- Step 3: Resolve skill ---
    event_type = row["event_type"]
    skill_registry = _get_skill_registry()
    skill_fn = skill_registry.get(event_type)
    if skill_fn is None:
        result = _record_replay_outcome(
            client=client,
            row_id=row_id,
            replay_result="NO_SKILL_FOR_EVENT_TYPE",
            replay_trace_id=None,
        )
        return {
            "row_id": row_id,
            "replay_result": "NO_SKILL_FOR_EVENT_TYPE",
            "replay_trace_id": None,
            "already_replayed": False,
            "apply_result": None,
        }

    # --- Step 4: Re-run skill ---
    envelope_json: Dict[str, Any] = row["envelope_json"] or {}
    payload = envelope_json.get("payload", {})

    try:
        skill_out = skill_fn(payload)
        emitted = [{"type": e.type, "payload": dict(e.payload)} for e in skill_out.events_to_emit]
    except Exception as exc:
        _record_replay_outcome(client=client, row_id=row_id, replay_result=f"SKILL_ERROR:{exc}", replay_trace_id=None)
        return {
            "row_id": row_id,
            "replay_result": f"SKILL_ERROR:{exc}",
            "replay_trace_id": None,
            "already_replayed": False,
            "apply_result": None,
        }

    # --- Step 5: Build new idempotency key and call apply_envelope ---
    replay_trace_id = f"dlq-replay-{row_id}-{uuid.uuid4().hex[:8]}"

    replay_envelope = dict(envelope_json)
    replay_envelope["idempotency"] = {"request_id": replay_trace_id}

    try:
        res = client.rpc("apply_envelope", {
            "p_envelope": replay_envelope,
            "p_emit": emitted,
        }).execute()
        apply_result: Optional[Dict[str, Any]] = res.data
        replay_result = (apply_result or {}).get("status", "UNKNOWN")
    except APIError as exc:
        replay_result = f"REJECTED:{exc.message}"
        apply_result = None

    # --- Step 6: Write outcome back to DLQ row ---
    _record_replay_outcome(
        client=client,
        row_id=row_id,
        replay_result=replay_result,
        replay_trace_id=replay_trace_id,
    )

    return {
        "row_id": row_id,
        "replay_result": replay_result,
        "replay_trace_id": replay_trace_id,
        "already_replayed": False,
        "apply_result": apply_result,
    }


def _record_replay_outcome(
    *,
    client: Any,
    row_id: int,
    replay_result: str,
    replay_trace_id: Optional[str],
) -> None:
    """Write replay outcome fields back to ota_dead_letter row."""
    client.table("ota_dead_letter").update({
        "replayed_at": datetime.now(timezone.utc).isoformat(),
        "replay_result": replay_result,
        "replay_trace_id": replay_trace_id,
    }).eq("id", row_id).execute()
