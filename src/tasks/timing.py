"""
src/tasks/timing.py — Phase 1033: Canonical Task Timing Model

Single source of truth for action-window computation.

Rules:
  Acknowledge window:  opens 24 hours before effective_due_at
  Start window:        opens 2 hours before effective_due_at
                       Exception: MAINTENANCE → always open (start_allowed_at = None)
  CRITICAL urgency:    both windows always open (allowed_at = None)
  No due_time:         fall back to kind default; if still None → no gate (always open)
  No due_date:         no gate on either action (always open)

Output fields added to every task row returned to worker / OM surfaces:
  effective_due_at   — ISO 8601 TIMESTAMPTZ string (aware)
  ack_allowed_at     — ISO 8601 or None
  start_allowed_at   — ISO 8601 or None
  ack_is_open        — bool
  start_is_open      — bool
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional

import pytz

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default timezone — all tasks are assumed to be in local property time.
# Phase 1033: single-tenant assumption; per-property TZ is a future phase.
_DEFAULT_TZ = pytz.timezone("Asia/Bangkok")

# Acknowledge window: 24 hours before effective due time
_ACK_WINDOW_HOURS = 24

# Start window: 2 hours before effective due time
_START_WINDOW_HOURS = 2

# Canonical kind → default due time (matches WorkerTaskCard.getDefaultTime())
_KIND_DEFAULT_TIME: dict[str, time] = {
    "CHECKOUT_VERIFY": time(11, 0),
    "CHECKOUT_PREP":   time(11, 0),
    "CLEANING":        time(10, 0),
    "CHECKIN_PREP":    time(14, 0),
    "GUEST_WELCOME":   time(14, 0),
    "MAINTENANCE":     time(17, 0),
}

# Kinds where Start Work is never time-gated
_NO_START_GATE_KINDS = frozenset({"MAINTENANCE", "GENERAL"})


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TaskTiming:
    effective_due_at: Optional[datetime]   # UTC-aware, or None if no due_date
    ack_allowed_at:   Optional[datetime]   # UTC-aware, or None (= always open)
    start_allowed_at: Optional[datetime]   # UTC-aware, or None (= always open)
    ack_is_open:      bool
    start_is_open:    bool

    def as_dict(self) -> dict:
        """Serialisable output for injection into task API responses."""
        def _iso(dt: Optional[datetime]) -> Optional[str]:
            return dt.isoformat() if dt else None

        return {
            "effective_due_at": _iso(self.effective_due_at),
            "ack_allowed_at":   _iso(self.ack_allowed_at),
            "start_allowed_at": _iso(self.start_allowed_at),
            "ack_is_open":      self.ack_is_open,
            "start_is_open":    self.start_is_open,
        }


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def compute_task_timing(
    task_row: dict,
    now_utc: Optional[datetime] = None,
) -> TaskTiming:
    """
    Compute canonical action-window timing for a task row.

    Args:
        task_row:  Raw dict from the tasks table (may include due_date, due_time,
                   kind, priority, urgency).
        now_utc:   Current UTC time (aware). Defaults to datetime.now(timezone.utc).
                   Inject in tests; leave default in production.

    Returns:
        TaskTiming dataclass with all computed fields.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    kind     = (task_row.get("kind") or "").upper()
    priority = (task_row.get("priority") or "").upper()
    urgency  = (task_row.get("urgency")  or "").upper()

    # ── CRITICAL fast-path: all gates open immediately ────────────────────────
    is_critical = priority == "CRITICAL" or urgency == "CRITICAL"

    # ── Resolve effective_due_at ──────────────────────────────────────────────
    due_date_str = task_row.get("due_date")   # "YYYY-MM-DD" or None
    due_time_raw = task_row.get("due_time")   # "HH:MM:SS" / time object / None

    if not due_date_str:
        # No due_date → no gate on anything
        return TaskTiming(
            effective_due_at=None,
            ack_allowed_at=None,
            start_allowed_at=None,
            ack_is_open=True,
            start_is_open=True,
        )

    # Parse due_date
    try:
        due_date_obj = (
            due_date_str if isinstance(due_date_str, date)
            else date.fromisoformat(str(due_date_str)[:10])
        )
    except (ValueError, TypeError):
        # Unparseable — allow everything
        return TaskTiming(
            effective_due_at=None,
            ack_allowed_at=None,
            start_allowed_at=None,
            ack_is_open=True,
            start_is_open=True,
        )

    # Parse due_time
    due_time_obj: Optional[time] = None
    if due_time_raw is not None:
        if isinstance(due_time_raw, time):
            due_time_obj = due_time_raw
        else:
            try:
                due_time_obj = time.fromisoformat(str(due_time_raw)[:8])
            except (ValueError, TypeError):
                due_time_obj = None

    # Fall back to kind default if DB value is NULL
    if due_time_obj is None:
        due_time_obj = _KIND_DEFAULT_TIME.get(kind)

    if due_time_obj is None:
        # No time at all (ad-hoc GENERAL task, etc.) → no gate
        return TaskTiming(
            effective_due_at=None,
            ack_allowed_at=None,
            start_allowed_at=None,
            ack_is_open=True,
            start_is_open=True,
        )

    # Combine date + time in local timezone → convert to UTC
    local_naive = datetime.combine(due_date_obj, due_time_obj)
    local_aware = _DEFAULT_TZ.localize(local_naive)
    effective_due_at_utc: datetime = local_aware.astimezone(timezone.utc)

    # ── CRITICAL: all gates open ──────────────────────────────────────────────
    if is_critical:
        return TaskTiming(
            effective_due_at=effective_due_at_utc,
            ack_allowed_at=None,
            start_allowed_at=None,
            ack_is_open=True,
            start_is_open=True,
        )

    # ── Acknowledge window ────────────────────────────────────────────────────
    ack_allowed_at = effective_due_at_utc - timedelta(hours=_ACK_WINDOW_HOURS)

    # ── Start window ──────────────────────────────────────────────────────────
    if kind in _NO_START_GATE_KINDS:
        start_allowed_at: Optional[datetime] = None   # MAINTENANCE: never gated
    else:
        start_allowed_at = effective_due_at_utc - timedelta(hours=_START_WINDOW_HOURS)

    # ── Evaluate open/closed ──────────────────────────────────────────────────
    ack_is_open   = (ack_allowed_at   is None) or (now_utc >= ack_allowed_at)
    start_is_open = (start_allowed_at is None) or (now_utc >= start_allowed_at)

    return TaskTiming(
        effective_due_at=effective_due_at_utc,
        ack_allowed_at=ack_allowed_at,
        start_allowed_at=start_allowed_at,
        ack_is_open=ack_is_open,
        start_is_open=start_is_open,
    )


# ---------------------------------------------------------------------------
# Batch enrichment — for task list responses
# ---------------------------------------------------------------------------

def enrich_tasks_with_timing(
    tasks: list[dict],
    now_utc: Optional[datetime] = None,
) -> list[dict]:
    """
    Inject timing fields into every task dict in a list.
    Returns the same list mutated in-place (also returned for chaining).
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    for t in tasks:
        timing = compute_task_timing(t, now_utc=now_utc)
        t.update(timing.as_dict())

    return tasks


# ---------------------------------------------------------------------------
# Human-readable helper for error messages
# ---------------------------------------------------------------------------

def format_opens_in(allowed_at: datetime, now_utc: datetime) -> str:
    """
    Returns a human-readable string like "11h 42m" or "1h 02m" or "42m".
    Used in backend error response messages and in frontend flash labels.
    """
    delta = allowed_at - now_utc
    total_minutes = max(0, int(delta.total_seconds() // 60))
    hours   = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"
