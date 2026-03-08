from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Optional

from adapters.ota.dlq_inspector import get_pending_count


_DEFAULT_THRESHOLD = 10
_ENV_VAR = "DLQ_ALERT_THRESHOLD"


@dataclass(frozen=True)
class DLQAlertResult:
    """
    Result of a DLQ threshold check.

    Fields:
        pending_count: number of unresolved DLQ rows at check time
        threshold:     the threshold value used for this check
        exceeded:      True if pending_count >= threshold
        message:       human-readable summary of the check result
    """
    pending_count: int
    threshold: int
    exceeded: bool
    message: str


def check_dlq_threshold(
    threshold: int,
    client: Any = None,
) -> DLQAlertResult:
    """
    Check whether the DLQ pending count exceeds the given threshold.

    If exceeded, emits a structured WARNING to stderr.
    Does not raise. Does not write to any database.
    Does not send external alerts.

    Args:
        threshold: alert if pending_count >= this value
        client:    optional injected Supabase client (for testing without live DB)

    Returns:
        DLQAlertResult with pending_count, threshold, exceeded, message
    """
    pending = get_pending_count(client)
    exceeded = pending >= threshold

    if exceeded:
        message = (
            f"[DLQ ALERT] pending={pending} >= threshold={threshold} — "
            f"{pending} unresolved DLQ rows require attention"
        )
        print(message, file=sys.stderr)
    else:
        message = (
            f"[DLQ OK] pending={pending} < threshold={threshold}"
        )

    return DLQAlertResult(
        pending_count=pending,
        threshold=threshold,
        exceeded=exceeded,
        message=message,
    )


def check_dlq_threshold_default(client: Any = None) -> DLQAlertResult:
    """
    Check DLQ threshold using the value from DLQ_ALERT_THRESHOLD env var.

    Default threshold: 10 (if env var is not set or invalid).
    """
    raw = os.environ.get(_ENV_VAR, "")
    try:
        threshold = int(raw) if raw.strip() else _DEFAULT_THRESHOLD
    except ValueError:
        threshold = _DEFAULT_THRESHOLD

    return check_dlq_threshold(threshold=threshold, client=client)
