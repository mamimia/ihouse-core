"""
Phase 66 — booking_financial_facts Supabase Writer
Phase 162 — OPERATOR_MANUAL confidence tier support

Persists BookingFinancialFacts to the booking_financial_facts table
after a successful BOOKING_CREATED or BOOKING_AMENDED event, or as an
operator correction (BOOKING_CORRECTED, confidence=OPERATOR_MANUAL).

Rules:
- Best-effort, non-blocking: exceptions are caught and logged to stderr.
- Never raises. Financial write failure must NEVER block canonical ingest.
- Append-only: no UPDATE or DELETE.
- Only called when financial_facts is not None.
- OPERATOR_MANUAL rows are always append-only like all other rows.

Confidence tiers:
  FULL            — all key fields present from OTA payload
  PARTIAL         — some fields missing from OTA payload
  ESTIMATED       — fields inferred / computed
  OPERATOR_MANUAL — operator-entered correction (Phase 162)

Invariant (locked Phase 62+):
  booking_state must NEVER contain financial data.
  booking_financial_facts is a separate projection table.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from typing import Any, Optional

from .financial_extractor import BookingFinancialFacts

# Phase 162: additional confidence tier for operator corrections
CONFIDENCE_OPERATOR_MANUAL = "OPERATOR_MANUAL"


def _decimal_to_str(value: Optional[Decimal]) -> Optional[str]:
    """Convert Decimal to string for Supabase NUMERIC insert."""
    if value is None:
        return None
    return str(value)


def write_financial_facts(
    booking_id: str,
    tenant_id: str,
    event_kind: str,
    facts: BookingFinancialFacts,
    client: Any = None,
) -> None:
    """
    Persist BookingFinancialFacts to booking_financial_facts table.

    Args:
        booking_id:  Canonical booking ID ({source}_{reservation_ref}).
        tenant_id:   Tenant identifier.
        event_kind:  Canonical event kind (e.g. "BOOKING_CREATED").
        facts:       BookingFinancialFacts instance from normalize().
        client:      Optional Supabase client. If None, creates a new client
                     using environment variables.

    This function is best-effort. Any exception is caught, logged to
    stderr, and swallowed — it must never interrupt canonical ingestion.
    """
    try:
        if client is None:
            client = _get_client()

        row = {
            "booking_id": booking_id,
            "tenant_id": tenant_id,
            "provider": facts.provider,
            "total_price": _decimal_to_str(facts.total_price),
            "currency": facts.currency,
            "ota_commission": _decimal_to_str(facts.ota_commission),
            "taxes": _decimal_to_str(facts.taxes),
            "fees": _decimal_to_str(facts.fees),
            "net_to_property": _decimal_to_str(facts.net_to_property),
            "source_confidence": facts.source_confidence,
            "raw_financial_fields": facts.raw_financial_fields,
            "event_kind": event_kind,
        }

        client.table("booking_financial_facts").insert(row).execute()

    except Exception as exc:  # noqa: BLE001
        print(
            f"[financial_writer] WARNING: failed to write financial facts "
            f"for booking_id={booking_id!r}: {exc}",
            file=sys.stderr,
        )


def _get_client() -> Any:
    """Build a Supabase client from environment variables."""
    import os
    from supabase import create_client  # type: ignore[import]

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)
