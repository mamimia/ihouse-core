"""
Phase 487 — Conflict Scanner Service

Scans all active bookings per property for date overlaps.
Uses booking_state (check_in, check_out) to detect conflicts
and writes detected overlaps to conflict_tasks table.

This fills the gap for bookings created before the auto-check hook
was active in service.py (Phase 207).
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ihouse.conflict_scanner")


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _parse_date(val: Any) -> Optional[date]:
    """Parse a date from string or date object."""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


def _dates_overlap(a_in: date, a_out: date, b_in: date, b_out: date) -> bool:
    """Check if two date ranges overlap (exclusive of checkout day)."""
    return a_in < b_out and b_in < a_out


def _conflict_id(booking_a: str, booking_b: str, property_id: str) -> str:
    """Deterministic conflict_task_id for a pair."""
    pair = sorted([booking_a, booking_b])
    raw = f"{pair[0]}:{pair[1]}:{property_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def scan_property_conflicts(
    bookings: List[Dict[str, Any]],
    property_id: str,
) -> List[Dict[str, Any]]:
    """
    Find all overlapping booking pairs for a single property.

    Args:
        bookings: List of booking dicts with booking_id, check_in, check_out, status
        property_id: The property being scanned

    Returns:
        List of conflict dicts: {booking_a, booking_b, property_id, overlap_days}
    """
    # Filter to active bookings with valid dates
    active = []
    for b in bookings:
        status = (b.get("status") or "").upper()
        if status in ("CANCELED", "CANCELLED"):
            continue
        ci = _parse_date(b.get("check_in"))
        co = _parse_date(b.get("check_out"))
        if ci and co and co > ci:
            active.append({
                "booking_id": b["booking_id"],
                "check_in": ci,
                "check_out": co,
                "status": status,
            })

    conflicts = []
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            if _dates_overlap(a["check_in"], a["check_out"],
                              b["check_in"], b["check_out"]):
                # Calculate overlap days
                overlap_start = max(a["check_in"], b["check_in"])
                overlap_end = min(a["check_out"], b["check_out"])
                overlap_days = (overlap_end - overlap_start).days

                conflicts.append({
                    "booking_a": a["booking_id"],
                    "booking_b": b["booking_id"],
                    "property_id": property_id,
                    "overlap_days": overlap_days,
                    "conflict_task_id": _conflict_id(
                        a["booking_id"], b["booking_id"], property_id
                    ),
                })

    return conflicts


def run_full_scan(
    *,
    tenant_id: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Scan all properties for booking date overlaps and write conflict_tasks.

    Args:
        tenant_id: Optional filter.
        dry_run: If True, detect but don't write to Supabase.

    Returns:
        Summary dict with property_count, total_conflicts, written, etc.
    """
    db = _get_db()

    # Fetch all bookings with dates
    query = db.table("booking_state").select(
        "booking_id, property_id, tenant_id, check_in, check_out, status"
    )
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)

    response = query.execute()
    all_bookings = response.data or []

    # Group by property
    by_property: Dict[str, List[Dict]] = {}
    for b in all_bookings:
        pid = b.get("property_id", "")
        if pid:
            by_property.setdefault(pid, []).append(b)

    stats = {
        "total_bookings": len(all_bookings),
        "properties_scanned": len(by_property),
        "total_conflicts": 0,
        "written": 0,
        "skipped_existing": 0,
        "errors": 0,
        "dry_run": dry_run,
        "conflicts": [],
    }

    for property_id, bookings in by_property.items():
        conflicts = scan_property_conflicts(bookings, property_id)
        stats["total_conflicts"] += len(conflicts)

        for conflict in conflicts:
            stats["conflicts"].append({
                "booking_a": conflict["booking_a"],
                "booking_b": conflict["booking_b"],
                "property_id": conflict["property_id"],
                "overlap_days": conflict["overlap_days"],
            })

            if dry_run:
                continue

            try:
                # Use the first booking's tenant_id
                b_tenant = next(
                    (b.get("tenant_id", tenant_id or "")
                     for b in bookings
                     if b["booking_id"] in (conflict["booking_a"], conflict["booking_b"])),
                    tenant_id or "",
                )

                import json
                from datetime import datetime, timezone
                now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

                db.table("conflict_tasks").upsert(
                    {
                        "conflict_task_id": conflict["conflict_task_id"],
                        "booking_id": conflict["booking_a"],
                        "property_id": property_id,
                        "status": "Open",
                        "priority": "High",
                        "conflicts_json": json.dumps({
                            "peer_booking": conflict["booking_b"],
                            "overlap_days": conflict["overlap_days"],
                        }),
                        "created_at_ms": now_ms,
                        "updated_at_ms": now_ms,
                    },
                    on_conflict="conflict_task_id",
                ).execute()
                stats["written"] += 1
            except Exception as exc:
                logger.warning("conflict_scanner write error: %s", exc)
                stats["errors"] += 1

    logger.info("Conflict scan complete: %s", {k: v for k, v in stats.items() if k != "conflicts"})
    return stats
