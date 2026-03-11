"""
Phase 259 — Bulk Operations API
================================

Service layer for batch operations across bookings, tasks, and sync triggers.
All-or-nothing validation + per-item outcome reporting.
Max 50 items per batch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


MAX_BATCH_SIZE = 50

BULK_STATUS_OK = "ok"
BULK_STATUS_PARTIAL = "partial"
BULK_STATUS_FAILED = "failed"


@dataclass
class BulkItemResult:
    """Per-item result in a bulk operation."""
    item_id: str
    success: bool
    error: str | None = None


@dataclass
class BulkOperationResult:
    """Aggregate result for a bulk operation."""
    total: int
    succeeded: int
    failed: int
    status: str  # "ok" | "partial" | "failed"
    results: list[BulkItemResult] = field(default_factory=list)


def _aggregate_status(results: list[BulkItemResult]) -> str:
    succeeded = sum(1 for r in results if r.success)
    failed = len(results) - succeeded
    if failed == 0:
        return BULK_STATUS_OK
    if succeeded == 0:
        return BULK_STATUS_FAILED
    return BULK_STATUS_PARTIAL


def _make_result(results: list[BulkItemResult]) -> BulkOperationResult:
    succeeded = sum(1 for r in results if r.success)
    return BulkOperationResult(
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
        status=_aggregate_status(results),
        results=results,
    )


# ---------------------------------------------------------------------------
# Bulk Cancel Bookings
# ---------------------------------------------------------------------------

def bulk_cancel_bookings(
    booking_ids: list[str],
    reason: str,
    actor_id: str,
    cancel_fn: Any,  # callable: (booking_id, reason, actor_id) → None | raises
) -> BulkOperationResult:
    """
    Cancel up to MAX_BATCH_SIZE bookings.

    cancel_fn is injected (Supabase-dependent) — pure logic here.
    Per-item errors are collected; operation continues past failures.
    """
    if len(booking_ids) > MAX_BATCH_SIZE:
        raise ValueError(f"Batch size exceeds maximum of {MAX_BATCH_SIZE}. Got {len(booking_ids)}.")
    if not booking_ids:
        raise ValueError("booking_ids must not be empty.")

    results: list[BulkItemResult] = []
    for bid in booking_ids:
        try:
            cancel_fn(bid, reason, actor_id)
            results.append(BulkItemResult(item_id=bid, success=True))
        except Exception as exc:  # noqa: BLE001
            results.append(BulkItemResult(item_id=bid, success=False, error=str(exc)))

    return _make_result(results)


# ---------------------------------------------------------------------------
# Bulk Task Assignment
# ---------------------------------------------------------------------------

def bulk_assign_tasks(
    assignments: list[dict],  # [{"task_id": str, "worker_id": str}]
    actor_id: str,
    assign_fn: Any,  # callable: (task_id, worker_id, actor_id) → None | raises
) -> BulkOperationResult:
    """
    Assign up to MAX_BATCH_SIZE tasks to workers.

    assignments: list of {"task_id": str, "worker_id": str}
    assign_fn is injected.
    """
    if len(assignments) > MAX_BATCH_SIZE:
        raise ValueError(f"Batch size exceeds maximum of {MAX_BATCH_SIZE}. Got {len(assignments)}.")
    if not assignments:
        raise ValueError("assignments must not be empty.")

    results: list[BulkItemResult] = []
    for item in assignments:
        task_id = item.get("task_id", "")
        worker_id = item.get("worker_id", "")
        try:
            if not task_id or not worker_id:
                raise ValueError("task_id and worker_id are required.")
            assign_fn(task_id, worker_id, actor_id)
            results.append(BulkItemResult(item_id=task_id, success=True))
        except Exception as exc:  # noqa: BLE001
            results.append(BulkItemResult(item_id=task_id or "(missing)", success=False, error=str(exc)))

    return _make_result(results)


# ---------------------------------------------------------------------------
# Bulk Sync Trigger
# ---------------------------------------------------------------------------

def bulk_trigger_sync(
    property_ids: list[str],
    tenant_id: str,
    trigger_fn: Any,  # callable: (property_id, tenant_id) → None | raises
) -> BulkOperationResult:
    """
    Trigger outbound sync for up to MAX_BATCH_SIZE properties.

    trigger_fn is injected.
    """
    if len(property_ids) > MAX_BATCH_SIZE:
        raise ValueError(f"Batch size exceeds maximum of {MAX_BATCH_SIZE}. Got {len(property_ids)}.")
    if not property_ids:
        raise ValueError("property_ids must not be empty.")

    results: list[BulkItemResult] = []
    for pid in property_ids:
        try:
            trigger_fn(pid, tenant_id)
            results.append(BulkItemResult(item_id=pid, success=True))
        except Exception as exc:  # noqa: BLE001
            results.append(BulkItemResult(item_id=pid, success=False, error=str(exc)))

    return _make_result(results)
