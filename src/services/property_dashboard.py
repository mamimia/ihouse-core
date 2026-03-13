"""
Phase 499 — Property Management Dashboard Data Service

Aggregates cross-table data for the property management dashboard:
- Occupancy rates per property
- Revenue summary
- Active tasks
- Upcoming check-ins/check-outs
- Guest feedback ratings

This is the data layer behind the frontend property dashboard.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ihouse.property_dashboard")


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def get_property_dashboard(
    db: Any,
    tenant_id: str,
    property_id: str,
) -> Dict[str, Any]:
    """
    Get comprehensive dashboard data for a single property.

    Aggregates:
    - Occupancy for current month
    - Revenue from booking_financial_facts
    - Active task counts
    - Upcoming arrivals/departures
    - Guest feedback average
    """
    today = date.today()
    month_start = today.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1)  # next month start
    week_ahead = today + timedelta(days=7)

    dashboard: Dict[str, Any] = {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "occupancy": {},
        "revenue": {},
        "tasks": {},
        "upcoming": {},
        "feedback": {},
    }

    # --- Occupancy ---
    try:
        bookings_result = (
            db.table("booking_state")
            .select("booking_id, check_in, check_out, status")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .gte("check_out", month_start.isoformat())
            .lte("check_in", month_end.isoformat())
            .execute()
        )
        bookings = bookings_result.data or []

        # Count occupied nights this month
        occupied_nights = set()
        for b in bookings:
            if (b.get("status") or "").upper() in ("CANCELED", "CANCELLED"):
                continue
            try:
                ci = date.fromisoformat(str(b.get("check_in", ""))[:10])
                co = date.fromisoformat(str(b.get("check_out", ""))[:10])
                current = max(ci, month_start)
                end = min(co, month_end)
                while current < end:
                    occupied_nights.add(current)
                    current += timedelta(days=1)
            except (ValueError, TypeError):
                pass

        days_in_month = (month_end - month_start).days
        dashboard["occupancy"] = {
            "month": month_start.isoformat(),
            "occupied_nights": len(occupied_nights),
            "total_nights": days_in_month,
            "occupancy_pct": round(len(occupied_nights) / max(days_in_month, 1) * 100, 1),
            "active_bookings": len([b for b in bookings if (b.get("status") or "").upper() != "CANCELED"]),
        }
    except Exception as exc:
        logger.warning("dashboard occupancy error: %s", exc)
        dashboard["occupancy"] = {"error": str(exc)}

    # --- Revenue ---
    try:
        rev_result = (
            db.table("booking_financial_facts")
            .select("total_gross, net_to_property, management_fee")
            .eq("property_id", property_id)
            .execute()
        )
        facts = rev_result.data or []
        dashboard["revenue"] = {
            "total_gross": round(sum(float(f.get("total_gross", 0) or 0) for f in facts), 2),
            "total_net": round(sum(float(f.get("net_to_property", 0) or 0) for f in facts), 2),
            "total_mgmt_fee": round(sum(float(f.get("management_fee", 0) or 0) for f in facts), 2),
            "bookings_with_financials": len(facts),
        }
    except Exception as exc:
        logger.warning("dashboard revenue error: %s", exc)
        dashboard["revenue"] = {"error": str(exc)}

    # --- Tasks ---
    try:
        tasks_result = (
            db.table("tasks")
            .select("task_id, status, kind, priority")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        tasks = tasks_result.data or []
        open_tasks = [t for t in tasks if t.get("status") in ("open", "claimed", "in_progress")]
        dashboard["tasks"] = {
            "total": len(tasks),
            "open": len([t for t in open_tasks if t.get("status") == "open"]),
            "in_progress": len([t for t in open_tasks if t.get("status") == "in_progress"]),
            "completed_total": len([t for t in tasks if t.get("status") == "completed"]),
        }
    except Exception as exc:
        logger.warning("dashboard tasks error: %s", exc)
        dashboard["tasks"] = {"error": str(exc)}

    # --- Upcoming ---
    try:
        upcoming_result = (
            db.table("booking_state")
            .select("booking_id, check_in, check_out, guest_name, status")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .gte("check_in", today.isoformat())
            .lte("check_in", week_ahead.isoformat())
            .order("check_in")
            .execute()
        )
        upcoming = upcoming_result.data or []
        dashboard["upcoming"] = {
            "arrivals_this_week": len(upcoming),
            "next_arrival": upcoming[0] if upcoming else None,
        }
    except Exception as exc:
        logger.warning("dashboard upcoming error: %s", exc)
        dashboard["upcoming"] = {"error": str(exc)}

    # --- Feedback ---
    try:
        feedback_result = (
            db.table("guest_feedback")
            .select("rating")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        ratings = [f["rating"] for f in (feedback_result.data or []) if f.get("rating")]
        dashboard["feedback"] = {
            "total_reviews": len(ratings),
            "average_rating": round(sum(ratings) / len(ratings), 1) if ratings else 0.0,
        }
    except Exception as exc:
        logger.warning("dashboard feedback error: %s", exc)
        dashboard["feedback"] = {"error": str(exc)}

    return dashboard


def get_portfolio_overview(
    db: Any,
    tenant_id: str,
) -> Dict[str, Any]:
    """
    Get a high-level overview across all properties for a tenant.
    """
    try:
        props_result = (
            db.table("properties")
            .select("property_id, name")
            .eq("tenant_id", tenant_id)
            .execute()
        )
        properties = props_result.data or []
    except Exception as exc:
        logger.warning("portfolio_overview: error loading properties: %s", exc)
        return {"error": str(exc)}

    try:
        bookings_result = (
            db.table("booking_state")
            .select("property_id", count="exact")
            .eq("tenant_id", tenant_id)
            .execute()
        )
        total_bookings = bookings_result.count if hasattr(bookings_result, "count") else len(bookings_result.data or [])
    except Exception:
        total_bookings = 0

    try:
        tasks_result = (
            db.table("tasks")
            .select("task_id, status", count="exact")
            .eq("tenant_id", tenant_id)
            .neq("status", "completed")
            .execute()
        )
        open_tasks = tasks_result.count if hasattr(tasks_result, "count") else len(tasks_result.data or [])
    except Exception:
        open_tasks = 0

    return {
        "tenant_id": tenant_id,
        "total_properties": len(properties),
        "total_bookings": total_bookings,
        "open_tasks": open_tasks,
        "properties": [{"property_id": p["property_id"], "name": p.get("name", "")} for p in properties],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
