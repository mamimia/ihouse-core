"""
Phase 494 — Task Management Write Operations

Provides mutation operations for tasks from the frontend:
- Create task manually
- Claim/assign task to a worker
- Update task status (e.g., in_progress → completed)
- Add task notes

All writes update the tasks table and write to admin_audit_log.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("ihouse.task_writer_frontend")


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _audit(
    db: Any,
    tenant_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_id: str = "frontend",
    details: Optional[Dict] = None,
) -> None:
    """Best-effort audit log entry."""
    try:
        db.table("admin_audit_log").insert({
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details or {},
            "performed_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as exc:
        logger.warning("audit log write failed: %s", exc)


def create_task(
    db: Any,
    tenant_id: str,
    kind: str,
    property_id: str,
    title: str,
    priority: str = "normal",
    assigned_to: str = "",
    booking_id: str = "",
    notes: str = "",
    due_date: str = "",
) -> Dict[str, Any]:
    """
    Create a task manually from the frontend.
    """
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    row = {
        "task_id": task_id,
        "tenant_id": tenant_id,
        "kind": kind,
        "property_id": property_id,
        "title": title,
        "priority": priority,
        "status": "open",
        "assigned_to": assigned_to or None,
        "booking_id": booking_id or None,
        "notes": notes,
        "due_date": due_date or None,
        "created_at": now.isoformat(),
    }

    try:
        result = db.table("tasks").insert(row).execute()
        saved = result.data[0] if result.data else row
    except Exception as exc:
        logger.warning("create_task failed: %s", exc)
        saved = row

    _audit(db, tenant_id, "task_created", "task", task_id, details={"kind": kind})
    return saved


def claim_task(
    db: Any,
    tenant_id: str,
    task_id: str,
    worker_id: str,
) -> Dict[str, Any]:
    """
    Claim/assign a task to a worker.
    """
    try:
        result = (
            db.table("tasks")
            .update({
                "assigned_to": worker_id,
                "status": "claimed",
                "claimed_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        _audit(db, tenant_id, "task_claimed", "task", task_id,
               actor_id=worker_id, details={"worker_id": worker_id})
        return result.data[0] if result.data else {"task_id": task_id, "status": "claimed"}
    except Exception as exc:
        logger.warning("claim_task failed: %s", exc)
        return {"task_id": task_id, "error": str(exc)}


def update_task_status(
    db: Any,
    tenant_id: str,
    task_id: str,
    new_status: str,
    actor_id: str = "frontend",
) -> Dict[str, Any]:
    """
    Update task status (open → claimed → in_progress → completed).
    """
    valid_statuses = {"open", "claimed", "in_progress", "completed", "canceled"}
    if new_status not in valid_statuses:
        return {"error": f"Invalid status. Must be one of: {valid_statuses}"}

    update = {"status": new_status}
    if new_status == "completed":
        update["completed_at"] = datetime.now(timezone.utc).isoformat()

    try:
        result = (
            db.table("tasks")
            .update(update)
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        _audit(db, tenant_id, f"task_{new_status}", "task", task_id,
               actor_id=actor_id, details={"new_status": new_status})
        return result.data[0] if result.data else {"task_id": task_id, "status": new_status}
    except Exception as exc:
        logger.warning("update_task_status failed: %s", exc)
        return {"task_id": task_id, "error": str(exc)}


def add_task_note(
    db: Any,
    tenant_id: str,
    task_id: str,
    note_text: str,
    author_id: str = "frontend",
) -> Dict[str, Any]:
    """
    Add a note/comment to a task.
    """
    note_id = f"note_{uuid.uuid4().hex[:8]}"
    try:
        result = db.table("task_notes").insert({
            "note_id": note_id,
            "task_id": task_id,
            "tenant_id": tenant_id,
            "author_id": author_id,
            "note_text": note_text,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        return result.data[0] if result.data else {"note_id": note_id}
    except Exception as exc:
        logger.warning("add_task_note failed: %s", exc)
        return {"note_id": note_id, "error": str(exc)}
