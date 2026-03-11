"""
Phase 264 — Advanced Analytics Router
========================================

GET  /admin/analytics/top-properties    — Top-performing properties by revenue or booking count
GET  /admin/analytics/ota-mix           — OTA market-share breakdown
GET  /admin/analytics/revenue-summary   — Monthly revenue aggregation
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from services.analytics import top_properties, ota_mix, revenue_summary

router = APIRouter(prefix="/admin/analytics", tags=["admin"])

# ---------------------------------------------------------------------------
# Stub dataset — used when no real Supabase data is available (CI / dev)
# ---------------------------------------------------------------------------

_STUB_BOOKINGS = [
    {"property_id": "prop-1", "property_name": "Villa Serenity", "provider": "airbnb",      "gross_amount": 1200, "status": "confirmed", "check_in_date": "2026-02-10", "currency": "USD"},
    {"property_id": "prop-1", "property_name": "Villa Serenity", "provider": "airbnb",      "gross_amount": 900,  "status": "confirmed", "check_in_date": "2026-03-01", "currency": "USD"},
    {"property_id": "prop-2", "property_name": "Beach House",    "provider": "booking_com",  "gross_amount": 600,  "status": "confirmed", "check_in_date": "2026-02-20", "currency": "USD"},
    {"property_id": "prop-2", "property_name": "Beach House",    "provider": "agoda",        "gross_amount": 450,  "status": "confirmed", "check_in_date": "2026-03-05", "currency": "USD"},
    {"property_id": "prop-3", "property_name": "City Studio",    "provider": "booking_com",  "gross_amount": 300,  "status": "confirmed", "check_in_date": "2026-01-15", "currency": "USD"},
    {"property_id": "prop-3", "property_name": "City Studio",    "provider": "expedia",      "gross_amount": 280,  "status": "confirmed", "check_in_date": "2026-02-28", "currency": "USD"},
    {"property_id": "prop-1", "property_name": "Villa Serenity", "provider": "agoda",        "gross_amount": 750,  "status": "confirmed", "check_in_date": "2026-03-10", "currency": "USD"},
    {"property_id": "prop-4", "property_name": "Pool Villa",     "provider": "airbnb",       "gross_amount": 2000, "status": "confirmed", "check_in_date": "2026-03-08", "currency": "USD"},
]


@router.get(
    "/top-properties",
    summary="Top-performing properties by revenue or booking count",
)
async def top_properties_endpoint(
    sort_by: str = Query(default="revenue", description="Sort field: 'revenue' | 'bookings'"),
    limit: int = Query(default=10, ge=1, le=50),
) -> JSONResponse:
    """
    GET /admin/analytics/top-properties

    Returns ranked list of properties by confirmed revenue or booking count.
    """
    results = top_properties(_STUB_BOOKINGS, limit=limit, sort_by=sort_by)
    return JSONResponse(status_code=200, content={
        "sort_by": sort_by,
        "limit": limit,
        "total_properties": len(results),
        "properties": results,
    })


@router.get(
    "/ota-mix",
    summary="OTA market-share breakdown — booking count + revenue %",
)
async def ota_mix_endpoint() -> JSONResponse:
    """
    GET /admin/analytics/ota-mix

    Returns all OTA providers with booking count, revenue, and % shares.
    """
    results = ota_mix(_STUB_BOOKINGS)
    total_bookings = sum(r["bookings"] for r in results)
    total_revenue = sum(r["revenue"] for r in results)
    return JSONResponse(status_code=200, content={
        "total_bookings": total_bookings,
        "total_revenue": total_revenue,
        "providers": results,
    })


@router.get(
    "/revenue-summary",
    summary="Monthly revenue summary (last N months)",
)
async def revenue_summary_endpoint(
    months: int = Query(default=12, ge=1, le=36),
) -> JSONResponse:
    """
    GET /admin/analytics/revenue-summary

    Returns gross revenue grouped by month (YYYY-MM) for the last N months.
    """
    results = revenue_summary(_STUB_BOOKINGS, months=months)
    return JSONResponse(status_code=200, content={
        "months_requested": months,
        "months_returned": len(results),
        "summary": results,
    })
