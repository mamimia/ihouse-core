"""
Phase 496 — Guest Feedback Collection + Storage

Collects guest feedback (ratings 1-5, comments) via the guest portal
and stores in guest_feedback table. Supports aggregation per property.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ihouse.guest_feedback")


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def submit_feedback(
    db: Any,
    booking_id: str,
    rating: int,
    comment: str = "",
    tenant_id: str = "",
    property_id: str = "",
    source: str = "portal",
) -> Dict[str, Any]:
    """
    Submit guest feedback for a booking.

    Args:
        db: Supabase client.
        booking_id: The booking being reviewed.
        rating: 1-5 star rating.
        comment: Optional text feedback.
        tenant_id: Tenant scope.
        property_id: Property the booking is for.
        source: 'portal' | 'email' | 'sms' | 'manual'.

    Returns:
        Created feedback row.
    """
    if not 1 <= rating <= 5:
        return {"error": "Rating must be between 1 and 5."}

    # Look up tenant_id and property_id if not provided
    if not tenant_id or not property_id:
        try:
            booking_result = (
                db.table("booking_state")
                .select("tenant_id, property_id")
                .eq("booking_id", booking_id)
                .limit(1)
                .execute()
            )
            if booking_result.data:
                tenant_id = tenant_id or booking_result.data[0].get("tenant_id", "")
                property_id = property_id or booking_result.data[0].get("property_id", "")
        except Exception:
            pass

    try:
        result = db.table("guest_feedback").insert({
            "tenant_id": tenant_id,
            "booking_id": booking_id,
            "property_id": property_id,
            "rating": rating,
            "comment": comment,
            "source": source,
        }).execute()
        return result.data[0] if result.data else {"booking_id": booking_id, "status": "submitted"}
    except Exception as exc:
        logger.warning("submit_feedback failed: %s", exc)
        return {"error": str(exc)}


def get_property_feedback_summary(
    db: Any,
    property_id: str,
    tenant_id: str,
) -> Dict[str, Any]:
    """
    Get aggregated feedback for a property.

    Returns:
        Summary with average rating, count, and distribution.
    """
    try:
        result = (
            db.table("guest_feedback")
            .select("rating, comment, booking_id, submitted_at")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .order("submitted_at", desc=True)
            .execute()
        )
        feedbacks = result.data or []
    except Exception as exc:
        logger.warning("get_property_feedback_summary failed: %s", exc)
        return {"error": str(exc)}

    if not feedbacks:
        return {
            "property_id": property_id,
            "total_reviews": 0,
            "average_rating": 0.0,
            "distribution": {str(i): 0 for i in range(1, 6)},
        }

    ratings = [f["rating"] for f in feedbacks if f.get("rating")]
    distribution = {str(i): sum(1 for r in ratings if r == i) for i in range(1, 6)}

    return {
        "property_id": property_id,
        "total_reviews": len(feedbacks),
        "average_rating": round(sum(ratings) / len(ratings), 1) if ratings else 0.0,
        "distribution": distribution,
        "recent_comments": [
            {"rating": f["rating"], "comment": f.get("comment", ""), "date": f.get("submitted_at", "")}
            for f in feedbacks[:5]
            if f.get("comment")
        ],
    }
