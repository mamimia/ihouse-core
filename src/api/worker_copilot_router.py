"""
Phase 231 — Worker Task Copilot

POST /ai/copilot/worker-assist

Provides contextual assistance for a field worker executing a task.
Given a task_id, fetches all relevant context from the DB and returns
a structured assist card for the worker to reference on their mobile device.

Assist card includes:
  - Task context (kind, priority, urgency, due_date, title)
  - Property instructions (access code, Wi-Fi, entry info, key rules)
  - Guest context (guest name, language, check-in/out dates)
  - Recent task history (last 5 completions at same property)
  - Priority justification (human-readable reason for urgency)
  - Assist narrative (heuristic bullet list or LLM natural-language overlay)

Design (ai-strategy.md):
  - LLM overlay when OPENAI_API_KEY set. Heuristic structured fallback always.
  - All context fetched deterministically from tasks + booking_state + properties.
  - JWT required. Tenant isolation enforced at DB level.
  - No writes — read-only endpoint.
  - AI audit log wired (best-effort, Phase 230).

Request body:
    { "task_id": "a1b2c3d4e5f6a7b8" }   // required

Response:
    {
        "tenant_id": "...",
        "task_id": "...",
        "generated_by": "heuristic" | "llm",
        "task_context": { "title", "kind", "priority", "urgency", "due_date", "status" },
        "property_info": { "name", "address", "access_code", "wifi_password",
                           "checkin_time", "checkout_time" },
        "guest_context": { "guest_name", "language", "check_in", "check_out",
                           "total_nights", "provider" },
        "recent_task_history": [ ... ],    // last 5 completed at this property
        "priority_justification": "...",
        "assist_narrative": "...",
        "generated_at": "..."
    }
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# LLM system prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """
You are a concise field operations assistant for a property management company.
You receive structured task context in JSON and produce a brief, actionable
assist narrative for the field worker assigned to this task.

Rules:
- Max 3 short paragraphs or a bullet list of 4-6 items.
- Use the worker's language if provided (default: English).
- Focus on what the worker needs to DO, not background information.
- Mention the access code and Wi-Fi only if present.
- Do not repeat headers or field names verbatim — use natural language.
- Do not mention the system, AI, or any model names.
""".strip()

# ---------------------------------------------------------------------------
# Heuristic narrative builders (per task kind)
# ---------------------------------------------------------------------------

_KIND_INTROS: dict[str, str] = {
    "CHECKIN_PREP":    "Prepare the property for guest arrival.",
    "CLEANING":        "Complete a full cleaning of the property.",
    "CHECKOUT_VERIFY": "Inspect the property after guest departure.",
    "MAINTENANCE":     "Carry out the required maintenance work.",
    "GENERAL":         "Complete the assigned general task.",
    "GUEST_WELCOME":   "Set up a welcome experience for the arriving guest.",
}


def _build_heuristic_narrative(
    task: dict,
    property_info: dict,
    guest_context: dict,
    recent_history: list[dict],
) -> str:
    """
    Build a deterministic, human-readable assist narrative from structured context.
    Returns a multi-line string (bullet list style).
    """
    kind = task.get("kind", "GENERAL")
    lines: list[str] = [_KIND_INTROS.get(kind, "Complete the assigned task."), ""]

    # Property access
    prop_name = property_info.get("name", "the property")
    access_code = property_info.get("access_code")
    wifi = property_info.get("wifi_password")
    checkin_time = property_info.get("checkin_time")
    checkout_time = property_info.get("checkout_time")
    address = property_info.get("address")

    if address:
        lines.append(f"• Location: {address}")
    if access_code:
        lines.append(f"• Entry code: {access_code}")
    if wifi:
        lines.append(f"• Wi-Fi password: {wifi}")

    # Guest context
    guest_name = guest_context.get("guest_name")
    check_in = guest_context.get("check_in")
    check_out = guest_context.get("check_out")

    if kind == "CHECKIN_PREP" and check_in:
        lines.append(f"• Guest check-in: {check_in}" + (f" at {checkin_time}" if checkin_time else ""))
    elif kind == "CHECKOUT_VERIFY" and check_out:
        lines.append(f"• Guest checked out: {check_out}" + (f" by {checkout_time}" if checkout_time else ""))

    if guest_name and kind in ("CHECKIN_PREP", "GUEST_WELCOME"):
        lines.append(f"• Arriving guest: {guest_name}")

    # Recent history hint
    completed = [h for h in recent_history if h.get("status") == "COMPLETED"]
    if completed:
        last = completed[0]
        lines.append(
            f"• Last completed task here: {last.get('kind', '?')} on {last.get('due_date', '?')}"
        )

    # Priority note
    priority = task.get("priority", "MEDIUM")
    urgency = task.get("urgency", "normal")
    if urgency in ("urgent", "critical"):
        lines.append(f"• ⚠ Priority: {priority} — acknowledge and start promptly.")

    return "\n".join(lines)


def _build_priority_justification(task: dict, guest_context: dict) -> str:
    """Short, human-readable explanation for why this task has its priority."""
    kind = task.get("kind", "GENERAL")
    priority = task.get("priority", "LOW")
    due_date = task.get("due_date", "")
    check_in = guest_context.get("check_in", "")

    base = f"This is a {priority} priority {kind} task"
    if due_date:
        base += f" due {due_date}"
    if kind in ("CHECKIN_PREP", "GUEST_WELCOME") and check_in:
        base += f". Guest arrives {check_in}"
    elif kind == "CHECKOUT_VERIFY":
        base += ". Please verify the property condition before re-listing"
    base += "."
    return base


# ---------------------------------------------------------------------------
# DB fetch helpers
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _fetch_task(db: Any, task_id: str, tenant_id: str) -> Optional[dict]:
    try:
        result = (
            db.table("tasks")
            .select("*")
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:  # noqa: BLE001
        return None


def _fetch_booking(db: Any, booking_id: str, tenant_id: str) -> dict:
    try:
        result = (
            db.table("booking_state")
            .select(
                "booking_id, guest_name, guest_email, check_in, check_out, "
                "lifecycle_status, provider, property_id"
            )
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else {}
    except Exception:  # noqa: BLE001
        return {}


def _fetch_property(db: Any, property_id: str, tenant_id: str) -> dict:
    try:
        result = (
            db.table("properties")
            .select(
                "property_id, name, address, access_code, wifi_password, "
                "checkin_time, checkout_time"
            )
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else {}
    except Exception:  # noqa: BLE001
        return {}


def _fetch_recent_task_history(
    db: Any, property_id: str, tenant_id: str, exclude_task_id: str
) -> list[dict]:
    """Return last 5 COMPLETED tasks at this property (excluding current)."""
    try:
        result = (
            db.table("tasks")
            .select("task_id, kind, status, due_date, title")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .eq("status", "COMPLETED")
            .order("due_date", desc=True)
            .limit(6)
            .execute()
        )
        rows = result.data if result.data else []
        return [r for r in rows if r.get("task_id") != exclude_task_id][:5]
    except Exception:  # noqa: BLE001
        return []


def _total_nights(check_in: str, check_out: str) -> Optional[int]:
    try:
        from datetime import date
        ci = date.fromisoformat(check_in)
        co = date.fromisoformat(check_out)
        return max(0, (co - ci).days)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# POST /ai/copilot/worker-assist
# ---------------------------------------------------------------------------

@router.post(
    "/ai/copilot/worker-assist",
    tags=["copilot"],
    summary="Worker Task Copilot — contextual assist card (Phase 231)",
    responses={
        200: {"description": "Assist card generated"},
        400: {"description": "Missing or invalid task_id"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Task not found for this tenant"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def post_worker_assist(
    body: Optional[dict] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return a contextual assist card for a field worker executing a task.

    **Request body:**
    ```json
    { "task_id": "a1b2c3d4e5f6a7b8" }
    ```

    The response bundles all context the worker needs:
    property access info, guest details, recent task history, and a
    priority justification — with an optional LLM narrative overlay.

    **Read-only.** Never writes to any table.
    Requires JWT (tenant-scoped). All DB queries enforce `tenant_id`.
    """
    # -- validate body --
    if not isinstance(body, dict):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "Request body required")

    task_id = (body.get("task_id") or "").strip()
    if not task_id:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "task_id is required")

    now = datetime.now(tz=timezone.utc)

    try:
        db = client or _get_db()

        # -- fetch task --
        task = _fetch_task(db, task_id, tenant_id)
        if task is None:
            return make_error_response(
                404, ErrorCode.NOT_FOUND, f"Task '{task_id}' not found"
            )

        booking_id = task.get("booking_id", "")
        property_id = task.get("property_id", "")

        # -- fetch supporting context (best-effort, never 500 on failure) --
        booking = _fetch_booking(db, booking_id, tenant_id) if booking_id else {}
        prop = _fetch_property(db, property_id, tenant_id) if property_id else {}
        history = (
            _fetch_recent_task_history(db, property_id, tenant_id, task_id)
            if property_id else []
        )

        # -- shape response sub-objects --
        task_context = {
            "title":    task.get("title", ""),
            "kind":     task.get("kind", ""),
            "priority": task.get("priority", ""),
            "urgency":  task.get("urgency", ""),
            "due_date": task.get("due_date", ""),
            "status":   task.get("status", ""),
        }

        property_info: dict[str, Any] = {
            k: prop.get(k)
            for k in ("name", "address", "access_code", "wifi_password",
                      "checkin_time", "checkout_time")
        }

        check_in = booking.get("check_in", "")
        check_out = booking.get("check_out", "")
        nights = _total_nights(check_in, check_out) if (check_in and check_out) else None
        guest_context: dict[str, Any] = {
            "guest_name":    booking.get("guest_name"),
            "language":      "en",   # default; guest profile integration Phase 236+
            "check_in":      check_in or None,
            "check_out":     check_out or None,
            "total_nights":  nights,
            "provider":      booking.get("provider"),
        }

        priority_justification = _build_priority_justification(task_context, guest_context)

        # -- dual-path: heuristic + LLM overlay --
        generated_by = "heuristic"
        assist_narrative = _build_heuristic_narrative(
            task_context, property_info, guest_context, history
        )

        try:
            from services import llm_client
            if llm_client.is_configured():
                context_block = (
                    f"Task: {task_context}\n"
                    f"Property: {property_info}\n"
                    f"Guest: {guest_context}\n"
                    f"Recent history: {history}\n"
                    f"Priority justification: {priority_justification}"
                )
                llm_text = llm_client.generate(
                    system_prompt=_SYSTEM_PROMPT,
                    user_prompt=context_block,
                )
                if llm_text:
                    assist_narrative = llm_text
                    generated_by = "llm"
        except Exception:  # noqa: BLE001
            pass  # heuristic fallback already set

        # Phase 230 — AI Audit Trail
        try:
            from services.ai_audit_log import log_ai_interaction
            log_ai_interaction(
                tenant_id=tenant_id,
                endpoint="POST /ai/copilot/worker-assist",
                request_type="worker_assist",
                input_summary=f"task_id={task_id}, kind={task_context.get('kind')}, priority={task_context.get('priority')}",
                output_summary=f"generated_by={generated_by}, history_count={len(history)}",
                generated_by=generated_by,
                entity_type="task",
                entity_id=task_id,
                client=db,
            )
        except Exception:  # noqa: BLE001
            pass

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id":             tenant_id,
                "task_id":               task_id,
                "generated_by":          generated_by,
                "task_context":          task_context,
                "property_info":         property_info,
                "guest_context":         guest_context,
                "recent_task_history":   history,
                "priority_justification": priority_justification,
                "assist_narrative":      assist_narrative,
                "generated_at":          now.isoformat(),
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("post_worker_assist error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to generate worker assist")
