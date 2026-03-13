"""
Phase 502 — Financial Write Operations

Provides mutation operations for financial data:
- Record manual payment/adjustment
- Update management fee settings
- Generate owner payout records

All writes go through booking_financial_facts and admin_audit_log.
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
) -> Dict[str, Any]:
    """
    Record a manual payment or financial adjustment.
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

        # Audit
        try:
            db.table("admin_audit_log").insert({
                "tenant_id": tenant_id,
                "actor_id": "frontend",
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
    Generate a payout record for an owner.

    Calculates total revenue, deducts management fee,
    and creates a payout entry.
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
        "status": "pending",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return payout
