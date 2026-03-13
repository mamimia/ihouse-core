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


# ---------------------------------------------------------------------------
# Phase 235 — GET /admin/conflicts/dashboard
# ---------------------------------------------------------------------------

def _compute_dashboard(
    conflicts: List[Dict[str, Any]],
    severity_filter: Optional[str],
    today: date,
) -> Dict[str, Any]:
    """
    Take a flat conflicts list (each has property_id, severity, overlap_start, …)
    and return aggregated dashboard data.
    """
    # Optional severity filter
    if severity_filter:
        conflicts = [c for c in conflicts if c.get("severity") == severity_filter.upper()]

    # --- Summary ---
    critical = sum(1 for c in conflicts if c.get("severity") == "CRITICAL")
    warning = sum(1 for c in conflicts if c.get("severity") == "WARNING")
    affected_props = {c["property_id"] for c in conflicts}
    involved: set = set()
    for c in conflicts:
        involved.add(c.get("booking_a", ""))
        involved.add(c.get("booking_b", ""))
    involved.discard("")

    summary = {
        "total_conflicts": len(conflicts),
        "critical": critical,
        "warning": warning,
        "properties_affected": len(affected_props),
        "bookings_involved": len(involved),
    }

    # --- By property ---
    by_prop: Dict[str, Dict[str, Any]] = {}
    for c in conflicts:
        pid = c["property_id"]
        if pid not in by_prop:
            by_prop[pid] = {"property_id": pid, "conflicts": [], "critical": 0, "warning": 0, "oldest_days": -1}
        entry = by_prop[pid]
        entry["conflicts"].append(c)
        if c.get("severity") == "CRITICAL":
            entry["critical"] += 1
        else:
            entry["warning"] += 1
        # Age in days since overlap_start
        try:
            age = (today - date.fromisoformat(c["overlap_start"])).days
            if entry["oldest_days"] < age:
                entry["oldest_days"] = age
        except (ValueError, KeyError):
            pass

    by_property = []
    for pid in sorted(by_prop.keys()):
        e = by_prop[pid]
        by_property.append({
            "property_id": pid,
            "conflicts": e["conflicts"],
            "critical": e["critical"],
            "warning": e["warning"],
            "oldest_conflict_days": max(0, e["oldest_days"]),
        })

    # --- Weekly timeline (last 4 ISO weeks) ---
    timeline = []
    for weeks_ago in range(3, -1, -1):
        week_start = today - timedelta(days=today.weekday() + weeks_ago * 7)
        week_end = week_start + timedelta(days=7)
        count = sum(
            1 for c in conflicts
            if c.get("overlap_start") and
            week_start <= date.fromisoformat(c["overlap_start"]) < week_end
        )
        timeline.append({"week_start": week_start.isoformat(), "conflict_count": count})

    # --- Heuristic narrative ---
    if len(conflicts) == 0:
        narrative = "No active conflicts detected across your portfolio."
    else:
        most_props = sorted(by_prop.keys(),
                            key=lambda p: by_prop[p]["critical"] * 10 + by_prop[p]["warning"],
                            reverse=True)
        top_prop = most_props[0] if most_props else "unknown"
        this_week = timeline[-1]["conflict_count"] if timeline else 0
        narrative = (
            f"{len(conflicts)} active conflict{'s' if len(conflicts) != 1 else ''} "
            f"({critical} CRITICAL, {warning} WARNING) across "
            f"{len(affected_props)} propert{'ies' if len(affected_props) != 1 else 'y'}. "
            f"{this_week} conflict{'s' if this_week != 1 else ''} this week. "
            f"Property with most conflicts: {top_prop}."
        )

    return {
        "summary": summary,
        "by_property": by_property,
        "timeline": timeline,
        "narrative": narrative,
    }


@router.get(
    "/admin/conflicts/dashboard",
    tags=["conflicts"],
    summary="Multi-Property Conflict Dashboard (Phase 235)",
    description=(
        "Cross-property conflict aggregation dashboard. "
        "Groups active conflicts by property, computes severity breakdown, "
        "age of oldest conflict, and a 4-week timeline. "
        "Includes a heuristic narrative summary.\n\n"
        "**Filters:** `property_id` (optional), `severity=CRITICAL|WARNING` (optional).\n\n"
        "**Source:** `booking_state` — read-only. Never writes."
    ),
    responses={
        200: {"description": "Dashboard data"},
        400: {"description": "Invalid severity parameter"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_conflict_dashboard(
    request: Request,
    tenant_id: str = Depends(jwt_auth),
    property_id: Optional[str] = None,
    severity: Optional[str] = None,
) -> JSONResponse:
    """
    GET /admin/conflicts/dashboard?property_id=&severity=CRITICAL|WARNING

    Multi-property conflict dashboard. Reuses Phase 128 conflict detection logic
    and adds grouping, age tracking, weekly timeline, and a heuristic narrative.
    """
    from datetime import datetime, timezone

    if severity and severity.upper() not in ("CRITICAL", "WARNING"):
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR,
            "severity must be CRITICAL or WARNING"
        )

    try:
        db = _get_supabase_client(request)

        query = (
            db.table("booking_state")
            .select(
                "booking_id, property_id, "
                "canonical_check_in, canonical_check_out, "
                "check_in, check_out, "
                "lifecycle_status, tenant_id"
            )
            .eq("tenant_id", tenant_id)
            .eq("lifecycle_status", "ACTIVE")
        )
        if property_id:
            query = query.eq("property_id", property_id)

        result = query.execute()
        bookings = result.data or []

    except Exception as exc:  # noqa: BLE001
        logger.exception("conflict_dashboard: DB error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to query booking state")

    conflicts = _find_all_conflicts(bookings)
    today = datetime.now(tz=timezone.utc).date()
    dashboard = _compute_dashboard(conflicts, severity, today)

    return JSONResponse(
        status_code=200,
        content={
            "tenant_id": tenant_id,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "filters": {
                "property_id": property_id,
                "severity": severity,
            },
            **dashboard,
        },
    )


# ---------------------------------------------------------------------------
# Phase 487 — POST /conflicts/scan (full property scan + backfill)
# ---------------------------------------------------------------------------

@router.post(
    "/conflicts/scan",
    tags=["conflicts", "admin"],
    summary="Full conflict scan — detect all overlapping bookings (Phase 487)",
    description=(
        "Scans all properties for date overlaps among active bookings and "
        "writes detected conflicts to the conflict_tasks table.\n\n"
        "Supports dry_run mode for preview without writes."
    ),
    responses={
        200: {"description": "Scan complete with results."},
        401: {"description": "Missing or invalid JWT."},
    },
)
async def scan_all_conflicts(
    dry_run: bool = False,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    POST /conflicts/scan?dry_run=false

    Triggers a full tenant-wide conflict scan. Writes detected overlaps
    to conflict_tasks table. Safe to run multiple times (upserts on
    deterministic conflict_task_id).
    """
    try:
        from services.conflict_scanner import run_full_scan
        result = run_full_scan(tenant_id=tenant_id, dry_run=dry_run)

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "tenant_id": tenant_id,
                **result,
            },
        )
    except Exception as exc:
        logger.exception("POST /conflicts/scan error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Conflict scan failed")
