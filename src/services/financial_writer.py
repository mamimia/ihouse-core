"""
Phase 502 — Financial Write Operations

Provides mutation operations for financial data:
- Record manual payment/adjustment  [writes to booking_financial_facts + audit log]
- Generate owner payout calculation [read + calculate only — NOT persisted]

All writes go through booking_financial_facts and admin_audit_log.

Payout persistence is intentionally deferred.
    generate_payout_record() is a calculation-only function. It reads
    booking_financial_facts, computes revenue/fees/net, and returns a
    dict. It does NOT write to any payout table — no such table exists yet.
    The returned payout_id is a session reference only (not retrievable later).
    Full payout lifecycle (persist, approve, mark paid, query history) is a
    planned future feature and requires a product decision before implementation.

Actor attribution:
    record_manual_payment() accepts an explicit actor_id parameter.
    Callers MUST pass the real user identity from the JWT claim so that
    admin_audit_log entries are traceable to a specific user.
    Do NOT pass hardcoded strings like "frontend" or "system" unless the
    action genuinely originates from an automated process (e.g. a cron job).
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("ihouse.financial_writer")


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def record_manual_payment(
    db: Any,
    tenant_id: str,
    booking_id: str,
    amount: float,
    currency: str = "THB",
    payment_type: str = "manual_adjustment",
    notes: str = "",
    actor_id: str = "unknown",
) -> Dict[str, Any]:
    """
    Record a manual payment or financial adjustment.

    Args:
        actor_id: The real user ID who is making this adjustment. Callers
                  must pass this from jwt_identity so that the audit log
                  entry is traceable. Do not pass "frontend" or hardcoded
                  strings.
    """
    payment_id = f"pay_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    try:
        result = db.table("booking_financial_facts").upsert(
            {
                "booking_id": booking_id,
                "tenant_id": tenant_id,
                "total_gross": amount,
                "currency": currency,
                "provider": payment_type,
                "extracted_at": now.isoformat(),
            },
            on_conflict="booking_id,tenant_id",
        ).execute()

        # Audit — use real actor_id, never a hardcoded placeholder
        try:
            db.table("admin_audit_log").insert({
                "tenant_id": tenant_id,
                "actor_id": actor_id,
                "action": "financial_adjustment",
                "entity_type": "booking",
                "entity_id": booking_id,
                "details": {
                    "payment_id": payment_id,
                    "amount": amount,
                    "currency": currency,
                    "type": payment_type,
                    "notes": notes,
                },
                "performed_at": now.isoformat(),
            }).execute()
        except Exception:
            pass

        return {
            "payment_id": payment_id,
            "booking_id": booking_id,
            "amount": amount,
            "currency": currency,
            "status": "recorded",
        }
    except Exception as exc:
        logger.warning("record_manual_payment failed: %s", exc)
        return {"error": str(exc)}


def generate_payout_record(
    db: Any,
    tenant_id: str,
    property_id: str,
    period_start: str,
    period_end: str,
    mgmt_fee_pct: float = 15.0,
) -> Dict[str, Any]:
    """
    Calculate an owner payout for a given property and period.

    IMPORTANT — CALCULATION ONLY, NOT PERSISTED:
        This function reads from booking_financial_facts and returns a
        calculated dict. It does NOT write to any database table.
        No payout table exists yet. The returned payout_id is a unique
        reference for this response only — it cannot be retrieved later
        because it is never stored.

        Full payout lifecycle (persist → approve → mark paid → query history)
        is a deferred product feature that requires a dedicated payouts table,
        status-transition endpoints, and a product decision on the approval
        workflow before implementation.
    """
    try:
        facts_result = (
            db.table("booking_financial_facts")
            .select("booking_id, total_gross, net_to_property, management_fee")
            .eq("property_id", property_id)
            .gte("extracted_at", period_start)
            .lt("extracted_at", period_end)
            .execute()
        )
        facts = facts_result.data or []
    except Exception as exc:
        return {"error": str(exc)}

    total_gross = sum(float(f.get("total_gross", 0) or 0) for f in facts)
    mgmt_fee = round(total_gross * mgmt_fee_pct / 100, 2)
    net_payout = round(total_gross - mgmt_fee, 2)

    payout = {
        # NOTE: This payout_id is a session reference only.
        # It is NOT stored in any database table and cannot be retrieved later.
        "payout_id": f"payout_{uuid.uuid4().hex[:8]}",
        "tenant_id": tenant_id,
        "property_id": property_id,
        "period_start": period_start,
        "period_end": period_end,
        "total_gross": round(total_gross, 2),
        "management_fee": mgmt_fee,
        "management_fee_pct": mgmt_fee_pct,
        "net_payout": net_payout,
        "bookings_count": len(facts),
        # "calculated" = this is a point-in-time calculation, not a committed record.
        # Do not display this as "pending" to operators — that implies a
        # lifecycle (pending → approved → paid) that does not exist yet.
        "status": "calculated",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return payout
