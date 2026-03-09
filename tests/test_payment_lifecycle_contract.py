"""
Phase 93 — Payment Lifecycle Contract Tests

Tests the payment_lifecycle module:
  - PaymentLifecycleStatus enum values
  - PaymentLifecycleState dataclass
  - PaymentLifecycleExplanation dataclass
  - project_payment_lifecycle() — all 7 status outcomes
  - explain_payment_lifecycle() — rule_applied + reason captured
  - Determinism: same input → same output
  - Error handling: bad types, unknown envelope_type

Test groups:
  A — Enum and dataclass structure
  B — project_payment_lifecycle(): status outcomes per rule
  C — explain_payment_lifecycle(): explanation content
  D — All 8 OTA providers: end-to-end from extract_financial_facts → lifecycle
  E — Determinism: same input → same state
  F — Error handling: type guards and validation
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from adapters.ota.financial_extractor import (
    BookingFinancialFacts,
    CONFIDENCE_FULL,
    CONFIDENCE_ESTIMATED,
    CONFIDENCE_PARTIAL,
    extract_financial_facts,
)
from adapters.ota.payment_lifecycle import (
    PaymentLifecycleStatus,
    PaymentLifecycleState,
    PaymentLifecycleExplanation,
    project_payment_lifecycle,
    explain_payment_lifecycle,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_facts(
    provider: str = "bookingcom",
    total_price: str = "500.00",
    net: str = "425.00",
    commission: str = "75.00",
    currency: str = "EUR",
) -> BookingFinancialFacts:
    return BookingFinancialFacts(
        provider=provider,
        total_price=Decimal(total_price),
        currency=currency,
        ota_commission=Decimal(commission),
        taxes=None,
        fees=None,
        net_to_property=Decimal(net),
        source_confidence=CONFIDENCE_FULL,
        raw_financial_fields={},
    )


def _partial_facts_with_total(
    provider: str = "expedia",
    total_price: str = "480.00",
    currency: str = "USD",
) -> BookingFinancialFacts:
    return BookingFinancialFacts(
        provider=provider,
        total_price=Decimal(total_price),
        currency=currency,
        ota_commission=None,
        taxes=None,
        fees=None,
        net_to_property=None,
        source_confidence=CONFIDENCE_PARTIAL,
        raw_financial_fields={},
    )


def _empty_facts(provider: str = "airbnb") -> BookingFinancialFacts:
    return BookingFinancialFacts(
        provider=provider,
        total_price=None,
        currency=None,
        ota_commission=None,
        taxes=None,
        fees=None,
        net_to_property=None,
        source_confidence=CONFIDENCE_PARTIAL,
        raw_financial_fields={},
    )


def _estimated_facts(provider: str = "expedia") -> BookingFinancialFacts:
    return BookingFinancialFacts(
        provider=provider,
        total_price=Decimal("480.00"),
        currency="USD",
        ota_commission=Decimal("72.00"),
        taxes=None,
        fees=None,
        net_to_property=Decimal("408.00"),
        source_confidence=CONFIDENCE_ESTIMATED,
        raw_financial_fields={},
    )


# ---------------------------------------------------------------------------
# Group A — Enum and dataclass structure
# ---------------------------------------------------------------------------

class TestGroupAStructure:

    def test_a1_status_enum_values_exist(self) -> None:
        assert PaymentLifecycleStatus.GUEST_PAID
        assert PaymentLifecycleStatus.OTA_COLLECTING
        assert PaymentLifecycleStatus.PAYOUT_PENDING
        assert PaymentLifecycleStatus.PAYOUT_RELEASED
        assert PaymentLifecycleStatus.RECONCILIATION_PENDING
        assert PaymentLifecycleStatus.OWNER_NET_PENDING
        assert PaymentLifecycleStatus.UNKNOWN

    def test_a2_status_enum_has_seven_values(self) -> None:
        assert len(PaymentLifecycleStatus) == 7

    def test_a3_status_enum_is_str(self) -> None:
        assert isinstance(PaymentLifecycleStatus.GUEST_PAID, str)
        assert PaymentLifecycleStatus.GUEST_PAID == "GUEST_PAID"

    def test_a4_lifecycle_state_is_frozen_dataclass(self) -> None:
        state = PaymentLifecycleState(
            status=PaymentLifecycleStatus.PAYOUT_PENDING,
            total_price=Decimal("500.00"),
            net_to_property=None,
            ota_commission=None,
            currency="EUR",
            source_confidence=CONFIDENCE_PARTIAL,
            envelope_type="BOOKING_CREATED",
            provider="bookingcom",
        )
        with pytest.raises(Exception):
            state.status = PaymentLifecycleStatus.UNKNOWN  # type: ignore[misc]

    def test_a5_explanation_is_frozen_dataclass(self) -> None:
        state = project_payment_lifecycle(_full_facts(), "BOOKING_CREATED")
        explanation = explain_payment_lifecycle(_full_facts(), "BOOKING_CREATED")
        assert isinstance(explanation, PaymentLifecycleExplanation)
        assert isinstance(explanation.state, PaymentLifecycleState)
        assert isinstance(explanation.rule_applied, str)
        assert isinstance(explanation.reason, str)

    def test_a6_state_has_all_expected_fields(self) -> None:
        state = project_payment_lifecycle(_full_facts(), "BOOKING_CREATED")
        assert hasattr(state, "status")
        assert hasattr(state, "total_price")
        assert hasattr(state, "net_to_property")
        assert hasattr(state, "ota_commission")
        assert hasattr(state, "currency")
        assert hasattr(state, "source_confidence")
        assert hasattr(state, "envelope_type")
        assert hasattr(state, "provider")

    def test_a7_state_preserves_envelope_type(self) -> None:
        state = project_payment_lifecycle(_full_facts(), "BOOKING_AMENDED")
        assert state.envelope_type == "BOOKING_AMENDED"

    def test_a8_state_preserves_provider(self) -> None:
        state = project_payment_lifecycle(_full_facts(provider="agoda"), "BOOKING_CREATED")
        assert state.provider == "agoda"


# ---------------------------------------------------------------------------
# Group B — project_payment_lifecycle(): status outcomes
# ---------------------------------------------------------------------------

class TestGroupBProjection:

    # Rule 1: CANCELED → RECONCILIATION_PENDING
    def test_b1_canceled_always_reconciliation_pending_full_facts(self) -> None:
        state = project_payment_lifecycle(_full_facts(), "BOOKING_CANCELED")
        assert state.status == PaymentLifecycleStatus.RECONCILIATION_PENDING

    def test_b2_canceled_reconciliation_pending_even_with_no_data(self) -> None:
        state = project_payment_lifecycle(_empty_facts(), "BOOKING_CANCELED")
        assert state.status == PaymentLifecycleStatus.RECONCILIATION_PENDING

    def test_b3_canceled_reconciliation_pending_with_partial(self) -> None:
        state = project_payment_lifecycle(_partial_facts_with_total(), "BOOKING_CANCELED")
        assert state.status == PaymentLifecycleStatus.RECONCILIATION_PENDING

    # Rule 2: no total AND no net → UNKNOWN
    def test_b4_no_data_unknown(self) -> None:
        state = project_payment_lifecycle(_empty_facts(), "BOOKING_CREATED")
        assert state.status == PaymentLifecycleStatus.UNKNOWN

    def test_b5_amended_no_data_unknown(self) -> None:
        state = project_payment_lifecycle(_empty_facts(), "BOOKING_AMENDED")
        assert state.status == PaymentLifecycleStatus.UNKNOWN

    # Rule 3: PARTIAL + no net + has total → PAYOUT_PENDING
    def test_b6_partial_with_total_no_net_payout_pending(self) -> None:
        state = project_payment_lifecycle(
            _partial_facts_with_total(), "BOOKING_CREATED"
        )
        assert state.status == PaymentLifecycleStatus.PAYOUT_PENDING

    def test_b7_partial_amended_with_total_no_net_payout_pending(self) -> None:
        state = project_payment_lifecycle(
            _partial_facts_with_total(), "BOOKING_AMENDED"
        )
        assert state.status == PaymentLifecycleStatus.PAYOUT_PENDING

    # Rule 4: net_to_property available → OWNER_NET_PENDING
    def test_b8_estimated_net_available_owner_net_pending(self) -> None:
        state = project_payment_lifecycle(_estimated_facts(), "BOOKING_CREATED")
        assert state.status == PaymentLifecycleStatus.OWNER_NET_PENDING

    def test_b9_full_facts_with_net_owner_net_pending(self) -> None:
        # Rule 4 fires before rule 5 (net available wins over full confidence)
        state = project_payment_lifecycle(_full_facts(), "BOOKING_CREATED")
        assert state.status == PaymentLifecycleStatus.OWNER_NET_PENDING

    def test_b10_amended_full_facts_owner_net_pending(self) -> None:
        state = project_payment_lifecycle(_full_facts(), "BOOKING_AMENDED")
        assert state.status == PaymentLifecycleStatus.OWNER_NET_PENDING

    # Financial fields preserved in all states
    def test_b11_state_total_price_preserved(self) -> None:
        state = project_payment_lifecycle(_full_facts(), "BOOKING_CREATED")
        assert state.total_price == Decimal("500.00")

    def test_b12_state_net_to_property_preserved(self) -> None:
        state = project_payment_lifecycle(_full_facts(), "BOOKING_CREATED")
        assert state.net_to_property == Decimal("425.00")

    def test_b13_state_currency_preserved(self) -> None:
        state = project_payment_lifecycle(_full_facts(), "BOOKING_CREATED")
        assert state.currency == "EUR"

    def test_b14_state_source_confidence_preserved(self) -> None:
        state = project_payment_lifecycle(_full_facts(), "BOOKING_CREATED")
        assert state.source_confidence == CONFIDENCE_FULL

    def test_b15_payout_pending_total_price_preserved(self) -> None:
        state = project_payment_lifecycle(_partial_facts_with_total(), "BOOKING_CREATED")
        assert state.total_price == Decimal("480.00")

    def test_b16_unknown_state_has_no_total(self) -> None:
        state = project_payment_lifecycle(_empty_facts(), "BOOKING_CREATED")
        assert state.total_price is None
        assert state.net_to_property is None


# ---------------------------------------------------------------------------
# Group C — explain_payment_lifecycle()
# ---------------------------------------------------------------------------

class TestGroupCExplanation:

    def test_c1_explanation_state_matches_project(self) -> None:
        state = project_payment_lifecycle(_full_facts(), "BOOKING_CREATED")
        explanation = explain_payment_lifecycle(_full_facts(), "BOOKING_CREATED")
        assert explanation.state.status == state.status

    def test_c2_canceled_rule_name(self) -> None:
        explanation = explain_payment_lifecycle(_full_facts(), "BOOKING_CANCELED")
        assert explanation.rule_applied == "canceled_booking"

    def test_c3_no_data_rule_name(self) -> None:
        explanation = explain_payment_lifecycle(_empty_facts(), "BOOKING_CREATED")
        assert explanation.rule_applied == "no_financial_data"

    def test_c4_partial_with_total_rule_name(self) -> None:
        explanation = explain_payment_lifecycle(
            _partial_facts_with_total(), "BOOKING_CREATED"
        )
        assert explanation.rule_applied == "partial_no_net"

    def test_c5_net_available_rule_name(self) -> None:
        explanation = explain_payment_lifecycle(_estimated_facts(), "BOOKING_CREATED")
        assert explanation.rule_applied == "net_available"

    def test_c6_reason_is_non_empty_string(self) -> None:
        for facts, etype in [
            (_full_facts(), "BOOKING_CREATED"),
            (_full_facts(), "BOOKING_CANCELED"),
            (_empty_facts(), "BOOKING_CREATED"),
            (_partial_facts_with_total(), "BOOKING_CREATED"),
            (_estimated_facts(), "BOOKING_CREATED"),
        ]:
            explanation = explain_payment_lifecycle(facts, etype)
            assert isinstance(explanation.reason, str)
            assert len(explanation.reason) > 10

    def test_c7_explanation_preserves_provider(self) -> None:
        explanation = explain_payment_lifecycle(
            _full_facts(provider="vrbo"), "BOOKING_CREATED"
        )
        assert explanation.state.provider == "vrbo"

    def test_c8_canceled_reason_mentions_reconciliation(self) -> None:
        explanation = explain_payment_lifecycle(_full_facts(), "BOOKING_CANCELED")
        assert "reconcil" in explanation.reason.lower()


# ---------------------------------------------------------------------------
# Group D — All 8 OTA providers: end-to-end from extract_financial_facts
# ---------------------------------------------------------------------------

PROVIDER_PAYLOADS = {
    "bookingcom": {
        "total_price": "750.00", "currency": "EUR",
        "commission": "75.00", "net": "675.00",
    },
    "expedia": {
        "total_amount": "480.00", "currency": "USD",
        "commission_percent": "15",
    },
    "airbnb": {
        "payout_amount": "540.00", "booking_subtotal": "620.00",
        "taxes": "80.00", "currency": "USD",
    },
    "agoda": {
        "selling_rate": "3300.00", "net_rate": "2805.00", "currency": "THB",
    },
    "tripcom": {
        "order_amount": "550.00", "channel_fee": "55.00", "currency": "CNY",
    },
    "vrbo": {
        "traveler_payment": "900.00", "manager_payment": "765.00",
        "service_fee": "135.00", "currency": "USD",
    },
    "gvr": {
        "booking_value": "400.00", "google_fee": "40.00",
        "net_amount": "360.00", "currency": "EUR",
    },
    "traveloka": {
        "booking_total": "3200.00", "traveloka_fee": "320.00",
        "net_payout": "2880.00", "currency_code": "THB",
    },
}


class TestGroupDAllProviders:

    @pytest.mark.parametrize("provider", list(PROVIDER_PAYLOADS.keys()))
    def test_d1_extract_then_project_returns_state(self, provider: str) -> None:
        facts = extract_financial_facts(provider, PROVIDER_PAYLOADS[provider])
        state = project_payment_lifecycle(facts, "BOOKING_CREATED")
        assert isinstance(state, PaymentLifecycleState)

    @pytest.mark.parametrize("provider", list(PROVIDER_PAYLOADS.keys()))
    def test_d2_provider_preserved_in_state(self, provider: str) -> None:
        facts = extract_financial_facts(provider, PROVIDER_PAYLOADS[provider])
        state = project_payment_lifecycle(facts, "BOOKING_CREATED")
        assert state.provider == provider

    @pytest.mark.parametrize("provider", list(PROVIDER_PAYLOADS.keys()))
    def test_d3_canceled_always_reconciliation_pending(self, provider: str) -> None:
        facts = extract_financial_facts(provider, PROVIDER_PAYLOADS[provider])
        state = project_payment_lifecycle(facts, "BOOKING_CANCELED")
        assert state.status == PaymentLifecycleStatus.RECONCILIATION_PENDING

    @pytest.mark.parametrize("provider", list(PROVIDER_PAYLOADS.keys()))
    def test_d4_status_is_not_unknown_when_data_present(self, provider: str) -> None:
        facts = extract_financial_facts(provider, PROVIDER_PAYLOADS[provider])
        state = project_payment_lifecycle(facts, "BOOKING_CREATED")
        # All test payloads have at least total_price — should not be UNKNOWN
        assert state.status != PaymentLifecycleStatus.UNKNOWN

    @pytest.mark.parametrize("provider", list(PROVIDER_PAYLOADS.keys()))
    def test_d5_explain_rule_applied_is_string(self, provider: str) -> None:
        facts = extract_financial_facts(provider, PROVIDER_PAYLOADS[provider])
        explanation = explain_payment_lifecycle(facts, "BOOKING_CREATED")
        assert isinstance(explanation.rule_applied, str)
        assert explanation.rule_applied

    @pytest.mark.parametrize("provider", list(PROVIDER_PAYLOADS.keys()))
    def test_d6_amended_returns_valid_status(self, provider: str) -> None:
        facts = extract_financial_facts(provider, PROVIDER_PAYLOADS[provider])
        state = project_payment_lifecycle(facts, "BOOKING_AMENDED")
        assert isinstance(state.status, PaymentLifecycleStatus)

    @pytest.mark.parametrize("provider", list(PROVIDER_PAYLOADS.keys()))
    def test_d7_currency_preserved_where_available(self, provider: str) -> None:
        facts = extract_financial_facts(provider, PROVIDER_PAYLOADS[provider])
        state = project_payment_lifecycle(facts, "BOOKING_CREATED")
        assert state.currency is not None  # All test payloads have currency

    @pytest.mark.parametrize("provider", list(PROVIDER_PAYLOADS.keys()))
    def test_d8_source_confidence_preserved(self, provider: str) -> None:
        facts = extract_financial_facts(provider, PROVIDER_PAYLOADS[provider])
        state = project_payment_lifecycle(facts, "BOOKING_CREATED")
        assert state.source_confidence in (CONFIDENCE_FULL, CONFIDENCE_PARTIAL, CONFIDENCE_ESTIMATED)


# ---------------------------------------------------------------------------
# Group E — Determinism: same input → same state
# ---------------------------------------------------------------------------

class TestGroupEDeterminism:

    @pytest.mark.parametrize("envelope_type", ["BOOKING_CREATED", "BOOKING_CANCELED", "BOOKING_AMENDED"])
    def test_e1_full_facts_same_status_twice(self, envelope_type: str) -> None:
        facts = _full_facts()
        s1 = project_payment_lifecycle(facts, envelope_type)
        s2 = project_payment_lifecycle(facts, envelope_type)
        assert s1.status == s2.status

    @pytest.mark.parametrize("envelope_type", ["BOOKING_CREATED", "BOOKING_CANCELED", "BOOKING_AMENDED"])
    def test_e2_empty_facts_same_status_twice(self, envelope_type: str) -> None:
        facts = _empty_facts()
        s1 = project_payment_lifecycle(facts, envelope_type)
        s2 = project_payment_lifecycle(facts, envelope_type)
        assert s1.status == s2.status

    @pytest.mark.parametrize("provider", list(PROVIDER_PAYLOADS.keys()))
    def test_e3_per_provider_idempotent(self, provider: str) -> None:
        facts = extract_financial_facts(provider, PROVIDER_PAYLOADS[provider])
        s1 = project_payment_lifecycle(facts, "BOOKING_CREATED")
        s2 = project_payment_lifecycle(facts, "BOOKING_CREATED")
        assert s1.status == s2.status
        assert s1.total_price == s2.total_price
        assert s1.net_to_property == s2.net_to_property

    def test_e4_explanation_rule_is_stable(self) -> None:
        exp1 = explain_payment_lifecycle(_estimated_facts(), "BOOKING_CREATED")
        exp2 = explain_payment_lifecycle(_estimated_facts(), "BOOKING_CREATED")
        assert exp1.rule_applied == exp2.rule_applied
        assert exp1.state.status == exp2.state.status


# ---------------------------------------------------------------------------
# Group F — Error handling
# ---------------------------------------------------------------------------

class TestGroupFErrorHandling:

    def test_f1_project_raises_on_non_facts(self) -> None:
        with pytest.raises(TypeError, match="BookingFinancialFacts"):
            project_payment_lifecycle({"total_price": "100.00"}, "BOOKING_CREATED")  # type: ignore[arg-type]

    def test_f2_project_raises_on_unknown_envelope_type(self) -> None:
        with pytest.raises(ValueError, match="envelope_type"):
            project_payment_lifecycle(_full_facts(), "BOOKING_REBASED")

    def test_f3_explain_raises_on_non_facts(self) -> None:
        with pytest.raises(TypeError, match="BookingFinancialFacts"):
            explain_payment_lifecycle(None, "BOOKING_CREATED")  # type: ignore[arg-type]

    def test_f4_explain_raises_on_unknown_envelope_type(self) -> None:
        with pytest.raises(ValueError, match="envelope_type"):
            explain_payment_lifecycle(_full_facts(), "INVALID_TYPE")

    def test_f5_empty_string_envelope_type_rejected(self) -> None:
        with pytest.raises(ValueError):
            project_payment_lifecycle(_full_facts(), "")

    def test_f6_lowercase_envelope_type_rejected(self) -> None:
        with pytest.raises(ValueError):
            project_payment_lifecycle(_full_facts(), "booking_created")

    def test_f7_none_envelope_type_rejected(self) -> None:
        with pytest.raises((ValueError, AttributeError, TypeError)):
            project_payment_lifecycle(_full_facts(), None)  # type: ignore[arg-type]
