"""
Owner Portal Data Service — Phase 301
========================================

Rich data queries for the Owner Portal. Reads from:
  - `booking_state`          — booking status, dates, channel
  - `booking_financial_facts` — net revenue, gross, management fee, OTA commission

All queries are scoped to a single property_id.
No write operations. Service-role DB client required.

Design:
    - Returns a rich OwnerPropertySummary dict with occupancy and financials.
    - Financial data (revenue, fees) only returned when role == 'owner'.
    - Booking breakdown counts by status always returned.
    - Date filter: last 90 days for "recent", all time for totals.
    - Best-effort: DB errors return partial data, never 500.

Phase note:
    This service ENRICHES the Phase 298 owner portal with real data rather
    than replacing it. The router calls this module for the /summary endpoint.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _days_ago(n: int) -> str:
    return (_now_utc() - timedelta(days=n)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Booking state queries
# ---------------------------------------------------------------------------

def get_property_booking_counts(db: Any, property_id: str) -> dict:
    """
    Return booking counts by status for a property.

    Returns:
        {
            "total": int,
            "confirmed": int,
            "cancelled": int,
            "checked_in": int,
            "checked_out": int,
            "pending": int,
        }
    """
    counts: dict[str, int] = {
        "total": 0,
        "confirmed": 0,
        "cancelled": 0,
        "checked_in": 0,
        "checked_out": 0,
        "pending": 0,
    }
    try:
        res = (
            db.table("booking_state")
            .select("status")
            .eq("property_id", property_id)
            .execute()
        )
        rows = res.data or []
        counts["total"] = len(rows)
        for row in rows:
            status = (row.get("status") or "pending").lower()
            key = status if status in counts else "pending"
            counts[key] = counts.get(key, 0) + 1
    except Exception as exc:
        logger.warning("get_property_booking_counts error for %s: %s", property_id, exc)
    return counts


def get_property_upcoming_bookings(db: Any, property_id: str, limit: int = 5) -> list[dict]:
    """
    Return the next N upcoming bookings (check_in_date >= today).

    Returns list of dicts with: booking_ref, check_in_date, check_out_date,
    status, channel (OTA source), nights.
    """
    today = _now_utc().strftime("%Y-%m-%d")
    try:
        res = (
            db.table("booking_state")
            .select("booking_ref, check_in_date, check_out_date, status, source")
            .eq("property_id", property_id)
            .gte("check_in_date", today)
            .order("check_in_date", desc=False)
            .limit(limit)
            .execute()
        )
        rows = res.data or []
        return [_enrich_booking_row(r) for r in rows]
    except Exception as exc:
        logger.warning("get_property_upcoming_bookings error for %s: %s", property_id, exc)
        return []


def get_property_recent_bookings(
    db: Any, property_id: str, days: int = 30, limit: int = 5
) -> list[dict]:
    """
    Return recent bookings within the last N days (check_in_date >= N days ago).
    """
    since = _days_ago(days)
    try:
        res = (
            db.table("booking_state")
            .select("booking_ref, check_in_date, check_out_date, status, source")
            .eq("property_id", property_id)
            .gte("check_in_date", since)
            .order("check_in_date", desc=True)
            .limit(limit)
            .execute()
        )
        rows = res.data or []
        return [_enrich_booking_row(r) for r in rows]
    except Exception as exc:
        logger.warning("get_property_recent_bookings error for %s: %s", property_id, exc)
        return []


def _enrich_booking_row(row: dict) -> dict:
    """Add nights calculation to a booking_state row."""
    out = {
        "booking_ref": row.get("booking_ref", ""),
        "check_in_date": row.get("check_in_date", ""),
        "check_out_date": row.get("check_out_date", ""),
        "status": row.get("status", ""),
        "channel": row.get("source", ""),
        "nights": None,
    }
    try:
        ci = row.get("check_in_date")
        co = row.get("check_out_date")
        if ci and co:
            delta = datetime.fromisoformat(co) - datetime.fromisoformat(ci)
            out["nights"] = max(0, delta.days)
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Financial queries (booking_financial_facts)
# ---------------------------------------------------------------------------

def get_property_financial_summary(db: Any, property_id: str, days: int = 90) -> dict:
    """
    Return financial summary for a property over the last N days.

    Returns:
        {
            "period_days": int,
            "gross_revenue_total": float,
            "net_revenue_total": float,
            "management_fee_total": float,
            "ota_commission_total": float,
            "booking_count_with_financials": int,
        }

    Uses booking_financial_facts joined concept (queries financial_facts via property_id
    available through booking_state foreign key).

    Note: booking_financial_facts.booking_id = booking_state.booking_id.
    We first get booking_ids for the property, then get their financials.
    """
    result: dict[str, Any] = {
        "period_days": days,
        "gross_revenue_total": 0.0,
        "net_revenue_total": 0.0,
        "management_fee_total": 0.0,
        "ota_commission_total": 0.0,
        "booking_count_with_financials": 0,
    }

    since = _days_ago(days)

    # Step 1: get booking_ids for this property in the period
    try:
        res = (
            db.table("booking_state")
            .select("booking_id")
            .eq("property_id", property_id)
            .gte("check_in_date", since)
            .execute()
        )
        booking_ids = [r["booking_id"] for r in (res.data or []) if r.get("booking_id")]
    except Exception as exc:
        logger.warning("get_property_financial_summary: booking_ids fetch error %s", exc)
        return result

    if not booking_ids:
        return result

    # Step 2: get financial facts for those booking_ids
    try:
        facts_res = (
            db.table("booking_financial_facts")
            .select("booking_id, gross_revenue, net_to_property, management_fee, ota_commission")
            .in_("booking_id", booking_ids)
            .execute()
        )
        facts = facts_res.data or []
    except Exception as exc:
        logger.warning("get_property_financial_summary: facts fetch error %s", exc)
        return result

    for f in facts:
        result["gross_revenue_total"] += float(f.get("gross_revenue") or 0)
        result["net_revenue_total"] += float(f.get("net_to_property") or 0)
        result["management_fee_total"] += float(f.get("management_fee") or 0)
        result["ota_commission_total"] += float(f.get("ota_commission") or 0)

    result["booking_count_with_financials"] = len(facts)

    # Round to 2dp
    for key in ("gross_revenue_total", "net_revenue_total",
                "management_fee_total", "ota_commission_total"):
        result[key] = round(result[key], 2)

    return result


# ---------------------------------------------------------------------------
# Occupancy calculation
# ---------------------------------------------------------------------------

def get_property_occupancy_rate(db: Any, property_id: str, days: int = 30) -> dict:
    """
    Calculate occupancy rate for a property over the last N days.

    Occupancy = (total nights with a confirmed/checked_in/checked_out booking)
                / total_days * 100

    Returns: { "occupancy_pct": float, "occupied_nights": int, "period_days": int }
    """
    since = _days_ago(days)
    occupied_nights = 0
    try:
        res = (
            db.table("booking_state")
            .select("check_in_date, check_out_date, status")
            .eq("property_id", property_id)
            .in_("status", ["confirmed", "checked_in", "checked_out"])
            .gte("check_out_date", since)
            .execute()
        )
        for row in (res.data or []):
            try:
                ci = datetime.fromisoformat(row["check_in_date"])
                co = datetime.fromisoformat(row["check_out_date"])
                # Clamp to the period
                start = max(ci, _now_utc() - timedelta(days=days))
                end = min(co, _now_utc())
                nights_in_period = max(0, (end - start).days)
                occupied_nights += nights_in_period
            except Exception:
                pass
    except Exception as exc:
        logger.warning("get_property_occupancy_rate error for %s: %s", property_id, exc)

    occupancy_pct = round(min(100.0, (occupied_nights / days) * 100), 1) if days > 0 else 0.0
    return {
        "occupancy_pct": occupancy_pct,
        "occupied_nights": occupied_nights,
        "period_days": days,
    }


# ---------------------------------------------------------------------------
# Full rich summary (combines all above)
# ---------------------------------------------------------------------------

def get_owner_property_rich_summary(
    db: Any,
    property_id: str,
    role: str = "owner",
    financial_period_days: int = 90,
    occupancy_period_days: int = 30,
) -> dict:
    """
    Build a complete rich summary for the owner portal property view.

    Always returns: property_id, role, booking_counts, upcoming_bookings,
                    occupancy (30 days).

    Returns financial summary only when role == 'owner'.

    Args:
        db: Supabase service-role client
        property_id: The property to summarise
        role: 'owner' | 'viewer' — controls financial visibility
        financial_period_days: Rolling window for revenue totals (default 90)
        occupancy_period_days: Rolling window for occupancy % (default 30)
    """
    booking_counts = get_property_booking_counts(db, property_id)
    upcoming = get_property_upcoming_bookings(db, property_id, limit=5)
    occupancy = get_property_occupancy_rate(db, property_id, days=occupancy_period_days)

    summary: dict[str, Any] = {
        "property_id": property_id,
        "role": role,
        "booking_counts": booking_counts,
        "upcoming_bookings": upcoming,
        "occupancy": occupancy,
    }

    if role == "owner":
        financials = get_property_financial_summary(
            db, property_id, days=financial_period_days
        )
        summary["financials"] = financials

    return summary
