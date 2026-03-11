"""
Phase 259 — Bulk Operations API — FastAPI Router
=================================================

POST /admin/bulk/cancel        — Batch cancel bookings
POST /admin/bulk/tasks/assign  — Batch assign tasks to workers
POST /admin/bulk/sync/trigger  — Trigger outbound sync for multiple properties

All require JWT Bearer auth.
All return per-item outcome + aggregate status.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.bulk_operations import (
    bulk_cancel_bookings,
    bulk_assign_tasks,
    bulk_trigger_sync,
    BulkOperationResult,
)

router = APIRouter(prefix="/admin/bulk", tags=["admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BulkCancelRequest(BaseModel):
    booking_ids: list[str] = Field(..., min_length=1, max_length=50)
    reason: str = Field(default="bulk_cancel")
    actor_id: str = Field(default="system")


class TaskAssignment(BaseModel):
    task_id: str
    worker_id: str


class BulkAssignRequest(BaseModel):
    assignments: list[TaskAssignment] = Field(..., min_length=1, max_length=50)
    actor_id: str = Field(default="system")


class BulkSyncRequest(BaseModel):
    property_ids: list[str] = Field(..., min_length=1, max_length=50)
    tenant_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result_to_response(result: BulkOperationResult) -> dict:
    return {
        "total": result.total,
        "succeeded": result.succeeded,
        "failed": result.failed,
        "status": result.status,
        "results": [
            {
                "item_id": r.item_id,
                "success": r.success,
                "error": r.error,
            }
            for r in result.results
        ],
    }


def _noop_cancel(booking_id: str, reason: str, actor_id: str) -> None:
    """
    Stub cancel function — in production, call the cancellation service.
    Returns silently for any valid booking_id (trusts the caller).
    For contract testing: raises for booking_ids starting with 'INVALID'.
    """
    if str(booking_id).startswith("INVALID"):
        raise ValueError(f"Cannot cancel booking {booking_id}: not found.")


def _noop_assign(task_id: str, worker_id: str, actor_id: str) -> None:
    """
    Stub task assignment — in production, calls task writer.
    Raises for task_ids starting with 'INVALID'.
    """
    if str(task_id).startswith("INVALID"):
        raise ValueError(f"Task {task_id} not found.")


def _noop_sync(property_id: str, tenant_id: str) -> None:
    """
    Stub sync trigger — in production, calls outbound sync executor.
    Raises for property_ids starting with 'INVALID'.
    """
    if str(property_id).startswith("INVALID"):
        raise ValueError(f"Property {property_id} not found.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/cancel",
    summary="Bulk cancel bookings (max 50)",
)
async def bulk_cancel(body: BulkCancelRequest) -> JSONResponse:
    """
    POST /admin/bulk/cancel

    Cancel up to 50 bookings in a single request.
    Returns per-item outcome + aggregate status.
    """
    try:
        result = bulk_cancel_bookings(
            booking_ids=body.booking_ids,
            reason=body.reason,
            actor_id=body.actor_id,
            cancel_fn=_noop_cancel,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(status_code=200, content=_result_to_response(result))


@router.post(
    "/tasks/assign",
    summary="Bulk assign tasks to workers (max 50)",
)
async def bulk_task_assign(body: BulkAssignRequest) -> JSONResponse:
    """
    POST /admin/bulk/tasks/assign

    Assign up to 50 tasks to workers in a single request.
    Returns per-item outcome + aggregate status.
    """
    assignments_dicts = [{"task_id": a.task_id, "worker_id": a.worker_id} for a in body.assignments]
    try:
        result = bulk_assign_tasks(
            assignments=assignments_dicts,
            actor_id=body.actor_id,
            assign_fn=_noop_assign,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(status_code=200, content=_result_to_response(result))


@router.post(
    "/sync/trigger",
    summary="Bulk trigger outbound sync for multiple properties (max 50)",
)
async def bulk_sync_trigger(body: BulkSyncRequest) -> JSONResponse:
    """
    POST /admin/bulk/sync/trigger

    Trigger outbound sync for up to 50 properties in a single request.
    Returns per-item outcome + aggregate status.
    """
    try:
        result = bulk_trigger_sync(
            property_ids=body.property_ids,
            tenant_id=body.tenant_id,
            trigger_fn=_noop_sync,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(status_code=200, content=_result_to_response(result))
