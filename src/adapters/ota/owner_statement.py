"""
Phase 100 — Owner Statement Foundation

Provides a deterministic, read-only monthly summary of financial facts
per property. Aggregates BookingFinancialFacts instances into a structured
monthly owner statement.

Design rules:
  - Zero writes to any data store. Pure aggregation, no side effects.
  - Does NOT modify booking_state, financial_facts, or canonical envelopes.
  - Deterministic: same inputs → same output, always.
  - Works entirely from in-memory BookingFinancialFacts produced by Phase 65.
  - Multi-currency guard: if entries span >1 currency, totals are None and
    currency is set to "MIXED". No cross-currency arithmetic is performed.
  - BOOKING_CANCELED entries are INCLUDED in the statement entries list
    (for full auditability) but their net_to_property is NOT added to net_total.

Invariant (locked Phase 62+):
  booking_state must NEVER contain financial calculations.

Invariant (Phase 100):
  owner_statement.py is READ-ONLY. No mutations, no DB calls, no IO.

Public API:
  build_owner_statement(property_id, month, facts_with_metadata) -> OwnerStatementSummary
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .financial_extractor import (
    BookingFinancialFacts,
    CONFIDENCE_FULL,
    CONFIDENCE_PARTIAL,
    CONFIDENCE_ESTIMATED,
)
from .payment_lifecycle import project_payment_lifecycle, PaymentLifecycleStatus


# ---------------------------------------------------------------------------
# 1. StatementConfidenceLevel — overall statement quality indicator
# ---------------------------------------------------------------------------

class StatementConfidenceLevel(str, Enum):
    """
    Overall confidence quality of an OwnerStatementSummary.

    Derived from the mix of source_confidence values across all entries.
    """

    VERIFIED = "VERIFIED"
    """All entries have FULL source_confidence. Statement is fully attested."""

    MIXED = "MIXED"
    """Mix of FULL and ESTIMATED entries. Most data is reliable but some
    values were derived rather than directly provided by the OTA."""

    INCOMPLETE = "INCOMPLETE"
    """One or more entries have PARTIAL confidence. Some financial data
    is missing — the statement may undercount revenue."""


# ---------------------------------------------------------------------------
# 2. OwnerStatementEntry — one booking's contribution to a statement
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OwnerStatementEntry:
    """
    One booking's financial contribution to a monthly owner statement.

    Immutable. Derived from a single (booking_id, envelope_type, BookingFinancialFacts)
    triple. The lifecycle_status is projected from payment_lifecycle.py (Phase 93).
    """

    booking_id: str
    """Canonical booking identifier: {source}_{normalized_ref}."""

    provider: str
    """OTA provider that produced this booking."""

    currency: Optional[str]
    """ISO 4217 currency code, or None if absent from financial facts."""

    total_price: Optional[Decimal]
    """Gross booking amount as reported by the OTA."""

    ota_commission: Optional[Decimal]
    """OTA commission amount (may be derived/estimated)."""

    net_to_property: Optional[Decimal]
    """Net payout to property (may be derived/estimated)."""

    source_confidence: str
    """FULL | PARTIAL | ESTIMATED — confidence of the underlying financial data."""

    lifecycle_status: str
    """PaymentLifecycleStatus string derived from project_payment_lifecycle()."""

    month: str
    """Calendar month this entry belongs to, format: YYYY-MM."""

    envelope_type: str
    """Canonical envelope type: BOOKING_CREATED | BOOKING_CANCELED | BOOKING_AMENDED."""

    is_canceled: bool
    """True if envelope_type is BOOKING_CANCELED. Net is excluded from statement totals."""


# ---------------------------------------------------------------------------
# 3. OwnerStatementSummary — aggregated monthly view
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OwnerStatementSummary:
    """
    Aggregated monthly financial summary for one property.

    Immutable. Produced by build_owner_statement().

    Aggregation rules:
    - gross_total: sum of total_price for all NON-canceled entries, same currency.
    - total_commission: sum of ota_commission for all NON-canceled entries.
    - net_total: sum of net_to_property for all NON-canceled entries.
    - Canceled entries appear in `entries` but are not added to totals.
    - Multi-currency: if currencies differ, all monetary totals are None
      and currency is set to "MIXED".
    - None monetary fields are excluded from sums (partial data).
    """

    property_id: str
    """Property identifier this statement covers."""

    month: str
    """Statement month, format: YYYY-MM."""

    currency: str
    """ISO 4217 currency code, or 'MIXED' if entries span multiple currencies."""

    gross_total: Optional[Decimal]
    """Sum of total_price for non-canceled entries. None if multi-currency or no data."""

    total_commission: Optional[Decimal]
    """Sum of ota_commission for non-canceled entries. None if multi-currency or no data."""

    net_total: Optional[Decimal]
    """Sum of net_to_property for non-canceled entries. None if multi-currency or no data."""

    booking_count: int
    """Total number of entries (including canceled)."""

    active_booking_count: int
    """Number of non-canceled entries contributing to financial totals."""

    canceled_booking_count: int
    """Number of canceled entries (excluded from financial totals)."""

    confidence_breakdown: Dict[str, int]
    """Count per confidence level: {'FULL': n, 'PARTIAL': n, 'ESTIMATED': n}."""

    statement_confidence: StatementConfidenceLevel
    """Overall quality indicator derived from confidence_breakdown."""

    entries: List[OwnerStatementEntry]
    """All entries for this month, including canceled ones."""


# ---------------------------------------------------------------------------
# 4. Internal helpers
# ---------------------------------------------------------------------------

def _derive_statement_confidence(
    breakdown: Dict[str, int],
) -> StatementConfidenceLevel:
    """
    Derive the overall statement confidence from a confidence breakdown dict.

    Rules (priority order):
    1. Any PARTIAL → INCOMPLETE
    2. All FULL (no ESTIMATED, no PARTIAL) → VERIFIED
    3. Otherwise (mix of FULL + ESTIMATED) → MIXED
    """
    if breakdown.get(CONFIDENCE_PARTIAL, 0) > 0:
        return StatementConfidenceLevel.INCOMPLETE
    if breakdown.get(CONFIDENCE_ESTIMATED, 0) == 0 and breakdown.get(CONFIDENCE_FULL, 0) > 0:
        return StatementConfidenceLevel.VERIFIED
    return StatementConfidenceLevel.MIXED


def _sum_optional(values: List[Optional[Decimal]]) -> Optional[Decimal]:
    """
    Sum a list of Optional[Decimal] values.
    If all are None → None. Otherwise sum the non-None values.
    """
    non_none = [v for v in values if v is not None]
    if not non_none:
        return None
    return sum(non_none, Decimal("0"))


# ---------------------------------------------------------------------------
# 5. Public API
# ---------------------------------------------------------------------------

def build_owner_statement(
    property_id: str,
    month: str,
    facts_with_metadata: List[Tuple[str, str, BookingFinancialFacts]],
) -> OwnerStatementSummary:
    """
    Build a monthly owner statement from a list of financial facts.

    Args:
        property_id:          Property identifier for this statement.
        month:                Statement month, format: YYYY-MM (e.g. "2026-06").
        facts_with_metadata:  List of (booking_id, envelope_type, BookingFinancialFacts)
                              tuples. Each tuple represents one booking event.

    Returns:
        OwnerStatementSummary — immutable, deterministic. Never raises on
        absent or None financial fields.

    Raises:
        ValueError: If property_id or month is empty.
        TypeError:  If any element of facts_with_metadata is not a 3-tuple
                    with a BookingFinancialFacts as its third element.
    """
    if not property_id:
        raise ValueError("property_id must be a non-empty string.")
    if not month:
        raise ValueError("month must be a non-empty string (format: YYYY-MM).")

    # --- Validate and build entries ---
    entries: List[OwnerStatementEntry] = []
    for item in facts_with_metadata:
        if (
            not isinstance(item, (list, tuple))
            or len(item) != 3
            or not isinstance(item[2], BookingFinancialFacts)
        ):
            raise TypeError(
                "Each element of facts_with_metadata must be a "
                "(booking_id: str, envelope_type: str, BookingFinancialFacts) tuple."
            )
        booking_id, envelope_type, facts = item[0], item[1], item[2]

        # Derive lifecycle status
        known_types = {"BOOKING_CREATED", "BOOKING_CANCELED", "BOOKING_AMENDED"}
        if envelope_type not in known_types:
            raise ValueError(
                f"envelope_type must be one of {sorted(known_types)}, got {envelope_type!r}"
            )

        lifecycle = project_payment_lifecycle(facts, envelope_type)
        is_canceled = (envelope_type == "BOOKING_CANCELED")

        entries.append(OwnerStatementEntry(
            booking_id=booking_id,
            provider=facts.provider,
            currency=facts.currency,
            total_price=facts.total_price,
            ota_commission=facts.ota_commission,
            net_to_property=facts.net_to_property,
            source_confidence=facts.source_confidence,
            lifecycle_status=lifecycle.status.value,
            month=month,
            envelope_type=envelope_type,
            is_canceled=is_canceled,
        ))

    # --- Currency guard ---
    currencies = {e.currency for e in entries if e.currency is not None}
    is_multi_currency = len(currencies) > 1
    currency_str = "MIXED" if is_multi_currency else (next(iter(currencies), None) or "UNKNOWN")

    # --- Separate active vs canceled ---
    active_entries = [e for e in entries if not e.is_canceled]
    canceled_entries = [e for e in entries if e.is_canceled]

    # --- Aggregate totals (only for active entries, only if single currency) ---
    if is_multi_currency:
        gross_total = None
        total_commission = None
        net_total = None
    else:
        gross_total = _sum_optional([e.total_price for e in active_entries])
        total_commission = _sum_optional([e.ota_commission for e in active_entries])
        net_total = _sum_optional([e.net_to_property for e in active_entries])

    # --- Confidence breakdown ---
    breakdown: Dict[str, int] = {
        CONFIDENCE_FULL: 0,
        CONFIDENCE_PARTIAL: 0,
        CONFIDENCE_ESTIMATED: 0,
    }
    for e in entries:
        if e.source_confidence in breakdown:
            breakdown[e.source_confidence] += 1

    statement_confidence = _derive_statement_confidence(breakdown)

    return OwnerStatementSummary(
        property_id=property_id,
        month=month,
        currency=currency_str,
        gross_total=gross_total,
        total_commission=total_commission,
        net_total=net_total,
        booking_count=len(entries),
        active_booking_count=len(active_entries),
        canceled_booking_count=len(canceled_entries),
        confidence_breakdown=breakdown,
        statement_confidence=statement_confidence,
        entries=entries,
    )
