from __future__ import annotations

import sys
from typing import Any, Dict, List

from adapters.ota.ordering_buffer import get_buffered_events, mark_replayed
from adapters.ota.dlq_replay import replay_dlq_row


def trigger_ordered_replay(
    booking_id: str,
    client: Any = None,
) -> Dict[str, Any]:
    """
    After a successful BOOKING_CREATED, replay any ordering-buffered events
    that were waiting for this booking_id to exist.

    Flow:
    1. read waiting buffer rows for booking_id
    2. for each row: call replay_dlq_row(dlq_row_id)
    3. on success: mark_replayed(buffer_id)
    4. on failure: log warning and continue (best-effort)

    Never raises. Returns a summary dict.

    Args:
        booking_id: the booking_id just created
        client:     optional injected Supabase client

    Returns:
        {
          "booking_id": str,
          "replayed":   int,
          "failed":     int,
          "results":    list[dict]
        }
    """
    waiting = get_buffered_events(booking_id, client)

    replayed = 0
    failed = 0
    results: List[Dict[str, Any]] = []

    for row in waiting:
        buffer_id = row["id"]
        dlq_row_id = row["dlq_row_id"]

        try:
            replay_result = replay_dlq_row(dlq_row_id)
            mark_replayed(buffer_id, client)
            replayed += 1
            results.append({
                "buffer_id": buffer_id,
                "dlq_row_id": dlq_row_id,
                "status": "replayed",
                "replay_result": replay_result,
            })
        except Exception as exc:
            failed += 1
            print(
                f"[ORDERING TRIGGER] replay failed for buffer_id={buffer_id} "
                f"dlq_row_id={dlq_row_id}: {exc}",
                file=sys.stderr,
            )
            results.append({
                "buffer_id": buffer_id,
                "dlq_row_id": dlq_row_id,
                "status": "failed",
                "error": str(exc),
            })

    return {
        "booking_id": booking_id,
        "replayed": replayed,
        "failed": failed,
        "results": results,
    }
