from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from supabase import create_client  # may be absent in test environments without Supabase
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment,misc]


def write_to_dlq(
    *,
    provider: str,
    event_type: str,
    rejection_code: str,
    rejection_msg: Optional[str],
    envelope_json: Dict[str, Any],
    emitted_json: Optional[List[Dict[str, Any]]] = None,
    trace_id: Optional[str] = None,
) -> None:
    """
    Write a rejected OTA event to the ota_dead_letter table.

    This is a best-effort, append-only preservation layer.
    It must NEVER block the OTA ingestion response.
    It must NEVER bypass apply_envelope.
    It must NEVER mutate canonical state.

    Failures in DLQ writes are logged and swallowed — they must not
    propagate up to the OTA adapter caller.
    """
    try:
        _do_write(
            provider=provider,
            event_type=event_type,
            rejection_code=rejection_code,
            rejection_msg=rejection_msg,
            envelope_json=envelope_json,
            emitted_json=emitted_json,
            trace_id=trace_id,
        )
    except Exception as exc:  # noqa: BLE001
        # DLQ write must never raise — log and swallow
        import sys
        print(
            f"[DLQ] WARNING: failed to write dead letter entry: {exc}",
            file=sys.stderr,
        )


def _do_write(
    *,
    provider: str,
    event_type: str,
    rejection_code: str,
    rejection_msg: Optional[str],
    envelope_json: Dict[str, Any],
    emitted_json: Optional[List[Dict[str, Any]]],
    trace_id: Optional[str],
) -> None:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        import sys
        print("[DLQ] WARNING: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set — DLQ write skipped", file=sys.stderr)
        return

    if create_client is None:  # pragma: no cover
        import sys
        print("[DLQ] WARNING: supabase-py not installed — DLQ write skipped", file=sys.stderr)
        return

    client = create_client(url, key)

    client.table("ota_dead_letter").insert({
        "provider": provider,
        "event_type": event_type,
        "rejection_code": rejection_code,
        "rejection_msg": rejection_msg,
        "envelope_json": envelope_json,
        "emitted_json": emitted_json,
        "trace_id": trace_id,
    }).execute()
