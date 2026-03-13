"""
Phase 535 / 561 — Export Router
===========================

Provides CSV download endpoints + response envelope adoption.
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
import io

from services.export_service import export_data
from api.response_envelope import success as env_success

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/csv/{export_type}")
async def download_csv(
    export_type: str,
    property_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    """
    Download data as CSV.

    export_type: bookings | financials | feedback | audit
    """
    from dependencies import get_db
    db = get_db()

    filters = {}
    if property_id:
        filters["property_id"] = property_id
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    csv_content = export_data(db, export_type, filters)

    filename = f"{export_type}_export.csv"
    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/types")
async def list_export_types():
    """List available export types — Phase 561 envelope adoption."""
    return env_success(
        data=[
            {"id": "bookings", "label": "Bookings", "description": "All booking records"},
            {"id": "financials", "label": "Financial Facts", "description": "Revenue, commission, fees"},
            {"id": "feedback", "label": "Guest Feedback", "description": "Ratings and comments"},
            {"id": "audit", "label": "Audit Log", "description": "Admin action history"},
        ]
    )

