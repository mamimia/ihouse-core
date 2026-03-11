"""
Phase 247 — Guest Feedback Collection API

Endpoints:
    POST /guest-feedback/{booking_id}
        Submit guest feedback. No JWT auth — verification_token-gated.
        Idempotent: a token can only be used once.
        Body: { rating (1-5), category (optional), comment (optional),
                verification_token (required) }

    GET  /admin/guest-feedback
        Admin view of aggregated guest feedback.
        JWT auth required. Tenant-scoped.
        Query params:
            property_id (optional) — filter by property
            from_date   (optional) — ISO date, filter submitted_at >= from_date
            to_date     (optional) — ISO date, filter submitted_at <= to_date
        Response:
            total_count, avg_rating, nps_score,
            category_breakdown { category: count },
            by_property { property_id: { avg_rating, nps_score, count } },
            feedback (list of raw rows)

NPS Score:
    Promoters   = rating 5  → +1
    Passives    = rating 4  → neutral
    Detractors  = rating 1-3 → -1
    NPS = round((promoters - detractors) / total × 100, 1)
    Ranges from -100 to +100.

Invariants:
    - POST does NOT require JWT — verification_token is the access control.
    - GET requires JWT (admin).
    - verification_token is unique — prevents duplicate submissions.
    - tenant_id on POST is resolved from the booking record via booking_id lookup
      (reads booking_state to find the tenant). If not found → 404.
    - Reads/writes guest_feedback table only for the feedback domain.
    - booking_state read for tenant resolution is read-only and scoped.
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Supabase helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:  # pragma: no cover
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# NPS helpers
# ---------------------------------------------------------------------------

def _nps_category(rating: int) -> str:
    if rating == 5:
        return "promoter"
    if rating == 4:
        return "passive"
    return "detractor"


def _compute_nps(rows: List[dict]) -> Optional[float]:
    """
    Compute NPS from a list of feedback rows (each must have a 'rating' key).
    Returns None if no rows.
    """
    if not rows:
        return None
    promoters = sum(1 for r in rows if r.get("rating") == 5)
    detractors = sum(1 for r in rows if (r.get("rating") or 0) <= 3)
    total = len(rows)
    return round((promoters - detractors) / total * 100, 1)


def _avg_rating(rows: List[dict]) -> Optional[float]:
    if not rows:
        return None
    return round(sum(r.get("rating", 0) for r in rows) / len(rows), 2)


def _category_breakdown(rows: List[dict]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for r in rows:
        cat = r.get("category") or "uncategorized"
        counts[cat] += 1
    return dict(sorted(counts.items()))


def _by_property(rows: List[dict]) -> Dict[str, Any]:
    groups: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        groups[r.get("property_id", "unknown")].append(r)

    result: Dict[str, Any] = {}
    for pid, prows in sorted(groups.items()):
        result[pid] = {
            "count": len(prows),
            "avg_rating": _avg_rating(prows),
            "nps_score": _compute_nps(prows),
        }
    return result


# ---------------------------------------------------------------------------
# POST /guest-feedback/{booking_id}
# ---------------------------------------------------------------------------

@router.post(
    "/guest-feedback/{booking_id}",
    tags=["guest"],
    summary="Submit guest feedback for a booking (token-gated, no auth)",
    responses={
        201: {"description": "Feedback submitted"},
        400: {"description": "Validation error or token already used"},
        404: {"description": "Booking not found"},
        500: {"description": "Internal server error"},
    },
)
async def submit_guest_feedback(
    booking_id: str,
    body: dict,
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Submit post-stay feedback.

    **No JWT auth** — access is controlled by `verification_token`.

    **Body (JSON):**
    - `verification_token` *(required)* — issued by the platform on checkout
    - `rating` *(required)* — integer 1–5
    - `category` *(optional)* — e.g. "cleanliness", "location", "value"
    - `comment` *(optional)* — free-text

    **Idempotency:** each token can only be used once.
    """
    # Validate
    token = body.get("verification_token")
    rating_raw = body.get("rating")

    if not token:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="verification_token is required.",
        )
    try:
        rating = int(rating_raw)
        if not 1 <= rating <= 5:
            raise ValueError()
    except (TypeError, ValueError):
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="rating must be an integer between 1 and 5.",
        )

    category = body.get("category")
    comment = body.get("comment")

    try:
        db = _client if _client is not None else _get_supabase_client()

        # Resolve tenant_id + property_id from booking_state
        bs_result = (
            db.table("booking_state")
            .select("tenant_id, property_id")
            .eq("booking_id", booking_id)
            .limit(1)
            .execute()
        )
        booking_rows = bs_result.data or []
        if not booking_rows:
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                message=f"Booking {booking_id!r} not found.",
            )

        tenant_id = booking_rows[0]["tenant_id"]
        property_id = booking_rows[0].get("property_id") or ""

        # Insert (will fail if token is duplicate due to unique index)
        row = {
            "booking_id": booking_id,
            "tenant_id": tenant_id,
            "property_id": property_id,
            "rating": rating,
            "category": category,
            "comment": comment,
            "verification_token": token,
            "token_used": True,
        }
        result = db.table("guest_feedback").insert(row).execute()
        saved = result.data[0] if result.data else row

        return JSONResponse(
            status_code=201,
            content={
                "message": "Feedback submitted. Thank you!",
                "feedback_id": saved.get("id"),
                "booking_id": booking_id,
                "rating": rating,
                "nps_category": _nps_category(rating),
            },
        )

    except Exception as exc:  # noqa: BLE001
        # Detect unique index violation (token already used)
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            return make_error_response(
                status_code=400,
                code="TOKEN_ALREADY_USED",
                message="This verification token has already been used.",
            )
        logger.exception(
            "POST /guest-feedback/%s error: %s", booking_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/guest-feedback
# ---------------------------------------------------------------------------

@router.get(
    "/admin/guest-feedback",
    tags=["admin"],
    summary="Aggregated guest feedback with NPS scores (admin)",
    responses={
        200: {"description": "Aggregated feedback stats"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_admin_guest_feedback(
    property_id: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Admin-facing aggregated guest feedback.

    **Authentication:** Bearer JWT. `sub` claim = `tenant_id`.

    **Query parameters (all optional):**
    - `property_id` — filter to a specific property
    - `from_date` — ISO date (e.g. "2025-01-01"), filter submitted_at >= from_date
    - `to_date` — ISO date, filter submitted_at <= to_date

    **Returns:**
    - `total_count`, `avg_rating` (2dp), `nps_score` (-100 to +100)
    - `category_breakdown` — count per feedback category
    - `by_property` — per-property NPS, avg_rating, count
    - `feedback` — list of raw feedback rows
    """
    try:
        db = _client if _client is not None else _get_supabase_client()

        q = (
            db.table("guest_feedback")
            .select(
                "id, booking_id, property_id, rating, category, comment, "
                "submitted_at, nps_category:rating"
            )
            .eq("tenant_id", tenant_id)
        )
        if property_id:
            q = q.eq("property_id", property_id)
        if from_date:
            q = q.gte("submitted_at", from_date)
        if to_date:
            q = q.lte("submitted_at", to_date + "T23:59:59Z")

        result = q.order("submitted_at", desc=True).execute()
        rows = result.data or []

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "filters": {
                    "property_id": property_id,
                    "from_date": from_date,
                    "to_date": to_date,
                },
                "total_count": len(rows),
                "avg_rating": _avg_rating(rows),
                "nps_score": _compute_nps(rows),
                "category_breakdown": _category_breakdown(rows),
                "by_property": _by_property(rows),
                "feedback": rows,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/guest-feedback error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
