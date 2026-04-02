"""
Phase 223 — Manager Copilot v1: Morning Briefing

Provides the 7AM manager briefing endpoint. Consumes an operations-day
context bundle (Phase 222) and returns a natural-language briefing —
either LLM-generated (when configured) or heuristic-static (fallback).

Design (per ai-strategy.md):
  - AI is explanation and prioritization — never canonical state.
  - LLM result is advisory. Source data (operations context) is truth.
  - Structured output: both the AI narrative AND the raw context signals
    are returned so the frontend can show data even if LLM is down.
  - Approval model: zero-risk (pure read + explain).

Endpoint:
  POST /ai/copilot/morning-briefing
    Request body (optional): { "language": "en" | "th" | "ja" }
    Returns:
      {
        "briefing_text": "...",   ← natural language summary
        "generated_by": "llm" | "heuristic",
        "language": "en",
        "context_signals": { ...operations-day snapshot... },
        "action_items": [...],    ← structured list of prioritized actions
        "generated_at": "...",
      }

LLM:
  Uses services.llm_client.generate().
  Falls back to _build_heuristic_briefing() when LLM is unconfigured
  or returns None (network error, quota exhaustion, etc.).

Prompt engineering:
  System: role = Thai-market hospitality operations copilot.
  User: operations context JSON + structured task list.
  Target output: bullet-point manager briefing in the requested language.

JWT required. Tenant-scoped.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

_SUPPORTED_LANGUAGES = {"en", "th", "ja", "es", "ko"}
_DEFAULT_LANGUAGE = "en"

_LANGUAGE_NAMES = {
    "en": "English",
    "th": "Thai",
    "ja": "Japanese",
    "es": "Spanish",
    "ko": "Korean",
}


# ---------------------------------------------------------------------------
# System prompt (injected once per request)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are the Manager Copilot for iHouse Core, a multi-property hospitality operations platform.
Your role: produce concise, decision-ready morning briefings for duty managers.

Rules:
- Respond ONLY in the requested language.
- Lead with the most urgent items: SLA breaches, overdue tasks, tasks due today, high-activity arrival/departure days.
- Use 3–5 bullet points maximum. Each bullet: 1–2 sentences.
- End with a single "Top Action" line summarizing what the manager should do first.
- Do NOT invent information. Only use the data provided.
- Do NOT mention AI, LLMs, or that you are an AI assistant.
- Do NOT surface scheduled future tasks as operational problems. Only surface tasks that are overdue or due today.
- Tone: professional, calm, direct. Like a well-prepared ops coordinator.
"""


def _build_user_prompt(context: Dict[str, Any], language: str) -> str:
    lang_name = _LANGUAGE_NAMES.get(language, "English")
    ctx_json = json.dumps(context, ensure_ascii=False, indent=2)
    return (
        f"Language: {lang_name}\n\n"
        f"Today's operations context:\n{ctx_json}\n\n"
        f"Write the morning briefing now."
    )


# ---------------------------------------------------------------------------
# Heuristic briefing (no LLM required)
# ---------------------------------------------------------------------------

def _build_heuristic_briefing(context: Dict[str, Any]) -> tuple[str, List[Dict[str, Any]]]:
    """
    Build a deterministic text briefing + action items from the context dict.
    Used when LLM is unconfigured or fails.
    Returns (briefing_text, action_items).

    Phase 1043: uses date-aware task buckets (actionable_now, due_soon, future).
    DLQ removed — not a valid OM signal (global, stale, no OM action path).
    """
    ops = context.get("operations", {})
    tasks = context.get("tasks", {})
    sync = context.get("outbound_sync", {})
    hints = context.get("ai_hints", {})

    today = ops.get("date", "today")
    arrivals = ops.get("arrivals_count", 0)
    departures = ops.get("departures_count", 0)
    cleanings = ops.get("cleanings_due", 0)
    active = ops.get("active_bookings", 0)

    # Phase 1043: date-aware task reading
    actionable_now = tasks.get("actionable_now", 0)   # overdue + due_today
    overdue = tasks.get("overdue", 0)
    due_today = tasks.get("due_today", 0)
    due_soon = tasks.get("due_soon", 0)                # next 3 days
    future = tasks.get("future", 0)                    # beyond 3 days
    by_priority_actionable = tasks.get("by_priority_actionable", {})
    total_open = tasks.get("total_open", 0)

    critical_sla = hints.get("critical_tasks_over_sla", 0)
    sync_degraded = hints.get("sync_degraded", False)
    high_arrival = hints.get("high_arrival_day", False)
    high_departure = hints.get("high_departure_day", False)

    lines = [f"Morning briefing for {today}:"]

    # Arrivals / departures / active stays
    if high_arrival or high_departure:
        lines.append(f"• High-activity day — {arrivals} check-in(s), {departures} check-out(s), {cleanings} cleaning(s) required. {active} active booking(s).")
    else:
        lines.append(f"• {arrivals} check-in(s), {departures} check-out(s), {cleanings} cleaning(s) today. {active} active booking(s).")

    # Critical SLA breach — always surfaces first
    if critical_sla > 0:
        lines.append(f"• ⚠ {critical_sla} CRITICAL task(s) past 5-minute ACK SLA — immediate acknowledgement required.")

    # Phase 1043: date-aware task wording
    if actionable_now > 0:
        high_actionable = by_priority_actionable.get("HIGH", 0) + by_priority_actionable.get("CRITICAL", 0)
        parts = []
        if overdue > 0:
            parts.append(f"{overdue} overdue")
        if due_today > 0:
            parts.append(f"{due_today} due today")
        detail = " + ".join(parts)
        if high_actionable > 0:
            lines.append(f"• {actionable_now} task(s) need attention now ({detail}) — {high_actionable} high priority. Review task queue.")
        else:
            lines.append(f"• {actionable_now} task(s) need attention now ({detail}).")
    elif due_soon > 0:
        lines.append(f"• No tasks overdue or due today. {due_soon} task(s) coming up in the next 3 days.")
    else:
        if total_open > 0:
            lines.append(f"• No tasks need immediate attention. {total_open} task(s) scheduled ahead.")
        else:
            lines.append("• No open tasks.")

    # Outbound sync degraded (tenant-scoped — valid OM signal)
    if sync_degraded:
        rate = sync.get("failure_rate_24h", "?")
        lines.append(f"• ⚠ Outbound sync degraded: {rate:.0%} failure rate in last 24h." if isinstance(rate, float) else "• ⚠ Outbound sync degraded — check provider connections.")

    # Top action — DLQ removed from priority chain
    if critical_sla > 0:
        top_action = f"Top action: Acknowledge {critical_sla} overdue CRITICAL task(s) immediately."
    elif actionable_now > 0:
        top_action = f"Top action: Review {actionable_now} task(s) that need attention today."
    elif high_arrival:
        top_action = "Top action: Confirm check-in preparations for today's arrivals."
    elif sync_degraded:
        top_action = "Top action: Investigate outbound sync failures."
    else:
        top_action = "Top action: Confirm daily operations are on track."

    lines.append(f"\n{top_action}")
    briefing_text = "\n".join(lines)

    # Structured action items — DLQ removed
    action_items: List[Dict[str, Any]] = []
    if critical_sla > 0:
        action_items.append({"priority": "CRITICAL", "action": "ACKNOWLEDGE_TASKS", "description": f"Acknowledge {critical_sla} critical task(s) past SLA"})
    if actionable_now > 0 and not critical_sla:
        action_items.append({"priority": "HIGH", "action": "REVIEW_TASKS_NOW", "description": f"Review {actionable_now} task(s) that are overdue or due today"})
    if sync_degraded:
        action_items.append({"priority": "HIGH", "action": "CHECK_SYNC", "description": "Investigate outbound sync degradation"})
    if high_arrival:
        action_items.append({"priority": "NORMAL", "action": "CONFIRM_CHECKINS", "description": f"Confirm check-in preparations for {arrivals} arrival(s)"})
    if not action_items:
        action_items.append({"priority": "NORMAL", "action": "CONFIRM_OPS", "description": "Review open task queue and confirm daily operations are on track"})

    return briefing_text, action_items


# ---------------------------------------------------------------------------
# Operations-day context helper
# ---------------------------------------------------------------------------

def _get_operations_context(db: Any, tenant_id: str) -> Dict[str, Any]:
    """
    Inline implementation of the operations-day context (mirrors
    Phase 222 GET /ai/context/operations-day, but callable directly
    without HTTP round-trip).

    Phase 1043: DLQ removed from OM context.
    _fetch_dlq_summary is NOT called here — DLQ is a global, unstoped,
    admin-only infrastructure signal with no OM action path.
    The admin endpoint GET /ai/context/operations-day still includes DLQ.
    """
    from api.ai_context_router import (
        _fetch_tenant_operations,
        _fetch_tenant_tasks_summary,
        _fetch_sync_summary,
    )
    ops = _fetch_tenant_operations(db, tenant_id)
    tasks = _fetch_tenant_tasks_summary(db, tenant_id)
    sync = _fetch_sync_summary(db, tenant_id)
    hints = {
        "critical_tasks_over_sla": tasks.get("critical_past_ack_sla", 0),
        "sync_degraded": (
            sync.get("failure_rate_24h") is not None
            and sync.get("failure_rate_24h", 0) > 0.2
        ),
        "high_arrival_day": ops.get("arrivals_count", 0) >= 3,
        "high_departure_day": ops.get("departures_count", 0) >= 3,
    }
    return {"operations": ops, "tasks": tasks, "outbound_sync": sync, "ai_hints": hints}


def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# POST /ai/copilot/morning-briefing
# ---------------------------------------------------------------------------

@router.post(
    "/ai/copilot/morning-briefing",
    tags=["copilot"],
    summary="Manager Copilot — Morning Briefing (Phase 223)",
    description=(
        "Generates a 7AM manager briefing from today's operations context.\\n\\n"
        "**LLM-powered** when `OPENAI_API_KEY` is configured; falls back to "
        "a deterministic heuristic briefing when unconfigured or on LLM error.\\n\\n"
        "**Risk level:** Zero — pure read + explain. No writes.\\n\\n"
        "**Languages:** `en` (English, default), `th` (Thai), "
        "`ja` (Japanese), `es` (Spanish), `ko` (Korean).\\n\\n"
        "**Structured output:** `briefing_text` (narrative) + `action_items` "
        "(prioritized list) + `context_signals` (raw context for frontend rendering).\\n\\n"
        "**Source:** `booking_state`, `tasks`, `ota_dead_letter`, `outbound_sync_log`. "
        "All read-only. JWT required."
    ),
    responses={
        200: {"description": "Morning briefing generated successfully"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def post_morning_briefing(
    language: str = Body(
        default=_DEFAULT_LANGUAGE,
        description="Language code: 'en', 'th', 'ja', 'es', 'ko'. Default: 'en'.",
        embed=True,
    ),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /ai/copilot/morning-briefing

    Generates the 7AM manager briefing for the authenticated tenant.

    The response always includes:
    - `briefing_text` — the natural language briefing
    - `generated_by` — 'llm' or 'heuristic'
    - `action_items` — structured prioritized action list
    - `context_signals` — raw operations context (for frontend use)
    - `generated_at` — ISO timestamp

    If `OPENAI_API_KEY` is not set, `generated_by` will be 'heuristic'
    and the briefing is constructed deterministically from the context.
    This ensures the endpoint is always usable regardless of LLM config.
    """
    # Normalize and validate language
    lang = str(language or _DEFAULT_LANGUAGE).lower().strip()
    if lang not in _SUPPORTED_LANGUAGES:
        lang = _DEFAULT_LANGUAGE

    try:
        db = client if client is not None else _get_db()
    except Exception as exc:  # noqa: BLE001
        logger.warning("morning_briefing: DB connection failed: %s", exc)
        return make_error_response(500, "INTERNAL_ERROR", "DB unavailable")

    # Get operations context (Phase 222 helpers, called directly)
    try:
        context = _get_operations_context(db, tenant_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("morning_briefing: context build failed: %s", exc)
        return make_error_response(500, "INTERNAL_ERROR", "Context aggregation failed")

    # Attempt LLM briefing
    from services import llm_client

    generated_by = "heuristic"
    briefing_text: Optional[str] = None
    action_items: List[Dict[str, Any]] = []

    if llm_client.is_configured():
        try:
            user_prompt = _build_user_prompt(context, lang)
            briefing_text = llm_client.generate(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            if briefing_text:
                generated_by = "llm"
                # Action items still built heuristically (structured data = always reliable)
                _, action_items = _build_heuristic_briefing(context)
        except Exception as exc:  # noqa: BLE001
            logger.warning("morning_briefing: LLM call failed — falling back: %s", exc)
            briefing_text = None

    if not briefing_text:
        # Static heuristic fallback
        briefing_text, action_items = _build_heuristic_briefing(context)
        generated_by = "heuristic"

    # Phase 230 — AI Audit Trail
    try:
        from services.ai_audit_log import log_ai_interaction
        log_ai_interaction(
            tenant_id=tenant_id,
            endpoint="POST /ai/copilot/morning-briefing",
            request_type="morning_briefing",
            input_summary=f"language={lang}",
            output_summary=(
                f"generated_by={generated_by}, "
                f"action_items={len(action_items)}, "
                f"critical_sla={context.get('ai_hints', {}).get('critical_tasks_over_sla', 0)}"
            ),
            generated_by=generated_by,
            language=lang,
            client=client,
        )
    except Exception:  # noqa: BLE001
        pass

    return JSONResponse(
        status_code=200,
        content={
            "briefing_text": briefing_text,
            "generated_by": generated_by,
            "language": lang,
            "tenant_id": tenant_id,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "action_items": action_items,
            "context_signals": context,
        },
    )
