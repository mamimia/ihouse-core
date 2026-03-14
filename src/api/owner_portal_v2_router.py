"""
Phases 721–726 — Owner Portal & Maintenance
==============================================

721: PUT/GET /owners/{owner_id}/properties/{property_id}/visibility
722: GET /owner-portal/{owner_id}/properties/{property_id}/summary — filtered by visibility
723: Owner summary includes maintenance reports if enabled
724: Owner auth concept (placeholder — uses JWT with role=owner)
725: CRUD /maintenance/specialties + /workers/{id}/specialties
726: GET /workers/{worker_id}/maintenance-tasks — filtered by specialty
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["owner-portal"])
maintenance_router = APIRouter(tags=["maintenance"])


def _get_db() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ===========================================================================
# Phase 721 — Owner Portal: Visibility Toggle API
# ===========================================================================

_DEFAULT_VISIBILITY = {
    "bookings": True,
    "financial_summary": True,
    "occupancy_rates": True,
    "maintenance_reports": False,
    "guest_details": False,
    "task_details": False,
    "worker_info": False,
    "cleaning_photos": False,
}


@router.put("/owners/{owner_id}/properties/{property_id}/visibility",
            summary="Set owner visibility (Phase 721)")
async def set_owner_visibility(
    owner_id: str, property_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    visible_fields = body.get("visible_fields")
    if not isinstance(visible_fields, dict):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "visible_fields must be a JSON object"})

    # Validate keys
    invalid_keys = set(visible_fields.keys()) - set(_DEFAULT_VISIBILITY.keys())
    if invalid_keys:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"Invalid visibility fields: {sorted(invalid_keys)}"})

    try:
        db = client if client is not None else _get_db()
        now = _now_iso()
        row_id = hashlib.sha256(f"VIS:{owner_id}:{property_id}".encode()).hexdigest()[:16]

        # Upsert
        row = {
            "id": row_id,
            "owner_id": owner_id,
            "property_id": property_id,
            "visible_fields": {**_DEFAULT_VISIBILITY, **visible_fields},
            "updated_by": tenant_id,
            "updated_at": now,
        }
        db.table("owner_visibility_settings").upsert(row).execute()

        return JSONResponse(status_code=200, content=row)
    except Exception as exc:
        logger.exception("set_owner_visibility error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


@router.get("/owners/{owner_id}/properties/{property_id}/visibility",
            summary="Get owner visibility (Phase 721)")
async def get_owner_visibility(
    owner_id: str, property_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()
        result = (db.table("owner_visibility_settings").select("*")
                  .eq("owner_id", owner_id).eq("property_id", property_id)
                  .limit(1).execute())
        rows = result.data or []
        if not rows:
            return JSONResponse(status_code=200, content={
                "owner_id": owner_id, "property_id": property_id,
                "visible_fields": _DEFAULT_VISIBILITY,
            })
        return JSONResponse(status_code=200, content=rows[0])
    except Exception as exc:
        logger.exception("get_owner_visibility error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 722 — Owner Portal: Filtered Data API
# ===========================================================================

@router.get("/owner-portal/{owner_id}/properties/{property_id}/summary",
            summary="Owner property summary — filtered (Phase 722)")
async def owner_property_summary(
    owner_id: str, property_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()

        # Get visibility settings
        vis_res = (db.table("owner_visibility_settings").select("visible_fields")
                   .eq("owner_id", owner_id).eq("property_id", property_id)
                   .limit(1).execute())
        vis_rows = vis_res.data or []
        visible = vis_rows[0]["visible_fields"] if vis_rows else _DEFAULT_VISIBILITY

        summary: Dict[str, Any] = {"owner_id": owner_id, "property_id": property_id}

        # Property basic info (always visible)
        try:
            prop = db.table("properties").select("name, address").eq("property_id", property_id).limit(1).execute()
            if prop.data:
                summary["property"] = prop.data[0]
        except Exception:
            pass

        # Bookings
        if visible.get("bookings", True):
            try:
                bookings = (db.table("bookings").select("booking_id, check_in, check_out, status, guest_name")
                            .eq("property_id", property_id)
                            .order("check_in", desc=True).limit(20).execute())
                summary["bookings"] = bookings.data or []
            except Exception:
                summary["bookings"] = []

        # Financial summary
        if visible.get("financial_summary", True):
            try:
                fin = (db.table("booking_financial_facts").select("total_price, management_fee, net_to_property")
                       .eq("property_id", property_id).execute())
                fin_data = fin.data or []
                summary["financial"] = {
                    "total_revenue": sum(f.get("total_price", 0) for f in fin_data),
                    "total_fees": sum(f.get("management_fee", 0) for f in fin_data),
                    "net_to_owner": sum(f.get("net_to_property", 0) for f in fin_data),
                    "booking_count": len(fin_data),
                }
            except Exception:
                summary["financial"] = {}

        # Phase 723 — Maintenance reports
        if visible.get("maintenance_reports", False):
            try:
                reports = (db.table("problem_reports").select("id, category, severity, status, description, created_at")
                           .eq("property_id", property_id)
                           .order("created_at", desc=True).limit(20).execute())
                summary["maintenance_reports"] = reports.data or []
            except Exception:
                summary["maintenance_reports"] = []

        return JSONResponse(status_code=200, content=summary)
    except Exception as exc:
        logger.exception("owner_property_summary error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 725 — Maintenance: Specialist Sub-Types CRUD
# ===========================================================================

@maintenance_router.post("/maintenance/specialties", summary="Create specialist type (Phase 725)")
async def create_specialty(
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    name = str(body.get("name") or "").strip()
    specialty_key = str(body.get("specialty_key") or "").strip().lower()
    description = str(body.get("description") or "").strip() or None

    if not name or not specialty_key:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "name and specialty_key required"})

    try:
        db = client if client is not None else _get_db()
        now = _now_iso()
        spec_id = hashlib.sha256(f"SPEC:{specialty_key}:{tenant_id}".encode()).hexdigest()[:16]
        row = {
            "id": spec_id,
            "tenant_id": tenant_id,
            "name": name,
            "specialty_key": specialty_key,
            "description": description,
            "active": True,
            "created_at": now,
        }
        result = db.table("maintenance_specialties").insert(row).execute()
        rows = result.data or []
        return JSONResponse(status_code=201, content=rows[0] if rows else row)
    except Exception as exc:
        logger.exception("create_specialty error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


@maintenance_router.get("/maintenance/specialties", summary="List specialties (Phase 725)")
async def list_specialties(
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()
        result = db.table("maintenance_specialties").select("*").eq("active", True).order("name").execute()
        rows = result.data or []
        return JSONResponse(status_code=200, content={"count": len(rows), "specialties": rows})
    except Exception as exc:
        logger.exception("list_specialties error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


@maintenance_router.patch("/maintenance/specialties/{specialty_id}", summary="Update specialty (Phase 725)")
async def update_specialty(
    specialty_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    update_fields = {}
    if "name" in body:
        update_fields["name"] = str(body["name"]).strip()
    if "description" in body:
        update_fields["description"] = str(body["description"]).strip() or None
    if "active" in body:
        update_fields["active"] = bool(body["active"])

    if not update_fields:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "No update fields provided"})

    try:
        db = client if client is not None else _get_db()
        result = db.table("maintenance_specialties").update(update_fields).eq("id", specialty_id).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(404, "NOT_FOUND")
        return JSONResponse(status_code=200, content=rows[0])
    except Exception as exc:
        logger.exception("update_specialty error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


@maintenance_router.delete("/maintenance/specialties/{specialty_id}", summary="Deactivate specialty (Phase 725)")
async def deactivate_specialty(
    specialty_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()
        db.table("maintenance_specialties").update({"active": False}).eq("id", specialty_id).execute()
        return JSONResponse(status_code=200, content={"id": specialty_id, "active": False})
    except Exception as exc:
        logger.exception("deactivate_specialty error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# Worker specialties assignment

@maintenance_router.post("/workers/{worker_id}/specialties", summary="Assign specialty to worker (Phase 725)")
async def assign_worker_specialty(
    worker_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    specialty_id = str(body.get("specialty_id") or "").strip()
    if not specialty_id:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "specialty_id required"})

    try:
        db = client if client is not None else _get_db()
        now = _now_iso()
        row_id = hashlib.sha256(f"WS:{worker_id}:{specialty_id}".encode()).hexdigest()[:16]
        db.table("worker_specialties").upsert({
            "id": row_id,
            "worker_id": worker_id,
            "specialty_id": specialty_id,
            "assigned_at": now,
            "assigned_by": tenant_id,
        }).execute()
        return JSONResponse(status_code=201, content={"worker_id": worker_id, "specialty_id": specialty_id})
    except Exception as exc:
        logger.exception("assign_worker_specialty error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


@maintenance_router.get("/workers/{worker_id}/specialties", summary="List worker specialties (Phase 725)")
async def list_worker_specialties(
    worker_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()
        result = db.table("worker_specialties").select("*").eq("worker_id", worker_id).execute()
        rows = result.data or []
        return JSONResponse(status_code=200, content={"count": len(rows), "specialties": rows})
    except Exception as exc:
        logger.exception("list_worker_specialties error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


@maintenance_router.delete("/workers/{worker_id}/specialties/{specialty_id}", summary="Remove worker specialty (Phase 725)")
async def remove_worker_specialty(
    worker_id: str, specialty_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()
        db.table("worker_specialties").delete().eq("worker_id", worker_id).eq("specialty_id", specialty_id).execute()
        return JSONResponse(status_code=200, content={"worker_id": worker_id, "specialty_id": specialty_id, "removed": True})
    except Exception as exc:
        logger.exception("remove_worker_specialty error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 726 — Maintenance: Filtered Task View
# ===========================================================================

@maintenance_router.get("/workers/{worker_id}/maintenance-tasks", summary="Filtered maintenance tasks (Phase 726)")
async def worker_maintenance_tasks(
    worker_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()

        # Check if worker has specialties
        spec_res = db.table("worker_specialties").select("specialty_id").eq("worker_id", worker_id).execute()
        worker_specs = spec_res.data or []

        if not worker_specs:
            # No specialties → return ALL maintenance tasks (single-person mode)
            tasks = (db.table("tasks").select("*")
                     .eq("task_kind", "MAINTENANCE")
                     .neq("status", "canceled")
                     .order("created_at", desc=True)
                     .execute())
            all_tasks = tasks.data or []
            return JSONResponse(status_code=200, content={
                "worker_id": worker_id,
                "mode": "all_tasks",
                "count": len(all_tasks),
                "tasks": all_tasks,
            })

        # Has specialties → filter by matching categories
        spec_ids = [s["specialty_id"] for s in worker_specs]

        # Get specialty keys
        spec_keys_res = db.table("maintenance_specialties").select("specialty_key").in_("id", spec_ids).execute()
        spec_keys = [sk["specialty_key"] for sk in (spec_keys_res.data or [])]

        if not spec_keys:
            return JSONResponse(status_code=200, content={
                "worker_id": worker_id, "mode": "filtered", "count": 0, "tasks": [],
            })

        # Get maintenance tasks matching categories
        tasks = (db.table("tasks").select("*")
                 .eq("task_kind", "MAINTENANCE")
                 .neq("status", "canceled")
                 .in_("category", spec_keys)
                 .order("created_at", desc=True)
                 .execute())
        filtered_tasks = tasks.data or []

        return JSONResponse(status_code=200, content={
            "worker_id": worker_id,
            "mode": "filtered",
            "specialty_keys": spec_keys,
            "count": len(filtered_tasks),
            "tasks": filtered_tasks,
        })
    except Exception as exc:
        logger.exception("worker_maintenance_tasks error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)
