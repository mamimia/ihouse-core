"""
Phase 225 — Task Recommendation Engine

POST /ai/copilot/task-recommendations

Given the authenticated tenant's open tasks (PENDING + ACKNOWLEDGED),
returns a ranked, role-filtered recommendation list telling workers and
managers *which tasks to tackle next* and *why*.

Design (ai-strategy.md compliance):
    - All ranking logic is deterministic Python. LLM adds natural-language
      rationale only — never changes scores or ordering.
    - Source of truth: `tasks` table (read-only).
    - Zero-risk: pure read + rank + explain. No writes. JWT required.
    - Heuristic path always available (no LLM key required).
    - Same dual-path pattern as Phases 223–224.

Scoring function (deterministic, higher = more urgent):
    BASE SCORE = priority_score + recency_score + sla_score
    where:
        priority_score:
            CRITICAL = 1000
            HIGH     = 500
            MEDIUM   = 200
            LOW      = 50
        sla_score (based on minutes since created_at vs ack_sla_minutes):
            Already past SLA → +800
            ≤ 25% remaining  → +400
            ≤ 50% remaining  → +200
            ≤ 75% remaining  → +100
            else             → 0
        recency_score:
            newer tasks score slightly higher within same priority
            score = max(0, 50 - days_old)  capped at 50

Request body (all optional):
    {
        "worker_role": "CLEANER",          // filter to this role's tasks
        "property_id": "prop-abc",         // filter by property
        "limit": 10,                       // max items (1-50, default 10)
        "language": "en"                   // narrative language
    }

Response:
    {
        "tenant_id": "...",
        "generated_by": "heuristic" | "llm",
        "language": "en",
        "generated_at": "...",
        "filter_applied": {"worker_role": "CLEANER", "property_id": null},
        "total_open_tasks": 24,
        "recommendation_count": 10,
        "recommendations": [
            {
                "rank": 1,
                "task_id": "...",
                "kind": "CLEANING",
                "title": "...",
                "priority": "CRITICAL",
                "status": "PENDING",
                "worker_role": "CLEANER",
                "due_date": "...",
                "property_id": "...",
                "booking_id": "...",
                "score": 1850,
                "score_breakdown": {"priority": 1000, "sla": 800, "recency": 50},
                "sla_status": "BREACHED" | "WARNING" | "OK",
                "minutes_past_sla": 37,      // only if BREACHED
                "rationale": "..."           // LLM or heuristic explanation
            }
        ],
        "summary": "..."  // 1-2 sentence overview of the recommendations
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
# Constants
# ---------------------------------------------------------------------------

_PRIORITY_SCORES = {
    "CRITICAL": 1000,
    "HIGH": 500,
    "MEDIUM": 200,
    "LOW": 50,
}

_SLA_MINUTES = {
    "CRITICAL": 5,
    "HIGH": 15,
    "MEDIUM": 60,
    "LOW": 240,
}

_OPEN_STATUSES = {"PENDING", "ACKNOWLEDGED"}
_VALID_ROLES = {"CLEANER", "PROPERTY_MANAGER", "MAINTENANCE_TECH", "INSPECTOR", "GENERAL_STAFF"}
_VALID_LANGUAGES = {"en", "th", "ja", "es", "ko"}
_DEFAULT_LANGUAGE = "en"
_MAX_LIMIT = 50
_DEFAULT_LIMIT = 10

_PRIORITY_LABELS = {
    "CRITICAL": "critical — 5-minute ACK SLA",
    "HIGH": "urgent — 15-minute ACK SLA",
    "MEDIUM": "normal — 1-hour ACK SLA",
    "LOW": "routine — 4-hour ACK SLA",
}

_KIND_LABELS = {
    "CLEANING": "Cleaning",
    "CHECKIN_PREP": "Check-in prep",
    "CHECKOUT_VERIFY": "Checkout verification",
    "MAINTENANCE": "Maintenance",
    "GENERAL": "General task",
    "GUEST_WELCOME": "Guest welcome",
}

_SYSTEM_PROMPT = """\
You are the Task Recommendation Engine for iHouse Core, a hospitality operations platform.
Your role: help workers and managers understand WHY a task is ranked high and what to do.

Rules:
- Write ONE concise sentence per task (max 25 words).
- Mention the most important reason for ranking (SLA breach, priority, due date imminence).
- Do NOT invent details not present in the task data.
- Do NOT mention AI or that you are a system.
- Tone: direct, operational, professional.
"""

_SYSTEM_PROMPT_SUMMARY = """\
You are a hospitality operations assistant. Write a 1-2 sentence plain-language summary
of the current task situation for a property manager or worker. Be direct and actionable.
Do not mention AI. No more than 40 words.
"""


# ---------------------------------------------------------------------------
# Supabase helper
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Task fetcher
# ---------------------------------------------------------------------------

def _fetch_open_tasks(
    db: Any,
    tenant_id: str,
    worker_role: Optional[str],
    property_id: Optional[str],
) -> List[dict]:
    """Fetch PENDING + ACKNOWLEDGED tasks for tenant, optionally filtered."""
    rows: List[dict] = []
    try:
        for status in _OPEN_STATUSES:
            q = (
                db.table("tasks")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("status", status)
                .order("created_at", desc=False)
                .limit(200)
            )
            if worker_role:
                q = q.eq("worker_role", worker_role)
            if property_id:
                q = q.eq("property_id", property_id)
            result = q.execute()
            rows.extend(result.data or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_open_tasks: %s", exc)
    return rows


# ---------------------------------------------------------------------------
# Scoring engine (purely deterministic)
# ---------------------------------------------------------------------------

def _parse_dt(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _compute_sla(
    task: dict,
    now: datetime,
) -> tuple[str, int, int]:
    """
    Returns (sla_status, minutes_past_sla, sla_score).
    sla_status: "BREACHED" | "WARNING_25" | "WARNING_50" | "WARNING_75" | "OK"
    minutes_past_sla: positive = over SLA, negative = time remaining
    sla_score: +800 breached, +400 ≤25% remaining, +200 ≤50%, +100 ≤75%, else 0
    """
    priority = (task.get("priority") or "MEDIUM").upper()
    sla_minutes = task.get("ack_sla_minutes") or _SLA_MINUTES.get(priority, 60)
    created = _parse_dt(task.get("created_at"))
    if created is None:
        return "OK", 0, 0

    elapsed_minutes = (now - created).total_seconds() / 60
    remaining = sla_minutes - elapsed_minutes
    minutes_past = int(elapsed_minutes - sla_minutes)

    if remaining <= 0:
        return "BREACHED", abs(int(elapsed_minutes - sla_minutes)), 800
    elif remaining / sla_minutes <= 0.25:
        return "WARNING_25", -int(remaining), 400
    elif remaining / sla_minutes <= 0.50:
        return "WARNING_50", -int(remaining), 200
    elif remaining / sla_minutes <= 0.75:
        return "WARNING_75", -int(remaining), 100
    return "OK", -int(remaining), 0


def _recency_score(task: dict, now: datetime) -> int:
    """Newer tasks get up to +50 points (decays 1pt/day)."""
    created = _parse_dt(task.get("created_at"))
    if created is None:
        return 0
    days_old = (now - created).total_seconds() / 86400
    return max(0, int(50 - days_old))


def _score_task(task: dict, now: datetime) -> tuple[dict, dict]:
    """
    Return (scored_task_dict, score_breakdown).
    scored_task_dict includes all scoring fields needed for ranking.
    """
    priority = (task.get("priority") or "MEDIUM").upper()
    priority_score = _PRIORITY_SCORES.get(priority, 200)
    recency = _recency_score(task, now)
    sla_status, minutes_past_sla, sla_score = _compute_sla(task, now)
    total_score = priority_score + sla_score + recency

    breakdown = {
        "priority": priority_score,
        "sla": sla_score,
        "recency": recency,
    }

    scored = {
        **task,
        "_score": total_score,
        "_sla_status": sla_status,
        "_minutes_past_sla": minutes_past_sla,
        "_breakdown": breakdown,
    }
    return scored, breakdown


# ---------------------------------------------------------------------------
# Heuristic rationale builder
# ---------------------------------------------------------------------------

def _sla_label(sla_status: str, minutes: int) -> str:
    if sla_status == "BREACHED":
        h = minutes // 60
        m = minutes % 60
        p = f"{h}h {m}m" if h else f"{m}m"
        return f"ACK SLA breached by {p}"
    if sla_status == "WARNING_25":
        return f"Only {abs(minutes)}m left on ACK SLA — act now"
    if sla_status == "WARNING_50":
        return f"{abs(minutes)}m remaining on ACK SLA"
    if sla_status == "WARNING_75":
        return f"SLA running — {abs(minutes)}m remaining"
    return "Within SLA"


def _build_heuristic_rationale(task: dict) -> str:
    """Single-sentence deterministic rationale for a task."""
    priority = (task.get("priority") or "MEDIUM").upper()
    kind = task.get("kind") or "GENERAL"
    kind_label = _KIND_LABELS.get(kind, kind)
    title = task.get("title") or kind_label
    sla_status = task.get("_sla_status", "OK")
    minutes_past = task.get("_minutes_past_sla", 0)
    due_date = task.get("due_date") or ""

    if sla_status == "BREACHED":
        return f"{_sla_label(sla_status, minutes_past)} — immediate acknowledgement required."
    if sla_status in ("WARNING_25", "WARNING_50"):
        return f"{_sla_label(sla_status, minutes_past)}. {kind_label} task needs attention soon."
    if priority == "CRITICAL":
        return f"CRITICAL priority — 5-minute ACK SLA. Acknowledge and act immediately."
    if priority == "HIGH":
        if due_date:
            return f"Urgent {kind_label.lower()} task due {due_date}. Acknowledge within 15 minutes."
        return f"High-priority {kind_label.lower()} task — 15-minute ACK window."
    if due_date:
        return f"{kind_label} task due {due_date}. Handle in order."
    return f"Scheduled {kind_label.lower()} task. Complete in priority order."


def _build_heuristic_summary(
    total: int,
    recs: List[dict],
    worker_role: Optional[str],
    property_id: Optional[str],
) -> str:
    """1-2 sentence plain-language summary of recommendations."""
    if not recs:
        scope = ""
        if worker_role:
            scope = f" for {worker_role.lower().replace('_', ' ')}"
        if property_id:
            scope += f" at {property_id}"
        return f"No open tasks found{scope}. All clear."

    breached = sum(1 for r in recs if r.get("sla_status") == "BREACHED")
    critical_count = sum(1 for r in recs if r.get("priority") == "CRITICAL")
    top = recs[0]
    top_title = top.get("title") or top.get("kind", "Unknown")

    parts = []
    if breached > 0:
        parts.append(f"{breached} task(s) have breached their ACK SLA — immediate action required.")
    if critical_count > 0 and not breached:
        parts.append(f"{critical_count} CRITICAL task(s) need acknowledgement within 5 minutes.")

    scope = ""
    if worker_role:
        scope = f" for {worker_role.lower().replace('_', ' ')}"

    parts.append(
        f"Top priority{scope}: '{top_title}' (score {top['score']}). "
        f"{len(recs)} recommendation(s) shown from {total} open task(s)."
    )
    return " ".join(parts)


# ---------------------------------------------------------------------------
# POST /ai/copilot/task-recommendations
# ---------------------------------------------------------------------------

@router.post(
    "/ai/copilot/task-recommendations",
    tags=["copilot"],
    summary="Task Recommendation Engine — prioritised task list (Phase 225)",
    description=(
        "Returns a ranked list of open tasks the caller should tackle next.\\n\\n"
        "**Scoring:** Deterministic — priority weight + SLA breach score + recency.\\n\\n"
        "**LLM overlay:** When `OPENAI_API_KEY` is set, each task gets a one-sentence "
        "LLM rationale; otherwise heuristic rationale is used.\\n\\n"
        "**Zero-risk:** Pure read. No writes. JWT required."
    ),
    responses={
        200: {"description": "Ranked task recommendation list"},
        400: {"description": "Invalid request body"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def post_task_recommendations(
    body: Optional[dict] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    if body is None:
        body = {}

    # Validate + normalise inputs
    worker_role: Optional[str] = body.get("worker_role")
    if worker_role and worker_role.upper() not in _VALID_ROLES:
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR,
            f"Invalid worker_role. Allowed: {', '.join(sorted(_VALID_ROLES))}",
        )
    if worker_role:
        worker_role = worker_role.upper()

    property_id: Optional[str] = body.get("property_id")
    limit = int(body.get("limit") or _DEFAULT_LIMIT)
    limit = max(1, min(limit, _MAX_LIMIT))

    raw_lang = (body.get("language") or _DEFAULT_LANGUAGE).lower()
    language = raw_lang if raw_lang in _VALID_LANGUAGES else _DEFAULT_LANGUAGE

    try:
        db = client if client is not None else _get_db()
    except Exception as exc:  # noqa: BLE001
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, str(exc))

    # Fetch open tasks (all, then score + sort)
    rows = _fetch_open_tasks(db, tenant_id, worker_role, property_id)
    total_open = len(rows)

    now = datetime.now(tz=timezone.utc)

    # Score every task
    scored: List[dict] = []
    for row in rows:
        enriched, breakdown = _score_task(row, now)
        scored.append(enriched)

    # Sort by score DESC, then priority weight, then task_id for stable sort
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    scored.sort(
        key=lambda t: (
            -t["_score"],
            priority_order.get((t.get("priority") or "MEDIUM").upper(), 99),
            t.get("task_id", ""),
        )
    )

    top_tasks = scored[:limit]

    # Build recommendation objects with heuristic rationale first
    recommendations: List[Dict[str, Any]] = []
    for i, task in enumerate(top_tasks, start=1):
        sla_status = task["_sla_status"]
        minutes_past = task["_minutes_past_sla"]
        rec: Dict[str, Any] = {
            "rank": i,
            "task_id": task.get("task_id"),
            "kind": task.get("kind"),
            "title": task.get("title"),
            "priority": task.get("priority"),
            "status": task.get("status"),
            "worker_role": task.get("worker_role"),
            "due_date": task.get("due_date"),
            "property_id": task.get("property_id"),
            "booking_id": task.get("booking_id"),
            "score": task["_score"],
            "score_breakdown": task["_breakdown"],
            "sla_status": sla_status,
            "rationale": _build_heuristic_rationale(task),
        }
        if sla_status == "BREACHED":
            rec["minutes_past_sla"] = minutes_past
        recommendations.append(rec)

    # After building heuristic rationale, attempt LLM overlay
    from services import llm_client
    generated_by = "heuristic"

    if llm_client.is_configured() and recommendations:
        import json as _json
        # Build a compact task list for the LLM — top 5 only to cap context
        llm_tasks = [
            {
                "rank": r["rank"],
                "title": r["title"],
                "priority": r["priority"],
                "kind": r["kind"],
                "sla_status": r["sla_status"],
                "score": r["score"],
                "due_date": r.get("due_date"),
                "minutes_past_sla": r.get("minutes_past_sla"),
            }
            for r in recommendations[:5]
        ]
        user_prompt = (
            f"Language: {language}\n"
            f"Worker role filter: {worker_role or 'all'}\n"
            f"Total open tasks: {total_open}\n"
            f"Top {len(llm_tasks)} recommendations:\n"
            f"{_json.dumps(llm_tasks, indent=2)}\n\n"
            "For each task (by rank), write a one-sentence rationale (≤25 words) "
            "explaining why it's ranked where it is. "
            f"Reply as a JSON array of strings in the same order as the tasks. "
            f"Language: {language}."
        )
        raw_response = llm_client.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        if raw_response:
            # Parse JSON array from response
            try:
                import json as _json2
                rationales = _json2.loads(raw_response)
                if isinstance(rationales, list):
                    for idx, rationale in enumerate(rationales):
                        if idx < len(recommendations) and isinstance(rationale, str):
                            recommendations[idx]["rationale"] = rationale.strip()
                    generated_by = "llm"
            except (ValueError, TypeError, KeyError):
                # LLM returned non-JSON — fall back to heuristic rationale (already set)
                logger.warning("task_recommendations: LLM rationale parse failed, using heuristic")

    # Build summary
    summary_heuristic = _build_heuristic_summary(total_open, recommendations, worker_role, property_id)
    summary = summary_heuristic

    if llm_client.is_configured() and generated_by == "llm" and recommendations:
        import json as _json3
        summary_prompt = (
            f"Language: {language}\n"
            f"Total open tasks: {total_open}, showing {len(recommendations)}.\n"
            f"Highest priority: {recommendations[0]['priority']}, "
            f"SLA status: {recommendations[0]['sla_status']}.\n"
            f"Role filter: {worker_role or 'all'}.\n\n"
            "Write a 1-2 sentence plain-language summary for the manager."
        )
        llm_summary = llm_client.generate(
            system_prompt=_SYSTEM_PROMPT_SUMMARY,
            user_prompt=summary_prompt,
        )
        if llm_summary:
            summary = llm_summary

    return JSONResponse(
        status_code=200,
        content={
            "tenant_id": tenant_id,
            "generated_by": generated_by,
            "language": language,
            "generated_at": now.isoformat(),
            "filter_applied": {
                "worker_role": worker_role,
                "property_id": property_id,
            },
            "total_open_tasks": total_open,
            "recommendation_count": len(recommendations),
            "recommendations": recommendations,
            "summary": summary,
        },
    )
