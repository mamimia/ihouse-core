"""
Phase 93 — Payment Lifecycle / Revenue State Projection

Provides a deterministic, read-only projection of a booking's payment
lifecycle state, derived purely from BookingFinancialFacts and the
canonical envelope type.

Design rules:
  - Zero writes to any data store. Pure projection, no side effects.
  - Does NOT modify booking_state, financial_facts, or canonical envelopes.
  - Deterministic: same inputs → same state, always. No clock, no randomness.
  - Works entirely from in-memory BookingFinancialFacts produced by Phase 65.

Invariant (locked Phase 62+):
  booking_state must NEVER contain financial calculations.

Invariant (Phase 93):
  payment_lifecycle.py is READ-ONLY. Corrections, writes, and mutations
  must go through the canonical pipeline (apply_envelope).

Public API:
  project_payment_lifecycle(financial_facts, envelope_type) -> PaymentLifecycleState
  explain_payment_lifecycle(financial_facts, envelope_type) -> PaymentLifecycleExplanation
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

from .financial_extractor import (
    BookingFinancialFacts,
    CONFIDENCE_FULL,
    CONFIDENCE_ESTIMATED,
    CONFIDENCE_PARTIAL,
)


# ---------------------------------------------------------------------------
# 1. PaymentLifecycleStatus — the finite state set
# ---------------------------------------------------------------------------

class PaymentLifecycleStatus(str, Enum):
    """
    Finite set of payment lifecycle states for a booking.

    States progress in a general order but not strictly linearly —
    cancellations and partial data create branches.
    """

    GUEST_PAID = "GUEST_PAID"
    """
    Guest has fully paid the OTA. The booking is active and financially
    settled on the guest side. Property payout is pending or released.
    """

    OTA_COLLECTING = "OTA_COLLECTING"
    """
    OTA is still collecting payment from the guest (e.g. instalment booking,
    partial payment detected). Payout to property cannot begin until complete.
    """

    PAYOUT_PENDING = "PAYOUT_PENDING"
    """
    OTA owes the property its net payout. The payout has not yet been
    confirmed as released. This is the most common post-booking state.
    """

    PAYOUT_RELEASED = "PAYOUT_RELEASED"
    """
    Net payout has been explicitly confirmed as released to the property.
    Requires explicit release signal from the provider (rare in webhooks).
    """

    RECONCILIATION_PENDING = "RECONCILIATION_PENDING"
    """
    A financial discrepancy or cancellation has been detected.
    Manual or automated reconciliation is needed.
    Examples: cancellation after payout, mismatched amounts, refund required.
    """

    OWNER_NET_PENDING = "OWNER_NET_PENDING"
    """
    The net-to-owner amount has been calculated (or derived) and is
    available, but no payout release confirmation has been received yet.
    Subtly different from PAYOUT_PENDING — net_to_property is known.
    """

    UNKNOWN = "UNKNOWN"
    """
    Insufficient data to determine the payment lifecycle state.
    This occurs when financial facts have PARTIAL confidence and key fields
    are missing. Not an error — just an absence of signal.
    """


# ---------------------------------------------------------------------------
# 2. PaymentLifecycleState — the output container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PaymentLifecycleState:
    """
    Result of a payment lifecycle projection.

    Immutable. Contains the computed status and supporting financial signals.
    """

    status: PaymentLifecycleStatus
    """The projected payment lifecycle status."""

    total_price: Optional[Decimal]
    """Gross booking amount (from financial facts)."""

    net_to_property: Optional[Decimal]
    """Net payout to property (from financial facts, may be derived)."""

    ota_commission: Optional[Decimal]
    """OTA commission amount (from financial facts, may be derived)."""

    currency: Optional[str]
    """ISO 4217 currency code."""

    source_confidence: str
    """FULL | PARTIAL | ESTIMATED — confidence of the underlying financial data."""

    envelope_type: str
    """Canonical envelope type that informed the projection."""

    provider: str
    """OTA provider that produced the financial facts."""


# ---------------------------------------------------------------------------
# 3. PaymentLifecycleExplanation — for diagnostics and audit
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PaymentLifecycleExplanation:
    """
    Diagnostic wrapper around PaymentLifecycleState.

    Captures the reasoning path that led to the projected status.
    Used for audit, debugging, and future reconciliation tooling.
    """

    state: PaymentLifecycleState
    """The projected state."""

    rule_applied: str
    """Short name of the decision rule that produced this state."""

    reason: str
    """Human-readable explanation of why this state was chosen."""


# ---------------------------------------------------------------------------
# 4. Decision rules (ordered by priority)
# ---------------------------------------------------------------------------
#
# Rules are applied in order. The first matching rule wins.
# Each rule is a pure function: (facts, envelope_type) -> (status, rule, reason) | None
#
# Rule naming convention: _rule_{n}_{short_name}

def _rule_1_canceled(
    facts: BookingFinancialFacts, envelope_type: str
) -> Optional[tuple[PaymentLifecycleStatus, str, str]]:
    """BOOKING_CANCELED always → RECONCILIATION_PENDING."""
    if envelope_type == "BOOKING_CANCELED":
        return (
            PaymentLifecycleStatus.RECONCILIATION_PENDING,
            "canceled_booking",
            "Booking is canceled. Financial reconciliation required "
            "(refund assessment, payout reversal, or confirmation of no payout).",
        )
    return None


def _rule_2_insufficient_data(
    facts: BookingFinancialFacts, envelope_type: str
) -> Optional[tuple[PaymentLifecycleStatus, str, str]]:
    """No total_price AND no net_to_property → UNKNOWN."""
    if facts.total_price is None and facts.net_to_property is None:
        return (
            PaymentLifecycleStatus.UNKNOWN,
            "no_financial_data",
            "Neither total_price nor net_to_property could be extracted. "
            f"Source confidence: {facts.source_confidence}. "
            "Cannot determine payment lifecycle state.",
        )
    return None


def _rule_3_partial_with_no_net(
    facts: BookingFinancialFacts, envelope_type: str
) -> Optional[tuple[PaymentLifecycleStatus, str, str]]:
    """PARTIAL confidence + no net_to_property → PAYOUT_PENDING."""
    if (
        facts.source_confidence == CONFIDENCE_PARTIAL
        and facts.net_to_property is None
        and facts.total_price is not None
    ):
        return (
            PaymentLifecycleStatus.PAYOUT_PENDING,
            "partial_no_net",
            f"Financial confidence is PARTIAL and net_to_property is absent. "
            f"total_price={facts.total_price} {facts.currency or '?'}. "
            "Payout to property is pending — amount not yet confirmed.",
        )
    return None


def _rule_4_net_available(
    facts: BookingFinancialFacts, envelope_type: str
) -> Optional[tuple[PaymentLifecycleStatus, str, str]]:
    """net_to_property is available (directly or derived) → OWNER_NET_PENDING."""
    if facts.net_to_property is not None and facts.total_price is not None:
        confidence_note = (
            " (net is derived/estimated)" if facts.source_confidence == CONFIDENCE_ESTIMATED
            else ""
        )
        return (
            PaymentLifecycleStatus.OWNER_NET_PENDING,
            "net_available",
            f"net_to_property={facts.net_to_property} {facts.currency or '?'}"
            f", total_price={facts.total_price}{confidence_note}. "
            "Owner net is calculated; awaiting payout release confirmation.",
        )
    return None


def _rule_5_full_confidence_guest_paid(
    facts: BookingFinancialFacts, envelope_type: str
) -> Optional[tuple[PaymentLifecycleStatus, str, str]]:
    """FULL confidence, active booking → GUEST_PAID."""
    if facts.source_confidence == CONFIDENCE_FULL and envelope_type == "BOOKING_CREATED":
        return (
            PaymentLifecycleStatus.GUEST_PAID,
            "full_confidence_created",
            f"Full financial confidence. total_price={facts.total_price} {facts.currency or '?'}. "
            "Guest payment to OTA is complete. Payout to property pending.",
        )
    return None


def _rule_6_fallback(
    facts: BookingFinancialFacts, envelope_type: str
) -> Optional[tuple[PaymentLifecycleStatus, str, str]]:
    """Catch-all → UNKNOWN."""
    return (
        PaymentLifecycleStatus.UNKNOWN,
        "fallback",
        f"No specific rule matched for envelope_type={envelope_type!r}, "
        f"confidence={facts.source_confidence}. "
        "Defaulting to UNKNOWN.",
    )


_RULES = [
    _rule_1_canceled,
    _rule_2_insufficient_data,
    _rule_3_partial_with_no_net,
    _rule_4_net_available,
    _rule_5_full_confidence_guest_paid,
    _rule_6_fallback,
]

# ---------------------------------------------------------------------------
# 5. Public API
# ---------------------------------------------------------------------------

def project_payment_lifecycle(
    financial_facts: BookingFinancialFacts,
    envelope_type: str,
) -> PaymentLifecycleState:
    """
    Project the payment lifecycle state from financial facts and envelope type.

    Args:
        financial_facts: BookingFinancialFacts produced by extract_financial_facts().
        envelope_type:   Canonical envelope type string:
                         "BOOKING_CREATED" | "BOOKING_CANCELED" | "BOOKING_AMENDED"

    Returns:
        PaymentLifecycleState — immutable, deterministic. Never raises on absent fields.

    Raises:
        TypeError: If financial_facts is not a BookingFinancialFacts instance.
        ValueError: If envelope_type is not a recognized canonical type.
    """
    if not isinstance(financial_facts, BookingFinancialFacts):
        raise TypeError(
            f"financial_facts must be a BookingFinancialFacts instance, "
            f"got {type(financial_facts).__name__}"
        )

    known_types = {"BOOKING_CREATED", "BOOKING_CANCELED", "BOOKING_AMENDED"}
    if envelope_type not in known_types:
        raise ValueError(
            f"envelope_type must be one of {sorted(known_types)}, got {envelope_type!r}"
        )

    for rule in _RULES:
        result = rule(financial_facts, envelope_type)
        if result is not None:
            status, _rule_name, _reason = result
            return PaymentLifecycleState(
                status=status,
                total_price=financial_facts.total_price,
                net_to_property=financial_facts.net_to_property,
                ota_commission=financial_facts.ota_commission,
                currency=financial_facts.currency,
                source_confidence=financial_facts.source_confidence,
                envelope_type=envelope_type,
                provider=financial_facts.provider,
            )

    # Unreachable — _rule_6_fallback always returns
    raise RuntimeError("No rule matched — this should never happen.")  # pragma: no cover


def explain_payment_lifecycle(
    financial_facts: BookingFinancialFacts,
    envelope_type: str,
) -> PaymentLifecycleExplanation:
    """
    Project the payment lifecycle state and capture the reasoning path.

    Same inputs as project_payment_lifecycle(). Returns a richer
    PaymentLifecycleExplanation that includes the rule name and reason string,
    useful for audit and diagnostics.

    Args:
        financial_facts: BookingFinancialFacts produced by extract_financial_facts().
        envelope_type:   Canonical envelope type string.

    Returns:
        PaymentLifecycleExplanation — immutable, includes state + explanation.
    """
    if not isinstance(financial_facts, BookingFinancialFacts):
        raise TypeError(
            f"financial_facts must be a BookingFinancialFacts instance, "
            f"got {type(financial_facts).__name__}"
        )

    known_types = {"BOOKING_CREATED", "BOOKING_CANCELED", "BOOKING_AMENDED"}
    if envelope_type not in known_types:
        raise ValueError(
            f"envelope_type must be one of {sorted(known_types)}, got {envelope_type!r}"
        )

    for rule in _RULES:
        result = rule(financial_facts, envelope_type)
        if result is not None:
            status, rule_name, reason = result
            state = PaymentLifecycleState(
                status=status,
                total_price=financial_facts.total_price,
                net_to_property=financial_facts.net_to_property,
                ota_commission=financial_facts.ota_commission,
                currency=financial_facts.currency,
                source_confidence=financial_facts.source_confidence,
                envelope_type=envelope_type,
                provider=financial_facts.provider,
            )
            return PaymentLifecycleExplanation(
                state=state,
                rule_applied=rule_name,
                reason=reason,
            )

    raise RuntimeError("No rule matched — this should never happen.")  # pragma: no cover
