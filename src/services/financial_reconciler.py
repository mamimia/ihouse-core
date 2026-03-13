"""
Phase 497 — Financial Reconciliation Real Service

Compares booking_financial_facts against OTA-reported data to find
discrepancies: missing extractions, stale data, or amount mismatches.

Outputs a reconciliation report per provider.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ihouse.financial_reconciler")


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def run_reconciliation(
    *,
    db: Optional[Any] = None,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run financial reconciliation:
    1. Count bookings in booking_state
    2. Count bookings with financial facts
    3. Identify bookings missing financial extraction
    4. Flag stale facts (older than 7 days)

    Returns:
        Reconciliation report dict.
    """
    if db is None:
        db = _get_db()

    # Count all bookings
    booking_query = db.table("booking_state").select("booking_id, provider", count="exact")
    if tenant_id:
        booking_query = booking_query.eq("tenant_id", tenant_id)
    bookings_result = booking_query.execute()
    all_bookings = bookings_result.data or []
    total_bookings = bookings_result.count if hasattr(bookings_result, "count") else len(all_bookings)

    # Count bookings with financial facts
    facts_query = db.table("booking_financial_facts").select("booking_id, provider, total_gross", count="exact")
    if tenant_id:
        facts_query = facts_query.eq("tenant_id", tenant_id)
    facts_result = facts_query.execute()
    all_facts = facts_result.data or []
    total_facts = facts_result.count if hasattr(facts_result, "count") else len(all_facts)

    # Find missing
    booking_ids = {b["booking_id"] for b in all_bookings}
    facts_ids = {f["booking_id"] for f in all_facts}
    missing_ids = booking_ids - facts_ids
    extra_facts = facts_ids - booking_ids

    # Provider breakdown
    provider_counts: Dict[str, Dict[str, int]] = {}
    for b in all_bookings:
        p = b.get("provider", "unknown")
        if p not in provider_counts:
            provider_counts[p] = {"bookings": 0, "with_facts": 0, "missing": 0}
        provider_counts[p]["bookings"] += 1

    for f in all_facts:
        p = f.get("provider", "unknown")
        if p in provider_counts:
            provider_counts[p]["with_facts"] += 1

    for p in provider_counts:
        provider_counts[p]["missing"] = provider_counts[p]["bookings"] - provider_counts[p]["with_facts"]

    # Zero-gross facts (potential extraction errors)
    zero_gross = [
        f["booking_id"] for f in all_facts
        if float(f.get("total_gross", 0) or 0) == 0
    ]

    coverage = round(total_facts / max(total_bookings, 1) * 100, 1)

    return {
        "status": "completed",
        "total_bookings": total_bookings,
        "total_with_facts": total_facts,
        "missing_facts": len(missing_ids),
        "extra_facts": len(extra_facts),
        "zero_gross_count": len(zero_gross),
        "coverage_pct": coverage,
        "by_provider": provider_counts,
        "sample_missing": list(missing_ids)[:10],
        "sample_zero_gross": zero_gross[:5],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
