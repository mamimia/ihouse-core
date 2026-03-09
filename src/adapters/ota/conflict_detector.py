"""
Phase 86 — Conflict Detection Layer

Detects booking conflicts and coverage gaps by reading existing tables.
This module is **purely read-only** — it never writes to booking_state,
event_log, or any other table.

Detection categories:
  A. DATE_OVERLAP      — Two ACTIVE bookings on the same property overlap in dates
  B. MISSING_DATES     — An ACTIVE booking has no check_in or check_out recorded
  C. MISSING_PROPERTY  — An ACTIVE booking has no property_id recorded
  D. DUPLICATE_REF     — Two bookings share the same (provider, reservation_id) pair

Design rules:
  - booking_state is the read source — it represents current derived state.
  - Date fields are read from booking_state.state_json if not top-level columns.
  - All queries are tenant-scoped.
  - Results are returned as ConflictReport — never raises.
  - Severity: ERROR (must investigate) > WARNING (may be data quality issue)

Invariants:
  - This module NEVER writes to any table.
  - This module NEVER calls apply_envelope or any writer.
  - Conflict detection does not block ingestion — it is a visibility tool only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class ConflictKind(str, Enum):
    DATE_OVERLAP     = "DATE_OVERLAP"       # Two active bookings overlap on same property
    MISSING_DATES    = "MISSING_DATES"      # Active booking has no check_in or check_out
    MISSING_PROPERTY = "MISSING_PROPERTY"   # Active booking has no property_id
    DUPLICATE_REF    = "DUPLICATE_REF"      # Two bookings share same provider+reservation_id


class ConflictSeverity(str, Enum):
    ERROR   = "ERROR"    # Must investigate — potential overbooking / data integrity failure
    WARNING = "WARNING"  # Data quality issue — should review, may not be immediately harmful


@dataclass(frozen=True)
class Conflict:
    """
    A single detected conflict.

    kind:         ConflictKind
    severity:     ERROR or WARNING
    booking_id_a: First booking involved
    booking_id_b: Second booking involved (None for single-booking conflicts)
    property_id:  Property affected (None if unknown)
    detail:       Human-readable description of the conflict
    metadata:     Additional structured data (dates, provider, refs, etc.)
    """
    kind: ConflictKind
    severity: ConflictSeverity
    booking_id_a: str
    detail: str
    booking_id_b: Optional[str] = None
    property_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConflictReport:
    """
    Result of running the full conflict detection scan.

    tenant_id:     Tenant scanned
    conflicts:     All detected conflicts, ordered by severity (ERROR first)
    partial:       True if any source query failed — scan may be incomplete
    scanned_count: Number of active bookings examined
    """
    tenant_id: str
    conflicts: List[Conflict]
    partial: bool = False
    scanned_count: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for c in self.conflicts if c.severity == ConflictSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.conflicts if c.severity == ConflictSeverity.WARNING)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_field(row: dict, key: str) -> Optional[str]:
    """
    Read a field from a booking_state row.
    Checks top-level first, then falls back to state_json dict.
    Returns None if not present in either location.
    """
    if key in row and row[key] is not None:
        return str(row[key])
    state = row.get("state_json") or {}
    if isinstance(state, dict):
        val = state.get(key)
        return str(val) if val is not None else None
    return None


def _dates_overlap(
    check_in_a: Optional[str],
    check_out_a: Optional[str],
    check_in_b: Optional[str],
    check_out_b: Optional[str],
) -> bool:
    """
    Returns True if two date ranges [check_in_a, check_out_a) and
    [check_in_b, check_out_b) overlap.

    Uses ISO string comparison (YYYY-MM-DD) which is lexicographically
    correct for date ordering.

    check_out is treated as exclusive (guest departs on checkout day).
    Returns False if any date is None (cannot determine overlap).
    """
    if not all([check_in_a, check_out_a, check_in_b, check_out_b]):
        return False
    # Overlap condition: A starts before B ends AND B starts before A ends
    return check_in_a < check_out_b and check_in_b < check_out_a


def _fetch_active_bookings(db: Any, tenant_id: str):
    """
    Fetch all ACTIVE bookings for the tenant from booking_state.
    Returns (rows, failed_bool).
    """
    try:
        result = (
            db.table("booking_state")
            .select("booking_id, status, tenant_id, state_json, provider, reservation_id")
            .eq("tenant_id", tenant_id)
            .eq("status", "ACTIVE")
            .execute()
        )
        return result.data or [], False
    except Exception:  # noqa: BLE001
        return [], True


# ---------------------------------------------------------------------------
# Detection functions (each returns List[Conflict])
# ---------------------------------------------------------------------------

def _detect_missing_dates(rows: List[dict]) -> List[Conflict]:
    """
    Detect ACTIVE bookings with no check_in or check_out.
    Severity: WARNING — may be a temporary ingestion state.
    """
    conflicts = []
    for row in rows:
        booking_id = row.get("booking_id", "UNKNOWN")
        check_in = _get_field(row, "check_in")
        check_out = _get_field(row, "check_out")

        if not check_in or not check_out:
            missing = []
            if not check_in:
                missing.append("check_in")
            if not check_out:
                missing.append("check_out")

            conflicts.append(Conflict(
                kind=ConflictKind.MISSING_DATES,
                severity=ConflictSeverity.WARNING,
                booking_id_a=booking_id,
                detail=f"Active booking {booking_id!r} is missing: {', '.join(missing)}",
                property_id=_get_field(row, "property_id"),
                metadata={"missing_fields": missing},
            ))
    return conflicts


def _detect_missing_property(rows: List[dict]) -> List[Conflict]:
    """
    Detect ACTIVE bookings with no property_id.
    Severity: ERROR — a booking without a property cannot be conflict-checked.
    """
    conflicts = []
    for row in rows:
        booking_id = row.get("booking_id", "UNKNOWN")
        property_id = _get_field(row, "property_id")

        if not property_id:
            conflicts.append(Conflict(
                kind=ConflictKind.MISSING_PROPERTY,
                severity=ConflictSeverity.ERROR,
                booking_id_a=booking_id,
                detail=f"Active booking {booking_id!r} has no property_id recorded",
                metadata={},
            ))
    return conflicts


def _detect_date_overlaps(rows: List[dict]) -> List[Conflict]:
    """
    Detect pairs of ACTIVE bookings on the same property whose dates overlap.
    Severity: ERROR — potential overbooking.

    Uses O(n²) comparison — acceptable for expected booking volumes per tenant.
    Skips pairs where either booking has missing dates (handled separately).
    """
    conflicts = []

    # Group by property_id; skip rows without property
    by_property: Dict[str, list] = {}
    for row in rows:
        prop = _get_field(row, "property_id")
        if prop:
            by_property.setdefault(prop, []).append(row)

    for property_id, bookings in by_property.items():
        for i in range(len(bookings)):
            for j in range(i + 1, len(bookings)):
                a = bookings[i]
                b = bookings[j]

                ci_a = _get_field(a, "check_in")
                co_a = _get_field(a, "check_out")
                ci_b = _get_field(b, "check_in")
                co_b = _get_field(b, "check_out")

                if _dates_overlap(ci_a, co_a, ci_b, co_b):
                    bid_a = a.get("booking_id", "UNKNOWN")
                    bid_b = b.get("booking_id", "UNKNOWN")
                    conflicts.append(Conflict(
                        kind=ConflictKind.DATE_OVERLAP,
                        severity=ConflictSeverity.ERROR,
                        booking_id_a=bid_a,
                        booking_id_b=bid_b,
                        property_id=property_id,
                        detail=(
                            f"Overlap on property {property_id!r}: "
                            f"{bid_a!r} [{ci_a}→{co_a}] "
                            f"conflicts with {bid_b!r} [{ci_b}→{co_b}]"
                        ),
                        metadata={
                            "check_in_a": ci_a, "check_out_a": co_a,
                            "check_in_b": ci_b, "check_out_b": co_b,
                        },
                    ))
    return conflicts


def _detect_duplicate_refs(rows: List[dict]) -> List[Conflict]:
    """
    Detect bookings that share the same (provider, reservation_id) pair.
    Severity: ERROR — same reservation ingested twice = dedup failure or replay artifact.

    Only compares ACTIVE bookings — a canceled + active pair may be expected
    (e.g., canceled and re-created) but is not flagged here.
    """
    seen: Dict[tuple, str] = {}  # (provider, reservation_id) → first booking_id
    conflicts = []

    for row in rows:
        provider = _get_field(row, "provider") or row.get("provider")
        reservation_id = _get_field(row, "reservation_id") or row.get("reservation_id")
        booking_id = row.get("booking_id", "UNKNOWN")

        if not provider or not reservation_id:
            continue

        key = (provider, reservation_id)
        if key in seen:
            conflicts.append(Conflict(
                kind=ConflictKind.DUPLICATE_REF,
                severity=ConflictSeverity.ERROR,
                booking_id_a=seen[key],
                booking_id_b=booking_id,
                detail=(
                    f"Duplicate booking reference: provider={provider!r} "
                    f"reservation_id={reservation_id!r} appears in both "
                    f"{seen[key]!r} and {booking_id!r}"
                ),
                metadata={"provider": provider, "reservation_id": reservation_id},
            ))
        else:
            seen[key] = booking_id

    return conflicts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_conflicts(db: Any, tenant_id: str) -> ConflictReport:
    """
    Run the full conflict detection scan for a tenant.

    Reads from booking_state (ACTIVE rows only). All detection is purely
    in-memory after the initial query — no additional DB calls per detection.

    Detection order:
      1. MISSING_PROPERTY (ERROR) — blocks date overlap detection
      2. MISSING_DATES (WARNING) — logged but does not block overlap check
      3. DATE_OVERLAP (ERROR) — overlap on same property
      4. DUPLICATE_REF (ERROR) — same (provider, reservation_id) in two bookings

    Returns ConflictReport — never raises.
    partial=True if the source query failed.

    Args:
        db:        Supabase client (or compatible mock)
        tenant_id: Authenticated tenant identifier

    Returns:
        ConflictReport
    """
    rows, failed = _fetch_active_bookings(db, tenant_id)

    if failed:
        return ConflictReport(
            tenant_id=tenant_id,
            conflicts=[],
            partial=True,
            scanned_count=0,
        )

    all_conflicts: List[Conflict] = []
    all_conflicts.extend(_detect_missing_property(rows))
    all_conflicts.extend(_detect_missing_dates(rows))
    all_conflicts.extend(_detect_date_overlaps(rows))
    all_conflicts.extend(_detect_duplicate_refs(rows))

    # Sort: ERROR first, then WARNING; within same severity preserve detection order
    sorted_conflicts = sorted(
        all_conflicts,
        key=lambda c: (0 if c.severity == ConflictSeverity.ERROR else 1),
    )

    return ConflictReport(
        tenant_id=tenant_id,
        conflicts=sorted_conflicts,
        partial=False,
        scanned_count=len(rows),
    )
