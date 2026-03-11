"""
Phase 224 — Financial Explainer

Provides LLM-powered (or heuristic) explanations of booking financial data,
targeting non-technical managers who need to understand what the numbers mean
and what (if anything) requires their attention.

Endpoints:
    GET /ai/copilot/financial/explain/{booking_id}
        — Explain the financial state of a single booking.
          Returns: field breakdown + confidence tier explanation + anomaly flags
          + natural language explanation text + recommended action.

    GET /ai/copilot/financial/reconciliation-summary?period=YYYY-MM
        — Summarise the reconciliation inbox for a period.
          Returns: stats (total checked, exception count, tier breakdown) +
          plain-language narrative per anomaly pattern +
          prioritised action list.

Design (ai-strategy.md compliance):
    - LLM used for explanation only — never for deciding financial values.
    - Source of truth: booking_financial_facts (unchanged).
    - All anomaly detection logic is deterministic Python.
    - LLM adds narrative; structured flags/actions come from code.
    - Zero-risk: pure read + explain. No writes. JWT required.

Source confidence tiers:
    FULL / VERIFIED   → Tier A — trusted, complete payout data from OTA.
    PARTIAL           → Tier B — some fields estimated; confirm with OTA.
    UNKNOWN / absent  → Tier C — unreliable; manual lookup required.

Anomaly flags:
    RECONCILIATION_PENDING  — discrepancy vs OTA statement.
    PARTIAL_CONFIDENCE      — source_confidence = PARTIAL.
    MISSING_NET_TO_PROPERTY — net_to_property is null.
    UNKNOWN_LIFECYCLE       — lifecycle_status cannot be projected.
    COMMISSION_HIGH         — ota_commission > 25% of total_price.
    COMMISSION_ZERO         — ota_commission = 0 (unusual).
    NET_NEGATIVE            — net_to_property < 0 (refund/overpayment).
"""
from __future__ import annotations

import logging
import os
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

_CONFIDENCE_TIER_EXPLANATIONS = {
    "A": (
        "Tier A — Verified. Complete payout data received from the OTA. "
        "These numbers are reliable and can be used for accounting."
    ),
    "B": (
        "Tier B — Partial. Some fields (e.g. commission, net payout) are estimated "
        "or missing. Cross-check with your OTA dashboard before booking this revenue."
    ),
    "C": (
        "Tier C — Unknown. Insufficient data received. These numbers should NOT be "
        "used for financial reporting until manually verified with the OTA."
    ),
}

_CONFIDENCE_TO_TIER = {
    "FULL": "A",
    "VERIFIED": "A",
    "PARTIAL": "B",
    "UNKNOWN": "C",
    "": "C",
}

_LIFECYCLE_LABELS = {
    "PAYOUT_EXPECTED": "Payout expected — booking confirmed, OTA will pay out.",
    "PAYOUT_SENT": "Payout sent — funds transferred to property.",
    "RECONCILIATION_PENDING": (
        "Reconciliation pending — a discrepancy was detected. "
        "Manual review required before this payout can be confirmed."
    ),
    "CANCELED_REFUNDED": "Booking canceled — refund issued to guest.",
    "CANCELED_NO_REFUND": "Booking canceled — no refund (within cancellation policy).",
    "UNKNOWN": "Status unknown — insufficient data to determine payout state.",
}

_COMMISSION_HIGH_THRESHOLD = 0.25  # 25% of total_price
_COMMISSION_ZERO_MIN = 0.01        # ota_commission < this considered zero


# ---------------------------------------------------------------------------
# Supabase helper
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Financial data fetchers
# ---------------------------------------------------------------------------

def _fetch_booking_financial(db: Any, tenant_id: str, booking_id: str) -> Optional[dict]:
    """Fetch latest financial row for a booking. Returns None if not found."""
    try:
        result = (
            db.table("booking_financial_facts")
            .select("*")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .order("recorded_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_booking_financial: %s", exc)
        return None


def _fetch_period_rows_for_reconciliation(db: Any, tenant_id: str, period: str) -> List[dict]:
    """Fetch all rows for a period from booking_financial_facts."""
    try:
        year_s, mon_s = period[:4], period[5:]
        month_start = f"{period}-01"
        year, mon = int(year_s), int(mon_s)
        next_year, next_mon = (year + 1, 1) if mon == 12 else (year, mon + 1)
        month_end = f"{next_year}-{next_mon:02d}-01"
        result = (
            db.table("booking_financial_facts")
            .select("*")
            .eq("tenant_id", tenant_id)
            .gte("recorded_at", month_start)
            .lt("recorded_at", month_end)
            .order("recorded_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_period_rows_for_reconciliation: %s", exc)
        return []


def _dedup_latest(rows: List[dict]) -> List[dict]:
    """Keep only the most-recent row per booking_id (already ordered DESC)."""
    seen: set = set()
    out: List[dict] = []
    for r in rows:
        bid = r.get("booking_id")
        if bid and bid not in seen:
            seen.add(bid)
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# Anomaly detection (deterministic)
# ---------------------------------------------------------------------------

def _compute_tier(confidence: str) -> str:
    return _CONFIDENCE_TO_TIER.get((confidence or "").upper(), "C")


def _project_lifecycle(row: dict) -> str:
    """Minimal lifecycle projection from event_kind + source_confidence."""
    event_kind = (row.get("event_kind") or "BOOKING_CREATED").upper()
    confidence = (row.get("source_confidence") or "").upper()
    net = row.get("net_to_property")
    total = row.get("total_price")

    if "CANCEL" in event_kind:
        refund = row.get("refund_amount") or row.get("fees")
        return "CANCELED_REFUNDED" if refund else "CANCELED_NO_REFUND"

    if confidence == "UNKNOWN" or not total:
        return "UNKNOWN"

    if net is None and confidence == "PARTIAL":
        return "RECONCILIATION_PENDING"

    if net is not None and float(net) >= 0:
        return "PAYOUT_EXPECTED"

    return "UNKNOWN"


def _detect_anomalies(row: dict) -> tuple[List[str], str]:
    """
    Returns (anomaly_flags, lifecycle_status).
    All logic is deterministic — no LLM involvement.
    """
    confidence = (row.get("source_confidence") or "").upper()
    net = row.get("net_to_property")
    total = row.get("total_price")
    commission = row.get("ota_commission")
    lifecycle = _project_lifecycle(row)
    flags: List[str] = []

    if lifecycle == "RECONCILIATION_PENDING":
        flags.append("RECONCILIATION_PENDING")

    if confidence == "PARTIAL":
        flags.append("PARTIAL_CONFIDENCE")

    if net is None:
        flags.append("MISSING_NET_TO_PROPERTY")

    if lifecycle == "UNKNOWN":
        flags.append("UNKNOWN_LIFECYCLE")

    # Commission anomalies (only when total is available and non-zero)
    if total is not None and commission is not None:
        try:
            total_f = float(total)
            comm_f = float(commission)
            if total_f > 0:
                if comm_f / total_f > _COMMISSION_HIGH_THRESHOLD:
                    flags.append("COMMISSION_HIGH")
                elif comm_f < _COMMISSION_ZERO_MIN:
                    flags.append("COMMISSION_ZERO")
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    if net is not None:
        try:
            if float(net) < 0:
                flags.append("NET_NEGATIVE")
        except (TypeError, ValueError):
            pass

    return flags, lifecycle


# ---------------------------------------------------------------------------
# Heuristic explanation builder
# ---------------------------------------------------------------------------

def _monetary(value: Any) -> Optional[str]:
    """Format a monetary value, or None."""
    if value is None:
        return None
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _build_booking_explanation(row: dict, flags: List[str], lifecycle: str) -> str:
    """Build a plain-language summary from financial fields and flags."""
    provider = row.get("provider") or "OTA"
    currency = row.get("currency") or ""
    total = _monetary(row.get("total_price"))
    commission = _monetary(row.get("ota_commission"))
    net = _monetary(row.get("net_to_property"))
    confidence = (row.get("source_confidence") or "UNKNOWN").upper()
    tier = _compute_tier(confidence)
    lifecycle_label = _LIFECYCLE_LABELS.get(lifecycle, lifecycle)

    lines = []
    lines.append(f"Booking via {provider} ({currency}).")

    if total:
        lines.append(f"Total charged to guest: {currency} {total}.")
    if commission:
        lines.append(f"{provider} commission: {currency} {commission}.")
    if net:
        lines.append(f"Net to property: {currency} {net}.")
    else:
        lines.append("Net to property: not yet available.")

    lines.append(f"Payout status: {lifecycle_label}")
    lines.append(f"Data confidence: Tier {tier} — {_CONFIDENCE_TIER_EXPLANATIONS[tier]}")

    if flags:
        lines.append("")
        lines.append("Issues requiring attention:")
        flag_messages = {
            "RECONCILIATION_PENDING": "• Reconciliation pending — verify amounts match OTA statement.",
            "PARTIAL_CONFIDENCE": "• Partial data — some fields estimated; confirm with OTA.",
            "MISSING_NET_TO_PROPERTY": "• Net payout amount is missing — may update after next sync.",
            "UNKNOWN_LIFECYCLE": "• Payout state is unknown — check OTA webhook history.",
            "COMMISSION_HIGH": "• Commission appears unusually high (>25%). Verify rate with OTA.",
            "COMMISSION_ZERO": "• Commission is zero — unusual for this OTA. Verify payout settings.",
            "NET_NEGATIVE": "• Net to property is negative — possible overpayment or refund offset.",
        }
        for f in flags:
            lines.append(flag_messages.get(f, f"• {f}"))

    if not flags:
        lines.append("No anomalies detected. Financials appear clean.")

    return "\n".join(lines)


def _build_recommended_action(flags: List[str], lifecycle: str) -> str:
    """Deterministic recommended action based on flags."""
    if "RECONCILIATION_PENDING" in flags:
        return "Cross-check this booking against your OTA monthly statement and confirm the payout amount."
    if "MISSING_NET_TO_PROPERTY" in flags and "PARTIAL_CONFIDENCE" in flags:
        return "Log in to your OTA dashboard and check the net payout amount for this booking."
    if "MISSING_NET_TO_PROPERTY" in flags:
        return "Wait for next OTA webhook sync. If net_to_property is still missing after 24h, check OTA dashboard."
    if "COMMISSION_HIGH" in flags:
        return "Review your OTA commission rate agreement. This may be a one-off fee or an error."
    if "NET_NEGATIVE" in flags:
        return "Investigate negative net amount — this may indicate a refund offset or payout error."
    if "UNKNOWN_LIFECYCLE" in flags:
        return "Manual OTA lookup required — insufficient data to determine payout state."
    return "No action required. Financials are clean."


# ---------------------------------------------------------------------------
# LLM prompt builders
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_BOOKING = """\
You are the Financial Explainer for iHouse Core, a hospitality operations platform.
Your role: produce concise, plain-language explanations of booking financial data for non-technical managers.

Rules:
- Use simple, clear language. No financial jargon.
- Lead with payout status. Then explain anomalies if any.
- Keep response to 3-4 sentences maximum.
- Do NOT invent or change any numbers from the data provided.
- Do NOT mention AI or that you are a system.
- Tone: professional, calm, direct.
"""

_SYSTEM_PROMPT_RECON = """\
You are the Financial Explainer for iHouse Core, summarizing reconciliation exceptions for a property manager.
Your role: provide a brief, plain-language summary of what needs attention in the financial inbox.

Rules:
- 2-4 bullet points maximum.
- Lead with most urgent issues (Tier C exceptions, then B).
- Be specific about what action to take.
- Do NOT invent numbers. Only use the data provided.
- Do NOT mention AI.
- Tone: professional, direct, actionable.
"""


# ---------------------------------------------------------------------------
# GET /ai/copilot/financial/explain/{booking_id}
# ---------------------------------------------------------------------------

import re as _re  # noqa: E402

@router.get(
    "/ai/copilot/financial/explain/{booking_id}",
    tags=["copilot"],
    summary="Financial Explainer — per-booking explanation (Phase 224)",
    description=(
        "Explains the financial state of a single booking in plain language.\\n\\n"
        "**LLM-powered** when `OPENAI_API_KEY` is configured; deterministic heuristic "
        "explanation otherwise.\\n\\n"
        "Returns: financial field breakdown, confidence tier explanation, anomaly "
        "flags, plain-language `explanation_text`, `recommended_action`, and "
        "`generated_by` ('llm' or 'heuristic').\\n\\n"
        "**Zero-risk:** Pure read. No writes. JWT required."
    ),
    responses={
        200: {"description": "Booking financial explanation"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "No financial data for this booking"},
        500: {"description": "Internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_booking_financial_explanation(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()
    except Exception as exc:  # noqa: BLE001
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, str(exc))

    row = _fetch_booking_financial(db, tenant_id, booking_id)
    if row is None:
        return make_error_response(404, ErrorCode.BOOKING_NOT_FOUND, f"No financial data: {booking_id}")

    flags, lifecycle = _detect_anomalies(row)
    confidence = (row.get("source_confidence") or "UNKNOWN").upper()
    tier = _compute_tier(confidence)

    # Attempt LLM explanation
    from services import llm_client
    generated_by = "heuristic"
    explanation_text: Optional[str] = None

    if llm_client.is_configured():
        import json as _json
        user_prompt = (
            f"Booking ID: {booking_id}\n"
            f"Provider: {row.get('provider')}\n"
            f"Currency: {row.get('currency')}\n"
            f"Total charged: {row.get('total_price')}\n"
            f"OTA commission: {row.get('ota_commission')}\n"
            f"Net to property: {row.get('net_to_property')}\n"
            f"Source confidence: {confidence} (Tier {tier})\n"
            f"Payout lifecycle: {lifecycle}\n"
            f"Anomaly flags: {', '.join(flags) if flags else 'None'}\n\n"
            "Explain this booking's financial state in plain language for a property manager."
        )
        explanation_text = llm_client.generate(
            system_prompt=_SYSTEM_PROMPT_BOOKING,
            user_prompt=user_prompt,
        )
        if explanation_text:
            generated_by = "llm"

    if not explanation_text:
        explanation_text = _build_booking_explanation(row, flags, lifecycle)
        generated_by = "heuristic"

    # Phase 230 — AI Audit Trail
    try:
        from services.ai_audit_log import log_ai_interaction
        log_ai_interaction(
            tenant_id=tenant_id,
            endpoint="GET /ai/copilot/financial/explain/{booking_id}",
            request_type="financial_explain",
            input_summary=f"booking_id={booking_id}",
            output_summary=(
                f"generated_by={generated_by}, "
                f"tier={tier}, flags={len(flags)}, lifecycle={lifecycle}"
            ),
            generated_by=generated_by,
            entity_type="booking",
            entity_id=booking_id,
            client=client,
        )
    except Exception:  # noqa: BLE001
        pass

    return JSONResponse(
        status_code=200,
        content={
            "booking_id": booking_id,
            "tenant_id": tenant_id,
            "generated_by": generated_by,
            "explanation_text": explanation_text,
            "recommended_action": _build_recommended_action(flags, lifecycle),
            "anomaly_flags": flags,
            "confidence_tier": {
                "tier": tier,
                "raw_confidence": confidence,
                "explanation": _CONFIDENCE_TIER_EXPLANATIONS.get(tier, ""),
            },
            "lifecycle_status": lifecycle,
            "lifecycle_label": _LIFECYCLE_LABELS.get(lifecycle, lifecycle),
            "financials": {
                "provider": row.get("provider"),
                "currency": row.get("currency"),
                "total_price": _monetary(row.get("total_price")),
                "ota_commission": _monetary(row.get("ota_commission")),
                "net_to_property": _monetary(row.get("net_to_property")),
                "taxes": _monetary(row.get("taxes")),
                "fees": _monetary(row.get("fees")),
                "recorded_at": row.get("recorded_at"),
                "event_kind": row.get("event_kind"),
            },
        },
    )


# ---------------------------------------------------------------------------
# GET /ai/copilot/financial/reconciliation-summary
# ---------------------------------------------------------------------------

_PERIOD_RE = _re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _build_reconciliation_narrative(stats: dict) -> str:
    """Heuristic narrative for the reconciliation period summary."""
    total = stats["total_checked"]
    exceptions = stats["exception_count"]
    tier_c = stats["tier_c_count"]
    tier_b = stats["tier_b_count"]
    flags_count = stats.get("flags_breakdown", {})

    if exceptions == 0:
        return (
            f"All {total} booking(s) checked for the period are clean. "
            "No reconciliation exceptions. No action required."
        )

    lines = [f"{exceptions} of {total} booking(s) have issues requiring attention."]

    if tier_c > 0:
        lines.append(
            f"• {tier_c} Tier C (critical) — unreliable data, manual OTA lookup required immediately."
        )
    if tier_b > 0:
        lines.append(
            f"• {tier_b} Tier B (partial) — estimated data, cross-check with OTA statements."
        )

    recon_count = flags_count.get("RECONCILIATION_PENDING", 0)
    missing_net = flags_count.get("MISSING_NET_TO_PROPERTY", 0)
    comm_high = flags_count.get("COMMISSION_HIGH", 0)

    if recon_count > 0:
        lines.append(f"• {recon_count} booking(s) have financial discrepancies — reconciliation pending.")
    if missing_net > 0:
        lines.append(f"• {missing_net} booking(s) are missing net payout amounts.")
    if comm_high > 0:
        lines.append(f"• {comm_high} booking(s) show unusually high OTA commission (>25%).")

    return "\n".join(lines)


@router.get(
    "/ai/copilot/financial/reconciliation-summary",
    tags=["copilot"],
    summary="Financial Explainer — period reconciliation summary (Phase 224)",
    description=(
        "Plain-language summary of the reconciliation inbox for a period.\\n\\n"
        "**LLM-powered** when `OPENAI_API_KEY` is configured; heuristic otherwise.\\n\\n"
        "Query params: `period` (YYYY-MM, required).\\n\\n"
        "Returns: stats (total checked, exception count, tier breakdown, flag counts) + "
        "narrative summary + prioritised action list.\\n\\n"
        "**Zero-risk:** Pure read. No writes. JWT required."
    ),
    responses={
        200: {"description": "Reconciliation period summary"},
        400: {"description": "Missing or invalid period"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_reconciliation_summary(
    period: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    # Validate period
    if not period or not _PERIOD_RE.match(period):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "period must be YYYY-MM (e.g. 2026-03)")

    try:
        db = client if client is not None else _get_db()
    except Exception as exc:  # noqa: BLE001
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, str(exc))

    rows = _fetch_period_rows_for_reconciliation(db, tenant_id, period)
    deduped = _dedup_latest(rows)

    # Compute stats over deduped rows
    exception_items: List[Dict[str, Any]] = []
    flags_breakdown: Dict[str, int] = {}
    tier_counts: Dict[str, int] = {"A": 0, "B": 0, "C": 0}

    for row in deduped:
        flags, lifecycle = _detect_anomalies(row)
        if flags:
            tier = _compute_tier((row.get("source_confidence") or "").upper())
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            for f in flags:
                flags_breakdown[f] = flags_breakdown.get(f, 0) + 1
            exception_items.append({
                "booking_id": row.get("booking_id"),
                "provider": row.get("provider"),
                "currency": row.get("currency"),
                "lifecycle": lifecycle,
                "tier": tier,
                "flags": flags,
                "recommended_action": _build_recommended_action(flags, lifecycle),
                "net_to_property": _monetary(row.get("net_to_property")),
            })

    # Sort: C first
    exception_items.sort(key=lambda x: ("C" != x["tier"], x.get("booking_id") or ""))

    stats = {
        "total_checked": len(deduped),
        "exception_count": len(exception_items),
        "tier_a_count": tier_counts.get("A", 0),
        "tier_b_count": tier_counts.get("B", 0),
        "tier_c_count": tier_counts.get("C", 0),
        "flags_breakdown": flags_breakdown,
    }

    # Attempt LLM narrative
    from services import llm_client
    generated_by = "heuristic"
    narrative: Optional[str] = None

    if llm_client.is_configured() and len(deduped) > 0:
        import json as _json
        top_exceptions = exception_items[:5]  # Cap context size
        user_prompt = (
            f"Period: {period}\n"
            f"Stats: {_json.dumps(stats, indent=2)}\n"
            f"Top exceptions: {_json.dumps(top_exceptions, indent=2)}\n\n"
            "Write a concise reconciliation inbox summary for the property manager."
        )
        narrative = llm_client.generate(
            system_prompt=_SYSTEM_PROMPT_RECON,
            user_prompt=user_prompt,
        )
        if narrative:
            generated_by = "llm"

    if not narrative:
        narrative = _build_reconciliation_narrative(stats)
        generated_by = "heuristic"

    # Phase 230 — AI Audit Trail
    try:
        from services.ai_audit_log import log_ai_interaction
        log_ai_interaction(
            tenant_id=tenant_id,
            endpoint="GET /ai/copilot/financial/reconciliation-summary",
            request_type="financial_reconciliation_summary",
            input_summary=f"period={period}",
            output_summary=(
                f"generated_by={generated_by}, "
                f"total_checked={stats['total_checked']}, "
                f"exceptions={stats['exception_count']}"
            ),
            generated_by=generated_by,
            client=client,
        )
    except Exception:  # noqa: BLE001
        pass

    return JSONResponse(
        status_code=200,
        content={
            "period": period,
            "tenant_id": tenant_id,
            "generated_by": generated_by,
            "narrative": narrative,
            "stats": stats,
            "exception_items": exception_items,
        },
    )
