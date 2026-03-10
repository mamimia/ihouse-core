"""
Phase 128 — Conflict Center

Provides a tenant-scoped view of all active booking conflicts across all (or one)
properties. A conflict exists when two or more ACTIVE bookings share at least one
overlapping date for the same property.

This router:
- Reads from booking_state only (same source as availability_projection, Phase 126).
- Never reads event_log, booking_financial_facts, or tasks.
- Never writes to any table.
- JWT auth required (tenant-scoped via X-Tenant-ID header or jwt_auth Depends).
- Computes conflicts in Python (no DB-level date arithmetic).

Endpoint:
    GET /conflicts?property_id=<optional>

Response:
    {
        "tenant_id": "...",
        "conflicts": [
            {
                "property_id": "prop_1",
                "booking_a": "bookingcom_R001",
                "booking_b": "airbnb_X002",
                "overlap_dates": ["2026-04-05", "2026-04-06"],
                "overlap_start": "2026-04-05",
                "overlap_end": "2026-04-07",   # exclusive
                "severity": "WARNING" | "CRITICAL"
            }
        ],
        "summary": {
            "total_conflicts": 1,
            "properties_affected": 1,
            "bookings_involved": 2
        }
    }

Severity:
    - CRITICAL: overlap >= 3 nights
    - WARNING:  overlap 1-2 nights

Design:
    - All ACTIVE bookings are fetched (or just a given property_id's bookings).
    - Group by property_id.
    - For each property, collect per-date occupancy per booking.
    - Any date occupied by 2+ bookings → conflict pair.
    - Pairs are deduplicated (A,B) vs (B,A).
    - Overlap_dates = sorted list of conflicting dates.
    - overlap_start/end derived from overlap_dates (min, max+1day).
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from itertools import combinations
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response
from core.skills.booking_conflict_resolver.skill import run as _skill_run  # Phase 184
from services.conflict_resolution_writer import write_resolution  # Phase 184

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# DB client helper
# ---------------------------------------------------------------------------

def _get_supabase_client(request: Request) -> Any:
    """Resolve Supabase client from app.state (standard pattern)."""
    return request.app.state.supabase


# ---------------------------------------------------------------------------
# Conflict computation — pure Python
# ---------------------------------------------------------------------------

def _date_set_for_booking(check_in_str: str, check_out_str: str) -> Set[date]:
    """
    Return a set of dates [check_in, check_out) — check_out exclusive.
    Returns empty set on parse error.
    """
    try:
        ci = date.fromisoformat(check_in_str)
        co = date.fromisoformat(check_out_str)
    except (ValueError, TypeError):
        return set()
    dates: Set[date] = set()
    current = ci
    while current < co:
        dates.add(current)
        current += timedelta(days=1)
    return dates


def _find_conflicts_for_property(
    bookings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Given a list of ACTIVE bookings for a single property, find all pairs
    that overlap on at least one date.

    Returns a list of conflict dicts:
        {
            "booking_a": str,
            "booking_b": str,
            "overlap_dates": List[str],  # sorted ISO strings
            "overlap_start": str,
            "overlap_end": str,          # exclusive (day after last overlap)
            "severity": "CRITICAL" | "WARNING",
        }
    """
    # Build per-booking date sets
    booking_dates: List[Tuple[str, Set[date]]] = []
    for b in bookings:
        bid = b.get("booking_id", "")
        ci = b.get("canonical_check_in") or b.get("check_in", "")
        co = b.get("canonical_check_out") or b.get("check_out", "")
        ds = _date_set_for_booking(ci, co)
        if bid and ds:
            booking_dates.append((bid, ds))

    conflicts: List[Dict[str, Any]] = []
    seen_pairs: Set[Tuple[str, str]] = set()

    for (bid_a, dates_a), (bid_b, dates_b) in combinations(booking_dates, 2):
        pair = (min(bid_a, bid_b), max(bid_a, bid_b))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        overlap = dates_a & dates_b
        if not overlap:
            continue

        sorted_overlap = sorted(overlap)
        overlap_start = sorted_overlap[0].isoformat()
        overlap_end = (sorted_overlap[-1] + timedelta(days=1)).isoformat()
        nights = len(sorted_overlap)
        severity = "CRITICAL" if nights >= 3 else "WARNING"

        conflicts.append({
            "booking_a": min(bid_a, bid_b),
            "booking_b": max(bid_a, bid_b),
            "overlap_dates": [d.isoformat() for d in sorted_overlap],
            "overlap_start": overlap_start,
            "overlap_end": overlap_end,
            "severity": severity,
        })

    return conflicts


def _find_all_conflicts(
    bookings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Group bookings by property_id and find conflicts in each group.
    Returns a flat list of conflict dicts (with property_id added).
    """
    # Group by property_id
    by_property: Dict[str, List[Dict[str, Any]]] = {}
    for b in bookings:
        pid = b.get("property_id", "")
        if pid:
            by_property.setdefault(pid, []).append(b)

    all_conflicts: List[Dict[str, Any]] = []
    for pid, prop_bookings in sorted(by_property.items()):
        for conflict in _find_conflicts_for_property(prop_bookings):
            all_conflicts.append({"property_id": pid, **conflict})

    return all_conflicts


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/conflicts",
    tags=["conflicts"],
    summary="Conflict Center — active booking overlaps (Phase 128)",
    description=(
        "Returns all active booking conflicts (overlapping dates on the same property) "
        "for the authenticated tenant.\n\n"
        "**Filter:** Optionally filter by `property_id`.\n\n"
        "**Conflict definition:** Two or more ACTIVE bookings share at least one date "
        "on the same property (check_in inclusive, check_out exclusive).\n\n"
        "**Severity:** CRITICAL ≥ 3 nights overlap; WARNING 1-2 nights.\n\n"
        "**Source:** `booking_state` — read-only. Never reads event_log, "
        "booking_financial_facts, or tasks."
    ),
    responses={
        200: {"description": "Active conflicts for this tenant."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_conflicts(
    request: Request,
    tenant_id: str = Depends(jwt_auth),
    property_id: Optional[str] = None,
) -> JSONResponse:
    """
    GET /conflicts?property_id=<optional>

    Returns all active booking overlaps (conflicts) for the authenticated tenant.

    Authentication: Bearer JWT required. tenant_id from sub claim.

    Query parameters:
        property_id (optional): if provided, only check this property.

    Reads from: booking_state (ACTIVE only). Never writes.
    """
    try:
        db = _get_supabase_client(request)

        # Fetch all ACTIVE bookings for this tenant (optionally scoped to property)
        query = (
            db.table("booking_state")
            .select(
                "booking_id, property_id, "
                "canonical_check_in, canonical_check_out, "
                "lifecycle_status, tenant_id"
            )
            .eq("tenant_id", tenant_id)
            .eq("lifecycle_status", "ACTIVE")
        )
        if property_id:
            query = query.eq("property_id", property_id)

        result = query.execute()
        bookings = result.data or []

    except Exception:  # noqa: BLE001
        return make_error_response(
            500,
            "INTERNAL_ERROR",
            "Failed to query booking state.",
        )

    conflicts = _find_all_conflicts(bookings)

    # Summary
    affected_properties = {c["property_id"] for c in conflicts}
    involved_bookings: Set[str] = set()
    for c in conflicts:
        involved_bookings.add(c["booking_a"])
        involved_bookings.add(c["booking_b"])

    return JSONResponse(
        status_code=200,
        content={
            "tenant_id": tenant_id,
            "conflicts": conflicts,
            "summary": {
                "total_conflicts": len(conflicts),
                "properties_affected": len(affected_properties),
                "bookings_involved": len(involved_bookings),
            },
        },
    )


# ---------------------------------------------------------------------------
# Phase 184 — POST /conflicts/resolve
# ---------------------------------------------------------------------------

@router.post(
    "/conflicts/resolve",
    tags=["conflicts"],
    summary="Conflict Resolver — run skill + persist artifacts (Phase 184)",
    description=(
        "Evaluates a booking_candidate against existing bookings using the "
        "booking_conflict_resolver skill. If conflicts are detected, enforces "
        "PendingResolution, creates a ConflictTask, and optionally an OverrideRequest "
        "(for admin/ops_admin actors with allow_admin_override=true). "
        "Artifacts are written to conflict_resolution_queue. "
        "AuditEvent is written to admin_audit_log (best-effort)."
    ),
    responses={
        200: {"description": "Conflict resolution decision + created artifacts."},
        400: {"description": "Invalid input payload."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def resolve_conflict(
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    POST /conflicts/resolve

    Body (JSON):
        {
            "actor": {"actor_id": "...", "role": "worker|manager|admin|ops_admin"},
            "booking_candidate": {
                "booking_id": "...",
                "property_id": "...",
                "start_utc": "2026-05-01",
                "end_utc": "2026-05-05",
                "requested_status": "ACTIVE"   // optional
            },
            "existing_bookings": [             // caller provides; use GET /conflicts to fetch
                {
                    "booking_id": "...",
                    "property_id": "...",
                    "start_utc": "...",
                    "end_utc": "...",
                    "status": "ACTIVE"
                }
            ],
            "policy": {
                "statuses_blocking": ["ACTIVE"],
                "allow_admin_override": false,
                "conflict_task_type_id": "CONFLICT_REVIEW",
                "override_request_type_id": "CONFLICT_OVERRIDE"
            },
            "idempotency": {"request_id": "..."},
            "time": {"now_utc": "2026-05-01T12:00:00Z"}
        }
    """
    import json as _json
    from datetime import datetime, timezone

    # --- Parse body ---
    try:
        body = await request.json()
    except Exception:
        return make_error_response(400, "INVALID_INPUT", "Request body must be valid JSON.")

    if not isinstance(body, dict):
        return make_error_response(400, "INVALID_INPUT", "Request body must be a JSON object.")

    # Inject tenant_id into idempotency and time defaults
    if "idempotency" not in body or not body["idempotency"].get("request_id"):
        return make_error_response(400, "INVALID_INPUT", "idempotency.request_id is required.")

    if "time" not in body or not body["time"].get("now_utc"):
        body.setdefault("time", {})
        body["time"]["now_utc"] = datetime.now(timezone.utc).isoformat()

    # --- Run skill (pure, no IO) ---
    result = _skill_run(body)

    if "error" in result:
        return make_error_response(400, "INVALID_INPUT", f"Skill returned: {result['error']}")

    # If allowed=False (e.g. INVALID_WINDOW), return 400 with denial_code
    decision = result.get("decision", {})
    if not decision.get("allowed", True) and decision.get("denial_code"):
        return make_error_response(
            400,
            decision["denial_code"],
            f"Booking window rejected: {decision['denial_code']}",
        )

    # --- Persist artifacts (best-effort) ---
    try:
        db = _get_supabase_client(request)
        artifacts_written, audit_written = write_resolution(
            db=db,
            tenant_id=tenant_id,
            artifacts_to_create=result.get("artifacts_to_create", []),
            events_to_emit=result.get("events_to_emit", []),
        )
    except Exception as exc:
        logger.warning("conflicts_router: write_resolution failed: %s", exc)
        artifacts_written, audit_written = 0, 0

    return JSONResponse(
        status_code=200,
        content={
            "tenant_id":         tenant_id,
            "decision":          result.get("decision", {}),
            "artifacts_created": result.get("artifacts_to_create", []),
            "artifacts_written": artifacts_written,
            "audit_written":     audit_written,
        },
    )


# ---------------------------------------------------------------------------
# Phase 207 — POST /conflicts/auto-check/{booking_id}
# ---------------------------------------------------------------------------

@router.post(
    "/conflicts/auto-check/{booking_id}",
    tags=["conflicts"],
    summary="Manually trigger conflict auto-check for a booking (Phase 207)",
    description=(
        "Runs the conflict auto-resolver for the given booking. "
        "Useful for retroactively checking bookings that existed before "
        "Phase 207 was deployed, or for operator debugging.\n\n"
        "**Flow:** Looks up `booking_state` for `property_id`, runs "
        "`conflict_auto_resolver.run_auto_check()`, returns result.\n\n"
        "**Idempotent:** Artifacts are upserted on `(booking_id, request_id, artifact_type)` — "
        "safe to call multiple times. Each call generates a new `request_id` so a fresh "
        "ConflictTask row is written per invocation (not de-duped across calls)."
    ),
    responses={
        200: {"description": "Auto-check completed."},
        401: {"description": "Missing or invalid JWT."},
        404: {"description": "Booking not found for this tenant."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def auto_check_conflict(
    booking_id: str,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    POST /conflicts/auto-check/{booking_id}

    Trigger the conflict auto-resolver for a specific booking.
    JWT auth required (tenant isolation).
    """
    from datetime import datetime, timezone
    from services.conflict_auto_resolver import run_auto_check

    try:
        db = _get_supabase_client(request)

        # --- Step 1: Resolve booking ---
        booking_result = (
            db.table("booking_state")
            .select("booking_id, property_id, tenant_id")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not booking_result.data:
            return make_error_response(
                404, ErrorCode.NOT_FOUND,
                f"Booking '{booking_id}' not found for this tenant",
            )

        property_id: str = booking_result.data[0].get("property_id") or ""

        # --- Step 2: Run auto-check ---
        result = run_auto_check(
            db=db,
            tenant_id=tenant_id,
            booking_id=booking_id,
            property_id=property_id,
            event_kind="MANUAL",
            now_utc=datetime.now(tz=timezone.utc).isoformat(),
        )

        return JSONResponse(
            status_code=200,
            content={
                "booking_id":       booking_id,
                "property_id":      property_id,
                "conflicts_found":  result.conflicts_found,
                "artifacts_written": result.artifacts_written,
                "partial":          result.partial,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("auto_check_conflict error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to run auto-check")

