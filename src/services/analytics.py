"""
Phase 264 — Advanced Analytics Service
========================================

Pure analytics layer — no DB required for contract testing.
Three analytics domains:

1. top_properties    — ranked by booking count + revenue
2. ota_mix           — OTA market-share breakdown
3. revenue_summary   — monthly revenue aggregation

All functions accept a list of booking dicts (mirroring the booking_state
shape already used by other analytics routers in this codebase).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


Booking = dict[str, Any]


# ---------------------------------------------------------------------------
# 1. Top-performing properties
# ---------------------------------------------------------------------------

def top_properties(
    bookings: list[Booking],
    limit: int = 10,
    sort_by: str = "revenue",  # "revenue" | "bookings"
) -> list[dict]:
    """
    Rank properties by total confirmed revenue or booking count.
    Returns up to `limit` entries newest-first within each rank.
    """
    by_prop: dict[str, dict] = {}

    for b in bookings:
        prop_id = b.get("property_id") or b.get("external_property_id") or "unknown"
        prop_name = b.get("property_name", prop_id)
        status = b.get("booking_status", b.get("status", "unknown"))

        if prop_id not in by_prop:
            by_prop[prop_id] = {
                "property_id":   prop_id,
                "property_name": prop_name,
                "total_bookings": 0,
                "confirmed_bookings": 0,
                "total_revenue":  0.0,
                "currency": b.get("currency", "USD"),
            }

        by_prop[prop_id]["total_bookings"] += 1
        if status in ("confirmed", "BOOKING_CREATED"):
            by_prop[prop_id]["confirmed_bookings"] += 1
            revenue = float(b.get("gross_amount", b.get("total_price", 0)) or 0)
            by_prop[prop_id]["total_revenue"] += revenue

    results = list(by_prop.values())
    key = "total_revenue" if sort_by == "revenue" else "confirmed_bookings"
    results.sort(key=lambda x: x[key], reverse=True)
    return results[:limit]


# ---------------------------------------------------------------------------
# 2. OTA Mix
# ---------------------------------------------------------------------------

def ota_mix(bookings: list[Booking]) -> list[dict]:
    """
    Breakdown of bookings by OTA provider: count + revenue share + %.
    """
    by_provider: dict[str, dict] = {}
    total_revenue = 0.0
    total_bookings = len(bookings)

    for b in bookings:
        provider = b.get("provider", b.get("source", "unknown"))
        revenue = float(b.get("gross_amount", b.get("total_price", 0)) or 0)

        if provider not in by_provider:
            by_provider[provider] = {"provider": provider, "bookings": 0, "revenue": 0.0}

        by_provider[provider]["bookings"] += 1
        by_provider[provider]["revenue"] += revenue
        total_revenue += revenue

    results = []
    for entry in by_provider.values():
        entry["booking_pct"] = (
            round(entry["bookings"] / total_bookings * 100, 1) if total_bookings else 0.0
        )
        entry["revenue_pct"] = (
            round(entry["revenue"] / total_revenue * 100, 1) if total_revenue else 0.0
        )
        results.append(entry)

    results.sort(key=lambda x: x["revenue"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# 3. Revenue Summary (monthly)
# ---------------------------------------------------------------------------

def revenue_summary(
    bookings: list[Booking],
    months: int = 12,
) -> list[dict]:
    """
    Monthly revenue aggregation for the last `months` calendar months.
    Reads check_in_date or created_at (YYYY-MM-… prefix) to bucket.
    Returns each bucket: month (YYYY-MM), booking_count, gross_revenue.
    """
    buckets: dict[str, dict] = {}

    for b in bookings:
        date_str = (
            b.get("check_in_date")
            or b.get("created_at", "")
        )
        if not date_str or len(date_str) < 7:
            continue
        month = date_str[:7]  # YYYY-MM

        if month not in buckets:
            buckets[month] = {"month": month, "booking_count": 0, "gross_revenue": 0.0}

        buckets[month]["booking_count"] += 1
        revenue = float(b.get("gross_amount", b.get("total_price", 0)) or 0)
        buckets[month]["gross_revenue"] += round(revenue, 2)

    # Sort chrono, return last N months
    sorted_months = sorted(buckets.values(), key=lambda x: x["month"])
    return sorted_months[-months:]
