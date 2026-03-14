"""
Cleaning Task Router — Phases 626–632

Endpoints for cleaning checklist templates, progress tracking,
photo uploads, supply checks, completion blocking, and reference
photo comparison.

Tables used (all created in Phase 600 migration):
    - cleaning_checklist_templates
    - cleaning_task_progress
    - cleaning_photos
    - property_reference_photos  (read-only, for comparison view)
    - tasks  (read for task lookup, update for status transition)

Invariant:
    This router NEVER writes to booking_state, event_log, or
    booking_financial_facts.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ============================================================================
# Phase 626 — Cleaning Checklist Template CRUD
# ============================================================================

@router.post(
    "/properties/{property_id}/cleaning-checklist",
    tags=["cleaning"],
    summary="Create or update cleaning checklist template for a property",
    responses={
        200: {"description": "Template saved"},
        400: {"description": "Invalid request body"},
        401: {"description": "Missing or invalid JWT"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def upsert_cleaning_template(
    property_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """Create or update cleaning checklist template for a property."""
    items = body.get("items")
    if not items or not isinstance(items, list):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "items must be a non-empty list")

    supply_checks = body.get("supply_checks", [])
    name = body.get("name", "Standard Cleaning")

    try:
        db = client or _get_supabase_client()
        row = {
            "tenant_id": tenant_id,
            "property_id": property_id,
            "name": name,
            "items": items,
            "supply_checks": supply_checks,
        }
        db.table("cleaning_checklist_templates").upsert(
            row, on_conflict="tenant_id,property_id"
        ).execute()
        return JSONResponse(status_code=200, content={"saved": True, "property_id": property_id, "item_count": len(items)})
    except Exception as exc:
        logger.exception("upsert_cleaning_template error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to save template")


@router.get(
    "/properties/{property_id}/cleaning-checklist",
    tags=["cleaning"],
    summary="Get cleaning checklist template (property-specific or global fallback)",
    responses={
        200: {"description": "Template object"},
        401: {"description": "Missing or invalid JWT"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_cleaning_template(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Get cleaning checklist template for a property.
    Falls back to tenant global template (property_id IS NULL),
    then to hardcoded default if nothing exists.
    """
    try:
        db = client or _get_supabase_client()

        # Try property-specific first
        result = (
            db.table("cleaning_checklist_templates")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return JSONResponse(status_code=200, content={"template": result.data[0], "source": "property"})

        # Try tenant global (property_id is null)
        global_result = (
            db.table("cleaning_checklist_templates")
            .select("*")
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if global_result.data:
            return JSONResponse(status_code=200, content={"template": global_result.data[0], "source": "global"})

        # Fallback to hardcoded default
        from tasks.cleaning_template_seeder import get_default_template
        default = get_default_template()
        return JSONResponse(status_code=200, content={"template": default, "source": "default"})

    except Exception as exc:
        logger.exception("get_cleaning_template error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to retrieve template")


# ============================================================================
# Phase 628 — Cleaning Progress Tracking
# ============================================================================

@router.post(
    "/tasks/{task_id}/start-cleaning",
    tags=["cleaning"],
    summary="Start cleaning task — creates progress record and links template",
    responses={
        200: {"description": "Cleaning progress started"},
        400: {"description": "Invalid request"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Task not found"},
        409: {"description": "Cleaning already started for this task"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def start_cleaning(
    task_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Start a cleaning task: creates cleaning_task_progress record,
    links to template, initializes checklist_state from template items.
    Sets task status to IN_PROGRESS.
    """
    worker_id = body.get("worker_id", "")
    if not worker_id:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "worker_id is required")

    try:
        db = client or _get_supabase_client()

        # Look up the task
        task_result = (
            db.table("tasks")
            .select("*")
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not task_result.data:
            return make_error_response(404, ErrorCode.NOT_FOUND, f"Task '{task_id}' not found")

        task = task_result.data[0]
        booking_id = task.get("booking_id", "")
        property_id = task.get("property_id", "")

        # Check if progress already exists
        existing = (
            db.table("cleaning_task_progress")
            .select("id")
            .eq("task_id", task_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return make_error_response(409, ErrorCode.CONFLICT, "Cleaning already started for this task")

        # Get template
        template_result = (
            db.table("cleaning_checklist_templates")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        template_id = None
        template_data = None
        if template_result.data:
            template_data = template_result.data[0]
            template_id = template_data.get("id")
        else:
            # Fallback to default
            from tasks.cleaning_template_seeder import get_default_template
            template_data = get_default_template()

        # Build initial checklist state
        items = template_data.get("items", [])
        checklist_state = [
            {"room": it.get("room"), "label": it.get("label"), "done": False, "requires_photo": it.get("requires_photo", False)}
            for it in items
        ]
        supply_items = template_data.get("supply_checks", [])
        supply_state = [
            {"item": s.get("item"), "label": s.get("label"), "status": "unchecked"}
            for s in supply_items
        ]

        progress_row = {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "booking_id": booking_id,
            "property_id": property_id,
            "template_id": template_id,
            "checklist_state": checklist_state,
            "supply_state": supply_state,
            "all_photos_taken": False,
            "all_items_done": False,
            "all_supplies_ok": False,
            "worker_id": worker_id,
        }
        insert_result = db.table("cleaning_task_progress").insert(progress_row).execute()

        # Update task status to IN_PROGRESS
        now = datetime.now(tz=timezone.utc).isoformat()
        db.table("tasks").update({"status": "IN_PROGRESS", "updated_at": now}).eq("task_id", task_id).eq("tenant_id", tenant_id).execute()

        progress_id = insert_result.data[0]["id"] if insert_result.data else None
        return JSONResponse(status_code=200, content={
            "started": True,
            "progress_id": progress_id,
            "task_id": task_id,
            "checklist_items": len(checklist_state),
            "supply_checks": len(supply_state),
        })

    except Exception as exc:
        logger.exception("start_cleaning error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to start cleaning")


@router.patch(
    "/tasks/{task_id}/cleaning-progress",
    tags=["cleaning"],
    summary="Update cleaning checklist progress",
    responses={
        200: {"description": "Progress updated"},
        400: {"description": "Invalid body"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "No cleaning progress for this task"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def update_cleaning_progress(
    task_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Update checklist_state: mark individual items as done/not done.
    Body: {"items": [{"index": 0, "done": true}, ...]}
    Recalculates all_items_done flag.
    """
    items_update = body.get("items")
    if not items_update or not isinstance(items_update, list):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "items must be a non-empty list of {index, done}")

    try:
        db = client or _get_supabase_client()

        result = (
            db.table("cleaning_task_progress")
            .select("*")
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return make_error_response(404, ErrorCode.NOT_FOUND, f"No cleaning progress for task '{task_id}'")

        progress = result.data[0]
        checklist_state = progress.get("checklist_state", [])

        # Apply updates
        for update in items_update:
            idx = update.get("index")
            done = update.get("done", False)
            if isinstance(idx, int) and 0 <= idx < len(checklist_state):
                checklist_state[idx]["done"] = done

        all_items_done = all(item.get("done", False) for item in checklist_state)

        db.table("cleaning_task_progress").update({
            "checklist_state": checklist_state,
            "all_items_done": all_items_done,
        }).eq("task_id", task_id).eq("tenant_id", tenant_id).execute()

        return JSONResponse(status_code=200, content={
            "updated": True,
            "all_items_done": all_items_done,
            "items_completed": sum(1 for i in checklist_state if i.get("done")),
            "items_total": len(checklist_state),
        })

    except Exception as exc:
        logger.exception("update_cleaning_progress error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to update progress")


# ============================================================================
# Phase 629 — Room Photo Upload
# ============================================================================

@router.post(
    "/tasks/{task_id}/cleaning-photos",
    tags=["cleaning"],
    summary="Upload a cleaning photo for a specific room",
    responses={
        201: {"description": "Photo recorded"},
        400: {"description": "Missing fields"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "No cleaning progress for this task"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def add_cleaning_photo(
    task_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Upload a cleaning verification photo for a room.
    Body: {"room_label": "bedroom_1", "photo_url": "https://...", "taken_by": "WRK-001"}
    Recalculates all_photos_taken flag.
    """
    room_label = body.get("room_label", "")
    photo_url = body.get("photo_url", "")
    taken_by = body.get("taken_by", "")

    if not room_label or not photo_url:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "room_label and photo_url are required")

    try:
        db = client or _get_supabase_client()

        # Get progress
        progress_result = (
            db.table("cleaning_task_progress")
            .select("*")
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not progress_result.data:
            return make_error_response(404, ErrorCode.NOT_FOUND, f"No cleaning progress for task '{task_id}'")

        progress = progress_result.data[0]
        progress_id = progress["id"]

        # Insert photo
        photo_row = {
            "progress_id": progress_id,
            "room_label": room_label,
            "photo_url": photo_url,
            "taken_by": taken_by or None,
        }
        db.table("cleaning_photos").insert(photo_row).execute()

        # Check if all required rooms have photos
        checklist = progress.get("checklist_state", [])
        rooms_needing_photos = {it["room"] for it in checklist if it.get("requires_photo")}

        photos_result = (
            db.table("cleaning_photos")
            .select("room_label")
            .eq("progress_id", progress_id)
            .execute()
        )
        rooms_with_photos = {p["room_label"] for p in (photos_result.data or [])}
        all_photos_taken = rooms_needing_photos.issubset(rooms_with_photos)

        db.table("cleaning_task_progress").update({
            "all_photos_taken": all_photos_taken,
        }).eq("id", progress_id).execute()

        return JSONResponse(status_code=201, content={
            "saved": True,
            "room_label": room_label,
            "all_photos_taken": all_photos_taken,
        })

    except Exception as exc:
        logger.exception("add_cleaning_photo error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to save cleaning photo")


# ============================================================================
# Phase 630 — Supply Check
# ============================================================================

@router.patch(
    "/tasks/{task_id}/supply-check",
    tags=["cleaning"],
    summary="Update supply check status for cleaning task",
    responses={
        200: {"description": "Supply state updated"},
        400: {"description": "Invalid body"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "No cleaning progress for this task"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def update_supply_check(
    task_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Update supply check state.
    Body: {"supplies": [{"index": 0, "status": "ok"}, {"index": 1, "status": "low"}, ...]}
    Valid statuses: "ok", "low", "empty", "unchecked"
    Recalculates all_supplies_ok flag.
    If any item = 'empty' → returns alert flag.
    """
    supplies_update = body.get("supplies")
    if not supplies_update or not isinstance(supplies_update, list):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "supplies must be a non-empty list of {index, status}")

    valid_statuses = {"ok", "low", "empty", "unchecked"}

    try:
        db = client or _get_supabase_client()

        result = (
            db.table("cleaning_task_progress")
            .select("*")
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return make_error_response(404, ErrorCode.NOT_FOUND, f"No cleaning progress for task '{task_id}'")

        progress = result.data[0]
        supply_state = progress.get("supply_state", [])

        for update in supplies_update:
            idx = update.get("index")
            status = update.get("status", "unchecked")
            if status not in valid_statuses:
                return make_error_response(400, ErrorCode.VALIDATION_ERROR, f"Invalid supply status '{status}'. Must be one of: {', '.join(sorted(valid_statuses))}")
            if isinstance(idx, int) and 0 <= idx < len(supply_state):
                supply_state[idx]["status"] = status

        all_supplies_ok = all(s.get("status") == "ok" for s in supply_state)
        has_empty = any(s.get("status") == "empty" for s in supply_state)

        db.table("cleaning_task_progress").update({
            "supply_state": supply_state,
            "all_supplies_ok": all_supplies_ok,
        }).eq("task_id", task_id).eq("tenant_id", tenant_id).execute()

        return JSONResponse(status_code=200, content={
            "updated": True,
            "all_supplies_ok": all_supplies_ok,
            "supply_alert": has_empty,
            "empty_items": [s["item"] for s in supply_state if s.get("status") == "empty"],
        })

    except Exception as exc:
        logger.exception("update_supply_check error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to update supply check")


# ============================================================================
# Phase 631 — Cleaning Task Complete (Blocking)
# ============================================================================

@router.post(
    "/tasks/{task_id}/complete-cleaning",
    tags=["cleaning"],
    summary="Complete cleaning task — blocks if pre-conditions not met",
    responses={
        200: {"description": "Task completed"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "No cleaning progress for this task"},
        409: {"description": "Pre-conditions not met — cannot complete"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def complete_cleaning(
    task_id: str,
    body: dict | None = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Complete a cleaning task. All pre-conditions must be met:
    - all_items_done = True
    - all_photos_taken = True
    - all_supplies_ok = True (or force_complete = True in body)

    Returns 409 with details of what's missing if any condition fails.
    """
    force = (body or {}).get("force_complete", False)

    try:
        db = client or _get_supabase_client()

        result = (
            db.table("cleaning_task_progress")
            .select("*")
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return make_error_response(404, ErrorCode.NOT_FOUND, f"No cleaning progress for task '{task_id}'")

        progress = result.data[0]
        blockers = []
        if not progress.get("all_items_done"):
            blockers.append("checklist_incomplete")
        if not progress.get("all_photos_taken"):
            blockers.append("photos_missing")
        if not progress.get("all_supplies_ok") and not force:
            blockers.append("supplies_not_ok")

        if blockers:
            return JSONResponse(status_code=409, content={
                "error": "Pre-conditions not met",
                "blockers": blockers,
                "detail": f"Cannot complete: {', '.join(blockers)}",
            })

        now = datetime.now(tz=timezone.utc).isoformat()
        db.table("cleaning_task_progress").update({
            "completed_at": now,
        }).eq("task_id", task_id).eq("tenant_id", tenant_id).execute()

        # Also complete the task itself
        db.table("tasks").update({
            "status": "COMPLETED",
            "updated_at": now,
        }).eq("task_id", task_id).eq("tenant_id", tenant_id).execute()

        return JSONResponse(status_code=200, content={
            "completed": True,
            "task_id": task_id,
            "completed_at": now,
        })

    except Exception as exc:
        logger.exception("complete_cleaning error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to complete cleaning")


# ============================================================================
# Phase 632 — Reference Photo Comparison View
# ============================================================================

@router.get(
    "/tasks/{task_id}/reference-vs-cleaning",
    tags=["cleaning"],
    summary="Side-by-side reference vs cleaning photos",
    responses={
        200: {"description": "Photo comparison pairs"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "No cleaning progress for this task"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def reference_vs_cleaning(
    task_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return side-by-side pairs of reference photos vs cleaning photos per room.
    Used by checkout worker to compare 'how it should look' vs 'how cleaner left it'.
    """
    try:
        db = client or _get_supabase_client()

        # Get progress
        progress_result = (
            db.table("cleaning_task_progress")
            .select("*")
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not progress_result.data:
            return make_error_response(404, ErrorCode.NOT_FOUND, f"No cleaning progress for task '{task_id}'")

        progress = progress_result.data[0]
        property_id = progress.get("property_id", "")
        progress_id = progress["id"]

        # Get reference photos for this property
        ref_result = (
            db.table("property_reference_photos")
            .select("room_label, photo_url")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .order("display_order")
            .execute()
        )
        ref_by_room: dict[str, str] = {}
        for r in (ref_result.data or []):
            room = r.get("room_label", "")
            if room not in ref_by_room:
                ref_by_room[room] = r.get("photo_url", "")

        # Get cleaning photos
        cleaning_result = (
            db.table("cleaning_photos")
            .select("room_label, photo_url")
            .eq("progress_id", progress_id)
            .execute()
        )
        clean_by_room: dict[str, str] = {}
        for c in (cleaning_result.data or []):
            room = c.get("room_label", "")
            if room not in clean_by_room:
                clean_by_room[room] = c.get("photo_url", "")

        # Build comparison pairs
        all_rooms = sorted(set(ref_by_room) | set(clean_by_room))
        pairs = [
            {
                "room": room,
                "reference_photo": ref_by_room.get(room),
                "cleaning_photo": clean_by_room.get(room),
            }
            for room in all_rooms
        ]

        return JSONResponse(status_code=200, content={
            "task_id": task_id,
            "property_id": property_id,
            "comparisons": pairs,
        })

    except Exception as exc:
        logger.exception("reference_vs_cleaning error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to build comparison")
