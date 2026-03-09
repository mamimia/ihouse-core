"""
Phase 100 — Owner Statement Contract Tests

Tests the owner_statement.py module:
  OwnerStatementEntry, OwnerStatementSummary, StatementConfidenceLevel,
  build_owner_statement()

Structure:
  Group A — Entry construction: fields, frozen, correct types
  Group B — Single-booking statement: one booking → correct summary totals
  Group C — Multi-booking aggregation: multiple bookings, sums correct
  Group D — Canceled booking handling: excluded from totals, included in entries
  Group E — Multi-currency guard: mixed currencies → MIXED, totals None
  Group F — Confidence breakdown: counts per confidence level
  Group G — Statement confidence level: VERIFIED / MIXED / INCOMPLETE rules
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from adapters.ota.financial_extractor import BookingFinancialFacts, CONFIDENCE_FULL, CONFIDENCE_PARTIAL, CONFIDENCE_ESTIMATED
from adapters.ota.owner_statement import (
    OwnerStatementEntry,
    OwnerStatementSummary,
    StatementConfidenceLevel,
    build_owner_statement,
)


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

def _make_facts(
    provider: str = "bookingcom",
    total_price: str = "1000.00",
    currency: str = "USD",
    ota_commission: str = "150.00",
    net_to_property: str = "850.00",
    source_confidence: str = CONFIDENCE_FULL,
) -> BookingFinancialFacts:
    return BookingFinancialFacts(
        provider=provider,
        total_price=Decimal(total_price) if total_price else None,
        currency=currency,
        ota_commission=Decimal(ota_commission) if ota_commission else None,
        taxes=None,
        fees=None,
        net_to_property=Decimal(net_to_property) if net_to_property else None,
        source_confidence=source_confidence,
        raw_financial_fields={},
    )


def _make_facts_partial(
    provider: str = "expedia",
    currency: str = "USD",
) -> BookingFinancialFacts:
    return BookingFinancialFacts(
        provider=provider,
        total_price=Decimal("500.00"),
        currency=currency,
        ota_commission=None,
        taxes=None,
        fees=None,
        net_to_property=None,
        source_confidence=CONFIDENCE_PARTIAL,
        raw_financial_fields={},
    )


def _single_entry(
    booking_id: str = "bookingcom_BK-001",
    envelope_type: str = "BOOKING_CREATED",
    facts: BookingFinancialFacts = None,
):
    if facts is None:
        facts = _make_facts()
    return (booking_id, envelope_type, facts)


# ---------------------------------------------------------------------------
# Group A — Entry construction
# ---------------------------------------------------------------------------

class TestGroupAEntryConstruction:

    def test_a1_build_owner_statement_returns_summary(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-06", [_single_entry()]
        )
        assert isinstance(summary, OwnerStatementSummary)

    def test_a2_summary_has_correct_property_id(self) -> None:
        summary = build_owner_statement(
            "PROP-XYZ", "2026-06", [_single_entry()]
        )
        assert summary.property_id == "PROP-XYZ"

    def test_a3_summary_has_correct_month(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-09", [_single_entry()]
        )
        assert summary.month == "2026-09"

    def test_a4_entries_are_owner_statement_entry_instances(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-06", [_single_entry()]
        )
        assert len(summary.entries) == 1
        assert isinstance(summary.entries[0], OwnerStatementEntry)

    def test_a5_entry_booking_id_preserved(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-06", [_single_entry("bookingcom_BK-TEST")]
        )
        assert summary.entries[0].booking_id == "bookingcom_BK-TEST"

    def test_a6_entry_provider_preserved(self) -> None:
        facts = _make_facts(provider="agoda")
        summary = build_owner_statement(
            "PROP-001", "2026-06", [("agoda_AG-001", "BOOKING_CREATED", facts)]
        )
        assert summary.entries[0].provider == "agoda"

    def test_a7_entry_month_matches_statement_month(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-07", [_single_entry()]
        )
        assert summary.entries[0].month == "2026-07"

    def test_a8_entry_is_frozen(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-06", [_single_entry()]
        )
        with pytest.raises((AttributeError, TypeError)):
            summary.entries[0].booking_id = "mutated"  # type: ignore[misc]

    def test_a9_summary_is_frozen(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-06", [_single_entry()]
        )
        with pytest.raises((AttributeError, TypeError)):
            summary.gross_total = Decimal("999")  # type: ignore[misc]

    def test_a10_entry_envelope_type_preserved(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-06", [_single_entry(envelope_type="BOOKING_AMENDED")]
        )
        assert summary.entries[0].envelope_type == "BOOKING_AMENDED"

    def test_a11_entry_is_canceled_false_for_created(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-06", [_single_entry(envelope_type="BOOKING_CREATED")]
        )
        assert summary.entries[0].is_canceled is False

    def test_a12_entry_is_canceled_true_for_canceled(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-06",
            [_single_entry(envelope_type="BOOKING_CANCELED")]
        )
        assert summary.entries[0].is_canceled is True

    def test_a13_empty_input_returns_empty_summary(self) -> None:
        summary = build_owner_statement("PROP-001", "2026-06", [])
        assert summary.booking_count == 0
        assert summary.entries == []

    def test_a14_empty_property_id_raises(self) -> None:
        with pytest.raises(ValueError, match="property_id"):
            build_owner_statement("", "2026-06", [])

    def test_a15_empty_month_raises(self) -> None:
        with pytest.raises(ValueError, match="month"):
            build_owner_statement("PROP-001", "", [])

    def test_a16_invalid_tuple_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            build_owner_statement("PROP-001", "2026-06", [("only", "two")])  # type: ignore

    def test_a17_invalid_envelope_type_raises_value_error(self) -> None:
        facts = _make_facts()
        with pytest.raises(ValueError, match="envelope_type"):
            build_owner_statement(
                "PROP-001", "2026-06",
                [("bookingcom_BK-001", "INVALID_TYPE", facts)]
            )


# ---------------------------------------------------------------------------
# Group B — Single-booking statement
# ---------------------------------------------------------------------------

class TestGroupBSingleBooking:

    def test_b1_booking_count_is_one(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-06", [_single_entry()]
        )
        assert summary.booking_count == 1

    def test_b2_active_booking_count_is_one(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-06", [_single_entry()]
        )
        assert summary.active_booking_count == 1

    def test_b3_canceled_booking_count_is_zero(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-06", [_single_entry()]
        )
        assert summary.canceled_booking_count == 0

    def test_b4_gross_total_matches_total_price(self) -> None:
        facts = _make_facts(total_price="1500.00")
        summary = build_owner_statement(
            "PROP-001", "2026-06", [("bk_001", "BOOKING_CREATED", facts)]
        )
        assert summary.gross_total == Decimal("1500.00")

    def test_b5_net_total_matches_net_to_property(self) -> None:
        facts = _make_facts(net_to_property="1275.00")
        summary = build_owner_statement(
            "PROP-001", "2026-06", [("bk_001", "BOOKING_CREATED", facts)]
        )
        assert summary.net_total == Decimal("1275.00")

    def test_b6_total_commission_matches_ota_commission(self) -> None:
        facts = _make_facts(ota_commission="225.00")
        summary = build_owner_statement(
            "PROP-001", "2026-06", [("bk_001", "BOOKING_CREATED", facts)]
        )
        assert summary.total_commission == Decimal("225.00")

    def test_b7_currency_matches_facts_currency(self) -> None:
        facts = _make_facts(currency="EUR")
        summary = build_owner_statement(
            "PROP-001", "2026-06", [("bk_001", "BOOKING_CREATED", facts)]
        )
        assert summary.currency == "EUR"

    def test_b8_entry_lifecycle_status_is_string(self) -> None:
        summary = build_owner_statement(
            "PROP-001", "2026-06", [_single_entry()]
        )
        assert isinstance(summary.entries[0].lifecycle_status, str)
        assert summary.entries[0].lifecycle_status != ""

    def test_b9_entry_source_confidence_preserved(self) -> None:
        facts = _make_facts(source_confidence=CONFIDENCE_FULL)
        summary = build_owner_statement(
            "PROP-001", "2026-06", [("bk_001", "BOOKING_CREATED", facts)]
        )
        assert summary.entries[0].source_confidence == CONFIDENCE_FULL


# ---------------------------------------------------------------------------
# Group C — Multi-booking aggregation
# ---------------------------------------------------------------------------

class TestGroupCMultiBooking:

    def _two_bookings(self):
        f1 = _make_facts(total_price="1000.00", ota_commission="150.00", net_to_property="850.00", currency="USD")
        f2 = _make_facts(total_price="2000.00", ota_commission="300.00", net_to_property="1700.00", currency="USD")
        return [
            ("bk_001", "BOOKING_CREATED", f1),
            ("bk_002", "BOOKING_CREATED", f2),
        ]

    def test_c1_booking_count_is_two(self) -> None:
        summary = build_owner_statement("PROP-001", "2026-06", self._two_bookings())
        assert summary.booking_count == 2

    def test_c2_gross_total_is_sum(self) -> None:
        summary = build_owner_statement("PROP-001", "2026-06", self._two_bookings())
        assert summary.gross_total == Decimal("3000.00")

    def test_c3_net_total_is_sum(self) -> None:
        summary = build_owner_statement("PROP-001", "2026-06", self._two_bookings())
        assert summary.net_total == Decimal("2550.00")

    def test_c4_total_commission_is_sum(self) -> None:
        summary = build_owner_statement("PROP-001", "2026-06", self._two_bookings())
        assert summary.total_commission == Decimal("450.00")

    def test_c5_all_entries_present(self) -> None:
        summary = build_owner_statement("PROP-001", "2026-06", self._two_bookings())
        booking_ids = {e.booking_id for e in summary.entries}
        assert booking_ids == {"bk_001", "bk_002"}

    def test_c6_three_bookings_correct_net(self) -> None:
        f = _make_facts(total_price="500.00", ota_commission="75.00", net_to_property="425.00", currency="USD")
        inputs = [
            ("bk_001", "BOOKING_CREATED", f),
            ("bk_002", "BOOKING_CREATED", f),
            ("bk_003", "BOOKING_CREATED", f),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.net_total == Decimal("1275.00")

    def test_c7_none_fields_excluded_from_sum(self) -> None:
        """A booking with None net_to_property should be excluded from sum, not error."""
        f_full = _make_facts(net_to_property="850.00", currency="USD")
        f_partial = BookingFinancialFacts(
            provider="expedia",
            total_price=Decimal("500.00"),
            currency="USD",
            ota_commission=None,
            taxes=None,
            fees=None,
            net_to_property=None,
            source_confidence=CONFIDENCE_PARTIAL,
            raw_financial_fields={},
        )
        inputs = [
            ("bk_001", "BOOKING_CREATED", f_full),
            ("bk_002", "BOOKING_CREATED", f_partial),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        # Only f_full contributes net
        assert summary.net_total == Decimal("850.00")

    def test_c8_amended_booking_included_in_active(self) -> None:
        f = _make_facts(currency="USD")
        inputs = [("bk_001", "BOOKING_AMENDED", f)]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.active_booking_count == 1
        assert summary.canceled_booking_count == 0


# ---------------------------------------------------------------------------
# Group D — Canceled booking handling
# ---------------------------------------------------------------------------

class TestGroupDCanceledBookings:

    def test_d1_canceled_booking_appears_in_entries(self) -> None:
        f = _make_facts(currency="USD")
        inputs = [("bk_001", "BOOKING_CANCELED", f)]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert len(summary.entries) == 1
        assert summary.entries[0].is_canceled is True

    def test_d2_canceled_net_excluded_from_net_total(self) -> None:
        f = _make_facts(net_to_property="850.00", currency="USD")
        inputs = [("bk_001", "BOOKING_CANCELED", f)]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        # Canceled → net_total should be None (no active bookings)
        assert summary.net_total is None

    def test_d3_canceled_excluded_from_gross_total(self) -> None:
        f = _make_facts(total_price="1000.00", currency="USD")
        inputs = [("bk_001", "BOOKING_CANCELED", f)]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.gross_total is None

    def test_d4_canceled_count_incremented(self) -> None:
        f = _make_facts(currency="USD")
        inputs = [("bk_001", "BOOKING_CANCELED", f)]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.canceled_booking_count == 1
        assert summary.active_booking_count == 0

    def test_d5_mixed_active_and_canceled(self) -> None:
        f_active = _make_facts(net_to_property="850.00", currency="USD")
        f_cancel = _make_facts(net_to_property="1000.00", currency="USD")
        inputs = [
            ("bk_001", "BOOKING_CREATED", f_active),
            ("bk_002", "BOOKING_CANCELED", f_cancel),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.active_booking_count == 1
        assert summary.canceled_booking_count == 1
        # Only active booking's net counts
        assert summary.net_total == Decimal("850.00")
        assert summary.booking_count == 2

    def test_d6_two_canceled_count_is_two(self) -> None:
        f = _make_facts(currency="USD")
        inputs = [
            ("bk_001", "BOOKING_CANCELED", f),
            ("bk_002", "BOOKING_CANCELED", f),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.canceled_booking_count == 2
        assert summary.booking_count == 2


# ---------------------------------------------------------------------------
# Group E — Multi-currency guard
# ---------------------------------------------------------------------------

class TestGroupEMultiCurrency:

    def test_e1_mixed_currency_sets_MIXED(self) -> None:
        f_usd = _make_facts(currency="USD")
        f_eur = _make_facts(currency="EUR")
        inputs = [
            ("bk_001", "BOOKING_CREATED", f_usd),
            ("bk_002", "BOOKING_CREATED", f_eur),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.currency == "MIXED"

    def test_e2_mixed_currency_gross_total_is_none(self) -> None:
        f_usd = _make_facts(currency="USD")
        f_eur = _make_facts(currency="EUR")
        inputs = [
            ("bk_001", "BOOKING_CREATED", f_usd),
            ("bk_002", "BOOKING_CREATED", f_eur),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.gross_total is None

    def test_e3_mixed_currency_net_total_is_none(self) -> None:
        f_usd = _make_facts(currency="USD")
        f_eur = _make_facts(currency="EUR")
        inputs = [
            ("bk_001", "BOOKING_CREATED", f_usd),
            ("bk_002", "BOOKING_CREATED", f_eur),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.net_total is None

    def test_e4_mixed_currency_commission_is_none(self) -> None:
        f_usd = _make_facts(currency="USD")
        f_eur = _make_facts(currency="EUR")
        inputs = [
            ("bk_001", "BOOKING_CREATED", f_usd),
            ("bk_002", "BOOKING_CREATED", f_eur),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.total_commission is None

    def test_e5_same_currency_not_mixed(self) -> None:
        f1 = _make_facts(currency="USD")
        f2 = _make_facts(currency="USD")
        inputs = [
            ("bk_001", "BOOKING_CREATED", f1),
            ("bk_002", "BOOKING_CREATED", f2),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.currency == "USD"
        assert summary.gross_total is not None

    def test_e6_entries_still_populated_when_mixed(self) -> None:
        f_usd = _make_facts(currency="USD")
        f_eur = _make_facts(currency="EUR")
        inputs = [
            ("bk_001", "BOOKING_CREATED", f_usd),
            ("bk_002", "BOOKING_CREATED", f_eur),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert len(summary.entries) == 2

    def test_e7_three_currencies_is_mixed(self) -> None:
        inputs = [
            ("bk_001", "BOOKING_CREATED", _make_facts(currency="USD")),
            ("bk_002", "BOOKING_CREATED", _make_facts(currency="EUR")),
            ("bk_003", "BOOKING_CREATED", _make_facts(currency="GBP")),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.currency == "MIXED"


# ---------------------------------------------------------------------------
# Group F — Confidence breakdown
# ---------------------------------------------------------------------------

class TestGroupFConfidenceBreakdown:

    def test_f1_all_full_breakdown(self) -> None:
        f = _make_facts(source_confidence=CONFIDENCE_FULL)
        inputs = [
            ("bk_001", "BOOKING_CREATED", f),
            ("bk_002", "BOOKING_CREATED", f),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.confidence_breakdown[CONFIDENCE_FULL] == 2
        assert summary.confidence_breakdown[CONFIDENCE_PARTIAL] == 0
        assert summary.confidence_breakdown[CONFIDENCE_ESTIMATED] == 0

    def test_f2_all_partial_breakdown(self) -> None:
        f = _make_facts_partial()
        inputs = [("bk_001", "BOOKING_CREATED", f)]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.confidence_breakdown[CONFIDENCE_PARTIAL] == 1
        assert summary.confidence_breakdown[CONFIDENCE_FULL] == 0

    def test_f3_mixed_breakdown_counted_correctly(self) -> None:
        f_full = _make_facts(source_confidence=CONFIDENCE_FULL)
        f_est = _make_facts(source_confidence=CONFIDENCE_ESTIMATED)
        f_partial = _make_facts_partial()
        inputs = [
            ("bk_001", "BOOKING_CREATED", f_full),
            ("bk_002", "BOOKING_CREATED", f_est),
            ("bk_003", "BOOKING_CREATED", f_partial),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.confidence_breakdown[CONFIDENCE_FULL] == 1
        assert summary.confidence_breakdown[CONFIDENCE_ESTIMATED] == 1
        assert summary.confidence_breakdown[CONFIDENCE_PARTIAL] == 1

    def test_f4_breakdown_keys_always_present(self) -> None:
        summary = build_owner_statement("PROP-001", "2026-06", [])
        assert CONFIDENCE_FULL in summary.confidence_breakdown
        assert CONFIDENCE_PARTIAL in summary.confidence_breakdown
        assert CONFIDENCE_ESTIMATED in summary.confidence_breakdown

    def test_f5_breakdown_counts_canceled_entries(self) -> None:
        f_full = _make_facts(source_confidence=CONFIDENCE_FULL, currency="USD")
        inputs = [
            ("bk_001", "BOOKING_CREATED", f_full),
            ("bk_002", "BOOKING_CANCELED", f_full),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        # Both entries are FULL — canceled ones still count toward breakdown
        assert summary.confidence_breakdown[CONFIDENCE_FULL] == 2


# ---------------------------------------------------------------------------
# Group G — Statement confidence level
# ---------------------------------------------------------------------------

class TestGroupGStatementConfidenceLevel:

    def test_g1_all_full_gives_verified(self) -> None:
        f = _make_facts(source_confidence=CONFIDENCE_FULL)
        inputs = [
            ("bk_001", "BOOKING_CREATED", f),
            ("bk_002", "BOOKING_CREATED", f),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.statement_confidence == StatementConfidenceLevel.VERIFIED

    def test_g2_any_partial_gives_incomplete(self) -> None:
        f_full = _make_facts(source_confidence=CONFIDENCE_FULL)
        f_partial = _make_facts_partial()
        inputs = [
            ("bk_001", "BOOKING_CREATED", f_full),
            ("bk_002", "BOOKING_CREATED", f_partial),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.statement_confidence == StatementConfidenceLevel.INCOMPLETE

    def test_g3_full_and_estimated_gives_mixed(self) -> None:
        f_full = _make_facts(source_confidence=CONFIDENCE_FULL)
        f_est = _make_facts(source_confidence=CONFIDENCE_ESTIMATED)
        inputs = [
            ("bk_001", "BOOKING_CREATED", f_full),
            ("bk_002", "BOOKING_CREATED", f_est),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.statement_confidence == StatementConfidenceLevel.MIXED

    def test_g4_only_estimated_gives_mixed(self) -> None:
        f_est = _make_facts(source_confidence=CONFIDENCE_ESTIMATED)
        inputs = [("bk_001", "BOOKING_CREATED", f_est)]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.statement_confidence == StatementConfidenceLevel.MIXED

    def test_g5_empty_statement_gives_mixed(self) -> None:
        """No entries → no FULL, no PARTIAL → MIXED (no data to verify)."""
        summary = build_owner_statement("PROP-001", "2026-06", [])
        assert summary.statement_confidence == StatementConfidenceLevel.MIXED

    def test_g6_partial_overrides_full_and_estimated(self) -> None:
        f_full = _make_facts(source_confidence=CONFIDENCE_FULL)
        f_est = _make_facts(source_confidence=CONFIDENCE_ESTIMATED)
        f_partial = _make_facts_partial()
        inputs = [
            ("bk_001", "BOOKING_CREATED", f_full),
            ("bk_002", "BOOKING_CREATED", f_est),
            ("bk_003", "BOOKING_CREATED", f_partial),
        ]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        # PARTIAL present → INCOMPLETE wins over MIXED or VERIFIED
        assert summary.statement_confidence == StatementConfidenceLevel.INCOMPLETE

    def test_g7_statement_confidence_level_enum_values(self) -> None:
        assert StatementConfidenceLevel.VERIFIED == "VERIFIED"
        assert StatementConfidenceLevel.MIXED == "MIXED"
        assert StatementConfidenceLevel.INCOMPLETE == "INCOMPLETE"

    def test_g8_single_full_entry_verified(self) -> None:
        f = _make_facts(source_confidence=CONFIDENCE_FULL)
        inputs = [("bk_001", "BOOKING_CREATED", f)]
        summary = build_owner_statement("PROP-001", "2026-06", inputs)
        assert summary.statement_confidence == StatementConfidenceLevel.VERIFIED
