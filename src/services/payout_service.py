"""
Phase 1062 — Canonical Payout Persistence Service

This is the authoritative payout layer for iHouse Core.
Prior to this phase, generate_payout_record() in financial_writer.py was
calculation-only — payout_id was a session reference that was never stored.

This service replaces that with real persistence:
  - create_payout()     → calculates from booking_financial_facts + writes to owner_payouts
  - transition_status() → advances lifecycle with full audit trail in payout_events
  - get_payout()        → retrieve a single payout by ID
  - list_payouts()      → list payouts for a property or tenant with optional status filter
  - get_payout_history()→ full event log for a payout

Status lifecycle (enforced as a state machine):
  draft → pending → approved → paid
  draft | pending | approved → voided

Design rules:
  - Calculation snapshot is locked at create time (immutable once committed).
  - All transitions are append-only in payout_events.
  - Uniqueness enforced by DB: one non-voided payout per (tenant, property, period).
  - All functions are sync (match existing service layer pattern).
  - All functions accept an explicit `db` client for testability.
  - Never raises — returns error dict on failure.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ihouse.payout_service")

# Valid status transitions
_TRANSITIONS: Dict[str, List[str]] = {
    "draft":    ["pending", "voided"],
    "pending":  ["approved", "voided"],
    "approved": ["paid", "voided"],
    "paid":     [],       # terminal
    "voided":   [],       # terminal
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_float(val: Any) -> float:
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def _calculate_from_facts(
    db: Any,
    tenant_id: str,
    property_id: str,
    period_start: str,
    period_end: str,
    mgmt_fee_pct: float,
) -> Dict[str, Any]:
    """
    Read booking_financial_facts for the given property+period and return
    a calculation dict.  This is the same arithmetic as the old
    generate_payout_record() but now feeds into a real DB write.
    """
    result = (
        db.table("booking_financial_facts")
        .select("booking_id, total_gross, net_to_property, management_fee, total_price, currency")
        .eq("tenant_id", tenant_id)
        .eq("property_id", property_id)
        .gte("recorded_at", period_start)
        .lt("recorded_at", period_end)
        .execute()
    )
    facts = result.data or []

    # Prefer total_gross; fall back to total_price (naming varies by adapter age)
    gross_total = sum(_to_float(f.get("total_gross") or f.get("total_price")) for f in facts)
    mgmt_fee_amt = round(gross_total * mgmt_fee_pct / 100, 2)
    net_payout = round(gross_total - mgmt_fee_amt, 2)

    currencies = {f.get("currency") for f in facts if f.get("currency")}
    currency = next(iter(currencies), "THB") if len(currencies) == 1 else "THB"

    return {
        "gross_total": round(gross_total, 2),
        "management_fee_pct": mgmt_fee_pct,
        "management_fee_amt": mgmt_fee_amt,
        "net_payout": net_payout,
        "bookings_count": len(facts),
        "currency": currency,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_payout(
    db: Any,
    *,
    tenant_id: str,
    property_id: str,
    period_start: str,
    period_end: str,
    mgmt_fee_pct: float = 0.0,
    actor_id: str,
    notes: str = "",
    initial_status: str = "draft",
) -> Dict[str, Any]:
    """
    Calculate the payout from booking_financial_facts and persist it to owner_payouts.

    Returns the created payout dict or {"error": ...} on failure.

    initial_status: "draft" (default) or "pending" if you want to submit immediately.
    Raises ValueError for invalid initial_status.
    """
    if initial_status not in ("draft", "pending"):
        return {"error": f"Invalid initial_status '{initial_status}' — must be 'draft' or 'pending'"}

    try:
        calc = _calculate_from_facts(
            db, tenant_id, property_id, period_start, period_end, mgmt_fee_pct
        )
    except Exception as exc:
        logger.warning("payout_service.create_payout: fact calculation failed: %s", exc)
        return {"error": f"Failed to calculate payout from financial facts: {exc}"}

    payout_id = str(uuid.uuid4())
    now = _now_iso()

    row = {
        "id": payout_id,
        "tenant_id": tenant_id,
        "property_id": property_id,
        "period_start": period_start,
        "period_end": period_end,
        "currency": calc["currency"],
        "gross_total": calc["gross_total"],
        "management_fee_pct": calc["management_fee_pct"],
        "management_fee_amt": calc["management_fee_amt"],
        "net_payout": calc["net_payout"],
        "bookings_count": calc["bookings_count"],
        "status": initial_status,
        "created_by": actor_id,
        "notes": notes,
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = db.table("owner_payouts").insert(row).execute()
        saved = (result.data or [{}])[0]
    except Exception as exc:
        logger.warning("payout_service.create_payout: DB insert failed: %s", exc)
        return {"error": f"Failed to persist payout: {exc}"}

    # Append creation event
    _append_event(db, payout_id=payout_id, tenant_id=tenant_id,
                  from_status=None, to_status=initial_status, actor_id=actor_id,
                  notes=f"Payout created for {property_id} {period_start}→{period_end}")

    logger.info(
        "payout_service: created payout=%s property=%s period=%s→%s net=%s status=%s",
        payout_id, property_id, period_start, period_end, calc["net_payout"], initial_status,
    )
    return saved


def transition_status(
    db: Any,
    *,
    payout_id: str,
    tenant_id: str,
    to_status: str,
    actor_id: str,
    payment_reference: Optional[str] = None,
    notes: str = "",
) -> Dict[str, Any]:
    """
    Advance payout lifecycle: draft→pending→approved→paid (or any→voided).

    Returns updated payout dict or {"error": ...}.
    """
    # Fetch current payout
    try:
        result = (
            db.table("owner_payouts")
            .select("*")
            .eq("id", payout_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:
        return {"error": f"Failed to fetch payout: {exc}"}

    if not rows:
        return {"error": "payout_not_found", "payout_id": payout_id}

    current = rows[0]
    from_status = current["status"]

    allowed = _TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        return {
            "error": f"Invalid transition '{from_status}' → '{to_status}'",
            "allowed_transitions": allowed,
        }

    update: Dict[str, Any] = {
        "status": to_status,
        "updated_at": _now_iso(),
    }

    if to_status == "approved":
        update["approved_by"] = actor_id
    elif to_status == "paid":
        update["paid_by"] = actor_id
        update["paid_at"] = _now_iso()
        if payment_reference:
            update["payment_reference"] = payment_reference

    try:
        up_result = (
            db.table("owner_payouts")
            .update(update)
            .eq("id", payout_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        updated = (up_result.data or [{}])[0]
    except Exception as exc:
        logger.warning("payout_service.transition_status: DB update failed: %s", exc)
        return {"error": f"Failed to update payout: {exc}"}

    _append_event(db, payout_id=payout_id, tenant_id=tenant_id,
                  from_status=from_status, to_status=to_status, actor_id=actor_id,
                  notes=notes)

    logger.info(
        "payout_service: transition payout=%s %s→%s actor=%s",
        payout_id, from_status, to_status, actor_id,
    )
    return updated


def get_payout(
    db: Any,
    *,
    payout_id: str,
    tenant_id: str,
) -> Optional[Dict[str, Any]]:
    """Return a single payout by ID + tenant. Returns None if not found."""
    try:
        result = (
            db.table("owner_payouts")
            .select("*")
            .eq("id", payout_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.warning("payout_service.get_payout failed: %s", exc)
        return None


def list_payouts(
    db: Any,
    *,
    tenant_id: str,
    property_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    List payouts for a tenant, optionally filtered by property_id and/or status.
    Ordered by period_start DESC (most recent first).
    """
    try:
        q = (
            db.table("owner_payouts")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("period_start", desc=True)
            .limit(limit)
        )
        if property_id:
            q = q.eq("property_id", property_id)
        if status:
            q = q.eq("status", status)
        result = q.execute()
        return result.data or []
    except Exception as exc:
        logger.warning("payout_service.list_payouts failed: %s", exc)
        return []


def get_payout_history(
    db: Any,
    *,
    payout_id: str,
    tenant_id: str,
) -> List[Dict[str, Any]]:
    """Return the full audit trail for a payout, oldest-first."""
    try:
        result = (
            db.table("payout_events")
            .select("*")
            .eq("payout_id", payout_id)
            .eq("tenant_id", tenant_id)
            .order("occurred_at", desc=False)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.warning("payout_service.get_payout_history failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _append_event(
    db: Any,
    *,
    payout_id: str,
    tenant_id: str,
    from_status: Optional[str],
    to_status: str,
    actor_id: str,
    notes: str = "",
) -> None:
    """Append an audit event. Best-effort — never raises."""
    try:
        db.table("payout_events").insert({
            "payout_id": payout_id,
            "tenant_id": tenant_id,
            "from_status": from_status,
            "to_status": to_status,
            "actor_id": actor_id,
            "notes": notes,
            "occurred_at": _now_iso(),
        }).execute()
    except Exception as exc:
        logger.warning("payout_service._append_event failed (non-fatal): %s", exc)
