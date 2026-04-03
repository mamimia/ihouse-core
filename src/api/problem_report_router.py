"""
Phase 598 + Phases 647–651 — Problem Reports API

Endpoints:
    POST  /problem-reports                   — create a problem report
    GET   /problem-reports                   — list reports (filters: property_id, status, priority)
    GET   /problem-reports/{id}              — get single report
    PATCH /problem-reports/{id}              — update status, assign, resolve
    POST  /problem-reports/{id}/photos       — add photo to report
    GET   /problem-reports/{id}/photos       — list photos for report

Phase 648: Auto-create MAINTENANCE task on problem report creation.
           Urgent → CRITICAL (5-min ACK SLA), Normal → MEDIUM.
Phase 649: List endpoint enhanced with photo_count per report.
Phase 650: Audit event emitted on status change.
Phase 651: SSE alert emitted on urgent problem creation.

Invariant:
    This router NEVER writes to booking_state, event_log, or
    booking_financial_facts.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/problem-reports", tags=["problem-reports"])


def _get_supabase_client() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


_VALID_CATEGORIES = frozenset({
    "pool", "plumbing", "electrical", "ac_heating", "furniture",
    "structure", "tv_electronics", "bathroom", "kitchen",
    "garden_outdoor", "pest", "cleanliness", "security", "other",
})

_VALID_STATUSES = frozenset({"open", "in_progress", "resolved", "dismissed"})
_VALID_PRIORITIES = frozenset({"urgent", "normal"})

# Phase 652 — Category → maintenance specialty mapping
_CATEGORY_SPECIALTY: dict[str, str] = {
    "pool": "pool", "plumbing": "plumbing", "electrical": "electrical",
    "ac_heating": "electrical", "furniture": "furniture",
    "structure": "general", "tv_electronics": "electrical",
    "bathroom": "plumbing", "kitchen": "general",
    "garden_outdoor": "gardening", "pest": "general",
    "cleanliness": "general", "security": "general", "other": "general",
}


# ---------------------------------------------------------------------------
# Phase 648 — Auto-create maintenance task from problem report
# ---------------------------------------------------------------------------

def _auto_create_maintenance_task(
    db: Any, tenant_id: str, property_id: str, booking_id: str | None,
    report_id: str, category: str, priority: str, description: str,
) -> str | None:
    """
    Create a MAINTENANCE task linked to this problem report.
    Returns the task_id or None on error.

    Priority mapping:
        urgent → CRITICAL (5-min ACK SLA per sla_engine.py)
        normal → MEDIUM   (1-hour ACK SLA)
    """
    from datetime import datetime, timezone
    from tasks.task_model import Task, TaskKind, TaskPriority

    task_priority = TaskPriority.CRITICAL if priority == "urgent" else TaskPriority.MEDIUM
    now = datetime.now(tz=timezone.utc).isoformat()
    bid = booking_id or f"report_{report_id[:8]}"

    task = Task.build(
        kind=TaskKind.MAINTENANCE,
        tenant_id=tenant_id,
        booking_id=bid,
        property_id=property_id,
        due_date=now[:10],  # today
        title=f"Maintenance: {category.replace('_', ' ').title()}",
        created_at=now,
        priority=task_priority,
        description=f"Auto-created from problem report. {description[:200]}",
    )

    try:
        db.table("tasks").insert({
            "task_id": task.task_id,
            "kind": task.kind.value,
            "status": task.status.value,
            "priority": task.priority.value,
            "urgency": task.urgency,
            "worker_role": task.worker_role.value,
            "ack_sla_minutes": task.ack_sla_minutes,
            "tenant_id": task.tenant_id,
            "booking_id": task.booking_id,
            "property_id": task.property_id,
            "due_date": task.due_date,
            "title": task.title,
            "description": task.description,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }).execute()
        return task.task_id
    except Exception as exc:
        logger.warning("auto_create_maintenance_task failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Phase 651 — SSE alert on urgent problem
# ---------------------------------------------------------------------------

def _emit_urgent_sse_alert(
    tenant_id: str, report_id: str, property_id: str,
    category: str, description: str,
) -> None:
    """Emit SSE PROBLEM_URGENT event to admin + ops dashboards."""
    try:
        from channels.sse_broker import broker
        broker.publish_alert(
            tenant_id=tenant_id,
            event_type="PROBLEM_URGENT",
            report_id=report_id,
            property_id=property_id,
            category=category,
            description=description[:120],
        )
    except Exception as exc:
        logger.warning("SSE alert failed: %s", exc)


@router.post("/", summary="Create a problem report (Phase 598)",
             responses={201: {}, 400: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def create_problem_report(
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a JSON object."})

    property_id = str(body.get("property_id") or "").strip()
    reported_by = str(body.get("reported_by") or "").strip()
    category = str(body.get("category") or "").strip().lower()
    description = str(body.get("description") or "").strip()

    if not property_id:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'property_id' is required."})
    if not reported_by:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'reported_by' (worker_id) is required."})
    if not category or category not in _VALID_CATEGORIES:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"'category' must be one of: {sorted(_VALID_CATEGORIES)}"})
    if not description:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'description' is required."})

    priority = str(body.get("priority", "normal")).strip().lower()
    if priority not in _VALID_PRIORITIES:
        priority = "normal"

    row = {
        "tenant_id": tenant_id, "property_id": property_id,
        "booking_id": body.get("booking_id"),
        "reported_by": reported_by, "category": category,
        "description": description,
        "description_original_lang": body.get("description_original_lang"),
        "priority": priority, "status": "open",
    }

    try:
        db = client if client is not None else _get_supabase_client()
        result = db.table("problem_reports").insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

        report = rows[0]
        report_id = str(report.get("id", ""))

        # Phase 648 — Auto-create maintenance task
        task_id = _auto_create_maintenance_task(
            db, tenant_id, property_id, body.get("booking_id"),
            report_id, category, priority, description,
        )
        if task_id:
            # Link task to report
            try:
                db.table("problem_reports").update(
                    {"maintenance_task_id": task_id}
                ).eq("id", report_id).eq("tenant_id", tenant_id).execute()
                report["maintenance_task_id"] = task_id
            except Exception:
                pass  # best-effort link

        # Phase 651 — SSE alert on urgent
        if priority == "urgent":
            _emit_urgent_sse_alert(tenant_id, report_id, property_id, category, description)

        # Phase 973 audit fix (Claudia/10): Post-creation property status downgrade.
        # If a property is currently 'ready', filing a new problem report should
        # immediately downgrade it to 'ready_with_issues'. This prevents the property
        # from showing as fully available when an active unresolved issue exists.
        # Non-blocking: report creation succeeds even if this update fails.
        try:
            prop_res = (
                db.table("properties")
                .select("operational_status")
                .eq("property_id", property_id)
                .eq("tenant_id", tenant_id)
                .limit(1)
                .execute()
            )
            current_status = (prop_res.data or [{}])[0].get("operational_status", "")
            if current_status == "ready":
                db.table("properties").update({
                    "operational_status": "ready_with_issues",
                }).eq("property_id", property_id).eq("tenant_id", tenant_id).execute()
                report["_property_status_downgraded"] = True
                logger.info(
                    "create_problem_report: property %s downgraded ready→ready_with_issues "
                    "(new open report %s)",
                    property_id, report_id,
                )
        except Exception as _prop_exc:
            logger.warning(
                "create_problem_report: property status downgrade failed for %s: %s",
                property_id, _prop_exc,
            )

        return JSONResponse(status_code=201, content=report)
    except Exception as exc:
        logger.exception("create problem report error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get("/", summary="List problem reports (Phase 598)",
            responses={200: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def list_problem_reports(
    property_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        q = db.table("problem_reports").select("*").eq("tenant_id", tenant_id)
        if property_id:
            q = q.eq("property_id", property_id)
        if status:
            q = q.eq("status", status.lower())
        if priority:
            q = q.eq("priority", priority.lower())
        result = q.order("created_at", desc=True).execute()
        rows = result.data or []
        return JSONResponse(status_code=200, content={"count": len(rows), "reports": rows})
    except Exception as exc:
        logger.exception("list problem reports error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get("/{report_id}", summary="Get a problem report (Phase 598)",
            responses={200: {}, 404: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def get_problem_report(
    report_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("problem_reports").select("*")
            .eq("tenant_id", tenant_id).eq("id", report_id)
            .limit(1).execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Report '{report_id}' not found."})
        return JSONResponse(status_code=200, content=rows[0])
    except Exception as exc:
        logger.exception("get problem report error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.patch("/{report_id}", summary="Update a problem report (Phase 598 + Phase 650)",
              responses={200: {}, 400: {}, 404: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def update_problem_report(
    report_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict) or not body:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a non-empty JSON object."})

    allowed = {"status", "priority", "resolved_by", "resolution_notes", "description_translated", "maintenance_task_id"}
    update: Dict[str, Any] = {k: v for k, v in body.items() if k in allowed}

    old_status = None
    if "status" in update:
        s = str(update["status"]).lower()
        if s not in _VALID_STATUSES:
            return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                       extra={"detail": f"Invalid status. Must be one of: {sorted(_VALID_STATUSES)}"})
        update["status"] = s
        if s == "resolved":
            import datetime
            update["resolved_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not update:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"No updatable fields. Allowed: {sorted(allowed)}"})

    try:
        db = client if client is not None else _get_supabase_client()

        # Phase 650 — Capture old status for audit
        if "status" in update:
            old_result = db.table("problem_reports").select("status").eq("id", report_id).eq("tenant_id", tenant_id).limit(1).execute()
            if old_result.data:
                old_status = old_result.data[0].get("status")

        result = (
            db.table("problem_reports").update(update)
            .eq("tenant_id", tenant_id).eq("id", report_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Report '{report_id}' not found."})

        # Phase 650 — Emit audit event on status change
        if "status" in update and old_status:
            try:
                from services.audit_writer import write_audit_event
                write_audit_event(
                    tenant_id=tenant_id,
                    actor_id=body.get("resolved_by", tenant_id),
                    action="PROBLEM_REPORT_STATUS_CHANGED",
                    entity_type="problem_report",
                    entity_id=report_id,
                    payload={"from_status": old_status, "to_status": update["status"]},
                    client=db,
                )
            except Exception:
                pass  # best-effort audit

        return JSONResponse(status_code=200, content=rows[0])
    except Exception as exc:
        logger.exception("update problem report error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.post("/{report_id}/photos", summary="Add photo to problem report (Phase 598)",
             responses={201: {}, 400: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def add_report_photo(
    report_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a JSON object."})
    photo_url = str(body.get("photo_url") or "").strip()
    if not photo_url:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'photo_url' is required."})
    row = {"report_id": report_id, "photo_url": photo_url, "caption": body.get("caption")}
    try:
        db = client if client is not None else _get_supabase_client()
        result = db.table("problem_report_photos").insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
        return JSONResponse(status_code=201, content=rows[0])
    except Exception as exc:
        logger.exception("add report photo error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get("/{report_id}/photos", summary="List photos for a problem report (Phase 598)",
            responses={200: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def list_report_photos(
    report_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("problem_report_photos").select("*")
            .eq("report_id", report_id)
            .order("created_at", desc=False).execute()
        )
        rows = result.data or []
        return JSONResponse(status_code=200, content={"report_id": report_id, "count": len(rows), "photos": rows})
    except Exception as exc:
        logger.exception("list report photos error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
