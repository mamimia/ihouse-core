"""
Phase 226 — Anomaly Alert Broadcaster

POST /ai/copilot/anomaly-alerts

Cross-domain platform scanner that combines data from three sources:
    1. tasks table  → CRITICAL/HIGH tasks with SLA breaches
    2. booking_financial_facts → financial anomalies (same 7 flags as Phase 224)
    3. booking_state          → low-confidence bookings (PARTIAL/UNKNOWN)

Returns a ranked list of active alerts with severity, domain, message, and
recommended action. LLM adds a one-paragraph platform health summary. Heuristic
fallback always available.

Design (ai-strategy.md compliance):
    - Deterministic detection and severity ranking. LLM narrative only.
    - Source tables: `tasks`, `booking_financial_facts`, `booking_state` (read-only).
    - Zero-risk: no writes. JWT required. Tenant isolation enforced at DB.
    - Same dual-path pattern as Phases 223-225.

Alert severity levels:
    CRITICAL  — CRITICAL tasks breached SLA
    HIGH      — HIGH tasks breached SLA / financial NET_NEGATIVE / COMMISSION_HIGH
    MEDIUM    — PARTIAL confidence bookings / missing net / reconciliation pending
    LOW       — UNKNOWN lifecycle / stale bookings / informational

Response shape:
    {
        "tenant_id": "...",
        "generated_by": "heuristic" | "llm",
        "generated_at": "...",
        "total_alerts": 12,
        "critical_count": 1,
        "high_count": 3,
        "medium_count": 5,
        "low_count": 3,
        "alerts": [
            {
                "alert_id": "task_sla_<task_id>",
                "severity": "CRITICAL",
                "domain": "tasks" | "financial" | "bookings",
                "title": "...",
                "message": "...",
                "recommended_action": "...",
                "reference_id": "<task_id or booking_id>",
                "detected_at": "..."
            }
        ],
        "summary": "...",  // 2-3 sentence platform health narrative
        "health_score": 85   // 0-100 heuristic score (100 = all clear)
    }

Request body (all optional):
    {
        "domains": ["tasks", "financial", "bookings"],  // default: all three
        "severity_filter": "CRITICAL",   // only return >= this severity
        "limit": 20                      // max alerts per domain (default 10, max 50)
    }
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_DOMAINS = {"tasks", "financial", "bookings"}
_ALL_DOMAINS = frozenset(_VALID_DOMAINS)
_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
_VALID_SEVERITIES = set(_SEVERITY_ORDER.keys())

_MAX_LIMIT = 50
_DEFAULT_LIMIT = 10

# SLA minutes by priority (locked — Phase 91)
_SLA_MINUTES = {
    "CRITICAL": 5,
    "HIGH": 15,
    "MEDIUM": 60,
    "LOW": 240,
}

# Financial anomaly severity map
_FINANCIAL_FLAG_SEVERITY = {
    "NET_NEGATIVE": "HIGH",
    "COMMISSION_HIGH": "HIGH",
    "RECONCILIATION_PENDING": "MEDIUM",
    "MISSING_NET_TO_PROPERTY": "MEDIUM",
    "PARTIAL_CONFIDENCE": "MEDIUM",
    "COMMISSION_ZERO": "LOW",
    "UNKNOWN_LIFECYCLE": "LOW",
}

_SYSTEM_PROMPT = """\
You are the Anomaly Alert Broadcaster for iHouse Core, a hospitality operations platform.
Your role: summarise the current platform health in 2-3 plain-language sentences.

Rules:
- Be direct and operational. Do NOT mention AI.
- Mention the number of critical/high alerts if any exist.
- End with one concrete recommendation for the manager.
- Max 60 words total.
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
# Timestamp helpers
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


def _alert_id(*parts: str) -> str:
    raw = ":".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Domain scanner: Tasks
# ---------------------------------------------------------------------------

def _scan_tasks(db: Any, tenant_id: str, limit: int, now: datetime) -> List[Dict]:
    """Find CRITICAL and HIGH tasks that have breached their ACK SLA."""
    alerts: List[Dict] = []
    try:
        result = (
            db.table("tasks")
            .select("task_id,kind,title,priority,status,ack_sla_minutes,created_at,property_id,booking_id,worker_role")
            .eq("tenant_id", tenant_id)
            .in_("status", ["PENDING", "ACKNOWLEDGED"])
            .in_("priority", ["CRITICAL", "HIGH"])
            .order("created_at", desc=False)
            .limit(limit * 2)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("_scan_tasks: %s", exc)
        return alerts

    for row in rows:
        priority = (row.get("priority") or "HIGH").upper()
        sla_minutes = row.get("ack_sla_minutes") or _SLA_MINUTES.get(priority, 60)
        created = _parse_dt(row.get("created_at"))
        if created is None:
            continue
        elapsed_minutes = (now - created).total_seconds() / 60
        if elapsed_minutes <= sla_minutes:
            continue  # SLA not breached — skip

        minutes_past = int(elapsed_minutes - sla_minutes)
        h = minutes_past // 60
        m = minutes_past % 60
        past_str = f"{h}h {m}m" if h else f"{m}m"
        kind_label = (row.get("kind") or "task").replace("_", " ").title()
        title = row.get("title") or kind_label

        alerts.append({
            "alert_id": _alert_id("task_sla", row.get("task_id", "")),
            "severity": priority,
            "domain": "tasks",
            "title": f"SLA Breach: {title}",
            "message": (
                f"{priority} task '{title}' — ACK SLA breached by {past_str}. "
                f"Status: {row.get('status', 'PENDING')}. "
                f"Role: {row.get('worker_role', 'unknown')}."
            ),
            "recommended_action": (
                "Acknowledge immediately."
                if priority == "CRITICAL"
                else "Acknowledge and assign within the next 15 minutes."
            ),
            "reference_id": row.get("task_id"),
            "detected_at": now.isoformat(),
            "_priority_order": _SEVERITY_ORDER.get(priority, 99),
            "_minutes_past_sla": minutes_past,
        })

        if len(alerts) >= limit:
            break

    return alerts


# ---------------------------------------------------------------------------
# Domain scanner: Financial
# ---------------------------------------------------------------------------

def _detect_financial_flags(row: dict) -> List[tuple[str, str]]:
    """
    Returns list of (flag, severity) for a financial record.
    Mirrors the logic from Phase 224 financial_explainer_router.
    """
    flags: List[tuple[str, str]] = []
    confidence = (row.get("source_confidence") or "UNKNOWN").upper()
    net = row.get("net_to_property")
    total = row.get("total_price")
    commission = row.get("ota_commission")

    if confidence in ("PARTIAL",):
        flags.append(("PARTIAL_CONFIDENCE", "MEDIUM"))

    if net is None:
        flags.append(("MISSING_NET_TO_PROPERTY", "MEDIUM"))
    elif net < 0:
        flags.append(("NET_NEGATIVE", "HIGH"))

    if total and commission is not None:
        if total > 0 and (commission / total) > 0.25:
            flags.append(("COMMISSION_HIGH", "HIGH"))
        elif commission == 0:
            flags.append(("COMMISSION_ZERO", "LOW"))

    if confidence == "UNKNOWN" and total is None:
        flags.append(("UNKNOWN_LIFECYCLE", "LOW"))

    if confidence in ("PARTIAL",) and net is None and total:
        flags.append(("RECONCILIATION_PENDING", "MEDIUM"))

    return flags


def _scan_financial(db: Any, tenant_id: str, limit: int, now: datetime) -> List[Dict]:
    """Scan booking_financial_facts for anomalies."""
    alerts: List[Dict] = []
    seen_bookings: Set[str] = set()
    try:
        result = (
            db.table("booking_financial_facts")
            .select("booking_id,provider,currency,total_price,ota_commission,net_to_property,source_confidence,recorded_at")
            .eq("tenant_id", tenant_id)
            .order("recorded_at", desc=True)
            .limit(limit * 4)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("_scan_financial: %s", exc)
        return alerts

    for row in rows:
        booking_id = row.get("booking_id", "")
        if booking_id in seen_bookings:
            continue
        seen_bookings.add(booking_id)

        flags = _detect_financial_flags(row)
        if not flags:
            continue

        worst_severity = min(flags, key=lambda x: _SEVERITY_ORDER.get(x[1], 99))[1]
        flag_names = [f[0] for f in flags]
        flag_label = ", ".join(flag_names[:3])
        provider = row.get("provider") or "OTA"
        net_str = (
            f"{row.get('currency', '')} {row.get('net_to_property', 'n/a')}"
            if row.get("net_to_property") is not None
            else "net missing"
        )

        alerts.append({
            "alert_id": _alert_id("fin", booking_id),
            "severity": worst_severity,
            "domain": "financial",
            "title": f"Financial Anomaly: {provider.title()} booking {booking_id[:12]}",
            "message": (
                f"Booking {booking_id} ({provider}) has {len(flags)} financial flag(s): {flag_label}. "
                f"Net to property: {net_str}."
            ),
            "recommended_action": _financial_recommended_action(flag_names),
            "reference_id": booking_id,
            "detected_at": now.isoformat(),
            "_priority_order": _SEVERITY_ORDER.get(worst_severity, 99),
            "_flags": flag_names,
        })

        if len(alerts) >= limit:
            break

    return alerts


def _financial_recommended_action(flags: List[str]) -> str:
    if "NET_NEGATIVE" in flags:
        return "Investigate negative net payout — check OTA remittance and deductions."
    if "COMMISSION_HIGH" in flags:
        return "Review OTA commission rate — exceeds 25% of gross booking value."
    if "RECONCILIATION_PENDING" in flags or "MISSING_NET_TO_PROPERTY" in flags:
        return "Cross-check OTA statement or manually enter net payout."
    return "Review booking financial record for accuracy."


# ---------------------------------------------------------------------------
# Domain scanner: Bookings (low-confidence)
# ---------------------------------------------------------------------------

def _scan_bookings(db: Any, tenant_id: str, limit: int, now: datetime) -> List[Dict]:
    """Find PARTIAL/UNKNOWN confidence bookings older than 24 hours."""
    alerts: List[Dict] = []
    cutoff = (now - timedelta(hours=24)).isoformat()
    try:
        result = (
            db.table("booking_state")
            .select("booking_id,provider,source_confidence,lifecycle_status,check_in,check_out,updated_at")
            .eq("tenant_id", tenant_id)
            .in_("source_confidence", ["PARTIAL", "UNKNOWN"])
            .lt("updated_at", cutoff)
            .order("updated_at", desc=False)
            .limit(limit)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("_scan_bookings: %s", exc)
        return alerts

    for row in rows:
        confidence = (row.get("source_confidence") or "UNKNOWN").upper()
        severity = "MEDIUM" if confidence == "PARTIAL" else "LOW"
        booking_id = row.get("booking_id", "")
        provider = row.get("provider") or "Unknown OTA"
        updated = _parse_dt(row.get("updated_at"))
        hours_stale = int((now - updated).total_seconds() / 3600) if updated else "?"

        alerts.append({
            "alert_id": _alert_id("booking_conf", booking_id),
            "severity": severity,
            "domain": "bookings",
            "title": f"Low-Confidence Booking: {booking_id[:12]}",
            "message": (
                f"Booking {booking_id} ({provider}) has {confidence} confidence — "
                f"stale for {hours_stale}h. Lifecycle: {row.get('lifecycle_status', 'n/a')}."
            ),
            "recommended_action": (
                "Log in to OTA dashboard and verify booking details to upgrade confidence."
                if confidence == "PARTIAL"
                else "Investigate UNKNOWN booking — possible schema gap or missing webhook."
            ),
            "reference_id": booking_id,
            "detected_at": now.isoformat(),
            "_priority_order": _SEVERITY_ORDER.get(severity, 99),
        })

        if len(alerts) >= limit:
            break

    return alerts


# ---------------------------------------------------------------------------
# Health score
# ---------------------------------------------------------------------------

def _compute_health_score(alerts: List[Dict]) -> int:
    """
    0–100 score. 100 = no alerts. Deductions:
        CRITICAL → -20 each (max -60)
        HIGH     → -10 each (max -30)
        MEDIUM   → -3  each (max -20)
        LOW      → -1  each (max -10)
    """
    deductions = {
        "CRITICAL": (-20, 60),
        "HIGH": (-10, 30),
        "MEDIUM": (-3, 20),
        "LOW": (-1, 10),
    }
    total_deduct = 0
    by_severity: Dict[str, int] = {}
    for a in alerts:
        s = a.get("severity", "LOW")
        by_severity[s] = by_severity.get(s, 0) + 1

    for sev, (per_alert, cap) in deductions.items():
        count = by_severity.get(sev, 0)
        total_deduct += min(count * abs(per_alert), cap)

    return max(0, 100 - total_deduct)


# ---------------------------------------------------------------------------
# Heuristic summary
# ---------------------------------------------------------------------------

def _build_heuristic_summary(
    alerts: List[Dict],
    health_score: int,
    domains: Set[str],
) -> str:
    total = len(alerts)
    critical = sum(1 for a in alerts if a.get("severity") == "CRITICAL")
    high = sum(1 for a in alerts if a.get("severity") == "HIGH")

    if total == 0:
        return f"Platform health: {health_score}/100. All clear — no anomalies detected across {', '.join(sorted(domains))}."

    domain_str = ", ".join(sorted(domains))
    parts: List[str] = [f"Platform health: {health_score}/100."]

    if critical:
        parts.append(
            f"{critical} CRITICAL alert(s) require immediate action — ACK SLA breached."
        )
    if high:
        parts.append(
            f"{high} HIGH-severity alert(s) detected across {domain_str}."
        )
    if not critical and not high:
        parts.append(
            f"{total} low-severity anomaly/anomalies detected. Review at next operational check."
        )

    top = alerts[0]
    parts.append(f"Top issue: {top.get('title', 'Unknown')}.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# POST /ai/copilot/anomaly-alerts
# ---------------------------------------------------------------------------

@router.post(
    "/ai/copilot/anomaly-alerts",
    tags=["copilot"],
    summary="Anomaly Alert Broadcaster — cross-domain platform scanner (Phase 226)",
    description=(
        "Scans tasks (SLA breaches), financial records (anomaly flags), and bookings "
        "(low-confidence) to produce a ranked alert list.\\n\\n"
        "**Severity:** CRITICAL > HIGH > MEDIUM > LOW.\\n\\n"
        "**Health score:** 0–100 heuristic (100 = all clear).\\n\\n"
        "**LLM overlay:** 2-3 sentence platform health summary. Heuristic fallback always.\\n\\n"
        "**Zero-risk:** Read-only. JWT required."
    ),
    responses={
        200: {"description": "Anomaly alert list with health score"},
        400: {"description": "Invalid request body"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def post_anomaly_alerts(
    body: Optional[dict] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    if body is None:
        body = {}

    # Validate domains
    requested_domains = body.get("domains")
    if requested_domains is not None:
        if not isinstance(requested_domains, list):
            return make_error_response(400, ErrorCode.VALIDATION_ERROR, "'domains' must be a list.")
        invalid = set(requested_domains) - _VALID_DOMAINS
        if invalid:
            return make_error_response(
                400, ErrorCode.VALIDATION_ERROR,
                f"Invalid domain(s): {', '.join(sorted(invalid))}. Allowed: tasks, financial, bookings.",
            )
        domains: Set[str] = set(requested_domains)
    else:
        domains = set(_ALL_DOMAINS)

    # Validate severity_filter
    severity_filter = body.get("severity_filter")
    if severity_filter and severity_filter.upper() not in _VALID_SEVERITIES:
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR,
            f"Invalid severity_filter '{severity_filter}'. Allowed: {', '.join(sorted(_VALID_SEVERITIES))}.",
        )
    severity_min_order = _SEVERITY_ORDER.get(severity_filter.upper(), 99) if severity_filter else 99

    limit = int(body.get("limit") or _DEFAULT_LIMIT)
    limit = max(1, min(limit, _MAX_LIMIT))

    try:
        db = client if client is not None else _get_db()
    except Exception as exc:  # noqa: BLE001
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, str(exc))

    now = datetime.now(tz=timezone.utc)
    all_alerts: List[Dict] = []

    # Scan each requested domain
    if "tasks" in domains:
        all_alerts.extend(_scan_tasks(db, tenant_id, limit, now))
    if "financial" in domains:
        all_alerts.extend(_scan_financial(db, tenant_id, limit, now))
    if "bookings" in domains:
        all_alerts.extend(_scan_bookings(db, tenant_id, limit, now))

    # Apply severity filter
    if severity_filter:
        all_alerts = [
            a for a in all_alerts
            if _SEVERITY_ORDER.get(a.get("severity", "LOW"), 99) <= severity_min_order
        ]

    # Sort: severity → minutes_past_sla DESC → alert_id for stable sort
    all_alerts.sort(
        key=lambda a: (
            a["_priority_order"],
            -a.get("_minutes_past_sla", 0),
            a.get("alert_id", ""),
        )
    )

    # Strip internal fields before response
    response_alerts = []
    for a in all_alerts:
        out = {k: v for k, v in a.items() if not k.startswith("_")}
        response_alerts.append(out)

    # Counters
    critical_count = sum(1 for a in response_alerts if a.get("severity") == "CRITICAL")
    high_count = sum(1 for a in response_alerts if a.get("severity") == "HIGH")
    medium_count = sum(1 for a in response_alerts if a.get("severity") == "MEDIUM")
    low_count = sum(1 for a in response_alerts if a.get("severity") == "LOW")
    health_score = _compute_health_score(all_alerts)

    # Build summary — heuristic first, LLM overlay attempt
    summary = _build_heuristic_summary(response_alerts, health_score, domains)
    generated_by = "heuristic"

    from services import llm_client
    if llm_client.is_configured() and response_alerts:
        top_alerts_for_llm = [
            {
                "severity": a["severity"],
                "domain": a["domain"],
                "title": a["title"],
                "message": a["message"],
            }
            for a in response_alerts[:6]
        ]
        import json as _json
        user_prompt = (
            f"Platform health score: {health_score}/100.\n"
            f"Alerts: {len(response_alerts)} total | "
            f"CRITICAL={critical_count} HIGH={high_count} MEDIUM={medium_count} LOW={low_count}.\n"
            f"Top alerts:\n{_json.dumps(top_alerts_for_llm, indent=2)}\n\n"
            "Write a 2-3 sentence plain-language platform health summary for the manager.\n"
            "Be direct. End with one concrete action."
        )
        llm_summary = llm_client.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        if llm_summary:
            summary = llm_summary
            generated_by = "llm"

    # Phase 230 — AI Audit Trail
    try:
        from services.ai_audit_log import log_ai_interaction
        log_ai_interaction(
            tenant_id=tenant_id,
            endpoint="POST /ai/copilot/anomaly-alerts",
            request_type="anomaly_alerts",
            input_summary=(
                f"domains={','.join(sorted(domains))}, "
                f"severity_filter={severity_filter or 'all'}, "
                f"limit={limit}"
            ),
            output_summary=(
                f"generated_by={generated_by}, "
                f"total_alerts={len(response_alerts)}, "
                f"health_score={health_score}, "
                f"critical={critical_count}"
            ),
            generated_by=generated_by,
            client=client,
        )
    except Exception:  # noqa: BLE001
        pass

    return JSONResponse(
        status_code=200,
        content={
            "tenant_id": tenant_id,
            "generated_by": generated_by,
            "generated_at": now.isoformat(),
            "domains_scanned": sorted(domains),
            "total_alerts": len(response_alerts),
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "health_score": health_score,
            "alerts": response_alerts,
            "summary": summary,
        },
    )
