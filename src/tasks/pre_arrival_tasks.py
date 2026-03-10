"""
Phase 206 — Pre-Arrival Guest Task Workflow

Pure module for generating guest-enriched pre-arrival tasks.

Architecture:
- Pure function: no DB calls, no side effects.
- Input: booking data + guest profile data (passed by caller).
- Output: deterministic list of Task objects.
- Same pattern as task_automator.py.

Pre-arrival task rules (Phase 206):

    tasks_for_pre_arrival(...)
        → GUEST_WELCOME task  (priority HIGH, due: check_in,
                               title personalized with guest_name,
                               description includes special_requests if present)
        → CHECKIN_PREP task   (priority HIGH, due: check_in,
                               title enriched: "Check-in prep – {guest_name} arriving {check_in}")

Design decisions:
- guest_name defaults to "Guest" if not provided (no-guest-linked fallback).
- special_requests is appended to GUEST_WELCOME description if non-empty.
- task_id is deterministic: sha256(kind:booking_id:property_id)[:16]
  This means pre_arrival CHECKIN_PREP de-dupes with the BOOKING_CREATED one.
  That is intentional — same booking, same task, just richer description.
- This module never reads from the database.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from tasks.task_model import (
    Task,
    TaskKind,
    TaskPriority,
)

_DEFAULT_GUEST_NAME = "Guest"


def tasks_for_pre_arrival(
    tenant_id: str,
    booking_id: str,
    property_id: str,
    check_in: str,
    guest_name: Optional[str] = None,
    special_requests: Optional[str] = None,
    created_at: Optional[str] = None,
) -> List[Task]:
    """
    Emit pre-arrival tasks enriched with guest profile data.

    Rules (Phase 206):
      - GUEST_WELCOME: priority HIGH, due check_in, personalized with guest_name.
        special_requests appended to description if non-empty.
      - CHECKIN_PREP: priority HIGH, due check_in, title enriched with guest name.

    Args:
        tenant_id:        Owning tenant.
        booking_id:       Canonical booking_id (e.g. "bookingcom_R001").
        property_id:      Property this booking applies to.
        check_in:         ISO 8601 date string for check_in (YYYY-MM-DD).
        guest_name:       Guest's first name. Defaults to "Guest" if None/empty.
        special_requests: Guest's special requests (free text). Optional.
        created_at:       ISO 8601 UTC timestamp. Defaults to now.

    Returns:
        List of two Tasks: [GUEST_WELCOME, CHECKIN_PREP], always in this order.
    """
    if created_at is None:
        created_at = datetime.now(tz=timezone.utc).isoformat()

    name = guest_name.strip() if guest_name and guest_name.strip() else _DEFAULT_GUEST_NAME

    # Build GUEST_WELCOME description
    welcome_description: Optional[str] = None
    if special_requests and special_requests.strip():
        welcome_description = (
            f"Guest special requests: {special_requests.strip()}"
        )

    guest_welcome = Task.build(
        kind=TaskKind.GUEST_WELCOME,
        tenant_id=tenant_id,
        booking_id=booking_id,
        property_id=property_id,
        due_date=check_in,
        title=f"Welcome prep for {name}",
        created_at=created_at,
        priority=TaskPriority.HIGH,
        description=welcome_description,
    )

    checkin_prep = Task.build(
        kind=TaskKind.CHECKIN_PREP,
        tenant_id=tenant_id,
        booking_id=booking_id,
        property_id=property_id,
        due_date=check_in,
        title=f"Check-in prep \u2013 {name} arriving {check_in}",
        created_at=created_at,
        priority=TaskPriority.HIGH,
    )

    return [guest_welcome, checkin_prep]


def has_special_requests(special_requests: Optional[str]) -> bool:
    """Return True if special_requests is non-empty after stripping."""
    return bool(special_requests and special_requests.strip())
