"""
Phase 65 Contract Tests: Financial Data Foundation

Verifies that:
- BookingFinancialFacts is immutable (frozen dataclass)
- extract_financial_facts() correctly extracts financial fields for all 5 providers
- Missing fields become None — no exceptions on absent data
- source_confidence reflects actual field completeness
- raw_financial_fields preserves verbatim provider values
- financial_facts attaches to NormalizedBookingEvent via adapter.normalize()

No live Supabase required. Pure unit/contract tests.

Run:
    cd "/Users/clawadmin/Antigravity Proj/ihouse-core"
    source .venv/bin/activate
    PYTHONPATH=src python3 -m pytest tests/test_financial_extractor_contract.py -v
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from adapters.ota.financial_extractor import (
    BookingFinancialFacts,
    CONFIDENCE_FULL,
    CONFIDENCE_PARTIAL,
    CONFIDENCE_ESTIMATED,
    extract_financial_facts,
)
from adapters.ota.bookingcom import BookingComAdapter
from adapters.ota.expedia import ExpediaAdapter
from adapters.ota.airbnb import AirbnbAdapter
from adapters.ota.agoda import AgodaAdapter
from adapters.ota.tripcom import TripComAdapter


# ---------------------------------------------------------------------------
# T0 — Immutability
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_bookingfinancialfacts_is_frozen(self):
        """BookingFinancialFacts must be frozen — mutation raises FrozenInstanceError."""
        facts = extract_financial_facts("bookingcom", {})
        with pytest.raises(FrozenInstanceError):
            facts.total_price = Decimal("100.00")  # type: ignore[misc]

    def test_bookingfinancialfacts_frozen_blocks_all_fields(self):
        """All fields on BookingFinancialFacts must be immutable (frozen=True)."""
        facts = extract_financial_facts("bookingcom", {"currency": "USD"})
        with pytest.raises(FrozenInstanceError):
            facts.currency = "EUR"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# T1 — Booking.com: full payload → FULL confidence
# ---------------------------------------------------------------------------

class TestBookingComExtractor:
    def _payload(self, **overrides):
        base = {
            "total_price": "250.00",
            "currency": "EUR",
            "commission": "37.50",
            "net": "212.50",
        }
        base.update(overrides)
        return base

    def test_full_payload_confidence_full(self):
        facts = extract_financial_facts("bookingcom", self._payload())
        assert facts.source_confidence == CONFIDENCE_FULL

    def test_total_price_extracted(self):
        facts = extract_financial_facts("bookingcom", self._payload())
        assert facts.total_price == Decimal("250.00")

    def test_currency_extracted(self):
        facts = extract_financial_facts("bookingcom", self._payload())
        assert facts.currency == "EUR"

    def test_commission_extracted_as_ota_commission(self):
        facts = extract_financial_facts("bookingcom", self._payload())
        assert facts.ota_commission == Decimal("37.50")

    def test_net_extracted_as_net_to_property(self):
        facts = extract_financial_facts("bookingcom", self._payload())
        assert facts.net_to_property == Decimal("212.50")

    def test_taxes_not_exposed(self):
        """Booking.com does not expose taxes in webhook — must be None."""
        facts = extract_financial_facts("bookingcom", self._payload())
        assert facts.taxes is None

    def test_partial_confidence_when_net_missing(self):
        payload = self._payload()
        del payload["net"]
        facts = extract_financial_facts("bookingcom", payload)
        assert facts.source_confidence == CONFIDENCE_PARTIAL
        assert facts.net_to_property is None

    def test_empty_payload_all_none(self):
        facts = extract_financial_facts("bookingcom", {})
        assert facts.total_price is None
        assert facts.currency is None
        assert facts.ota_commission is None
        assert facts.net_to_property is None
        assert facts.source_confidence == CONFIDENCE_PARTIAL

    def test_raw_financial_fields_preserved(self):
        facts = extract_financial_facts("bookingcom", self._payload())
        assert facts.raw_financial_fields["total_price"] == "250.00"
        assert facts.raw_financial_fields["currency"] == "EUR"
        assert facts.raw_financial_fields["commission"] == "37.50"
        assert facts.raw_financial_fields["net"] == "212.50"

    def test_provider_set_correctly(self):
        facts = extract_financial_facts("bookingcom", {})
        assert facts.provider == "bookingcom"


# ---------------------------------------------------------------------------
# T2 — Expedia: total_amount + commission_percent → ESTIMATED (derived net)
# ---------------------------------------------------------------------------

class TestExpediaExtractor:
    def _payload(self, **overrides):
        base = {
            "total_amount": "300.00",
            "currency": "USD",
            "commission_percent": "15",
        }
        base.update(overrides)
        return base

    def test_full_payload_confidence_estimated(self):
        """When both total_amount and commission_percent present → ESTIMATED (derived)."""
        facts = extract_financial_facts("expedia", self._payload())
        assert facts.source_confidence == CONFIDENCE_ESTIMATED

    def test_total_price_extracted(self):
        facts = extract_financial_facts("expedia", self._payload())
        assert facts.total_price == Decimal("300.00")

    def test_commission_derived_from_percent(self):
        """commission = total_amount * commission_percent / 100."""
        facts = extract_financial_facts("expedia", self._payload())
        assert facts.ota_commission == Decimal("45.00")

    def test_net_derived(self):
        """net = total_amount - derived_commission."""
        facts = extract_financial_facts("expedia", self._payload())
        assert facts.net_to_property == Decimal("255.00")

    def test_partial_when_no_commission_percent(self):
        payload = self._payload()
        del payload["commission_percent"]
        facts = extract_financial_facts("expedia", payload)
        assert facts.source_confidence == CONFIDENCE_PARTIAL
        assert facts.ota_commission is None
        assert facts.net_to_property is None

    def test_empty_payload_all_none_no_exception(self):
        facts = extract_financial_facts("expedia", {})
        assert facts.total_price is None
        assert facts.ota_commission is None
        assert facts.net_to_property is None

    def test_raw_financial_fields_preserved(self):
        facts = extract_financial_facts("expedia", self._payload())
        assert facts.raw_financial_fields["total_amount"] == "300.00"
        assert facts.raw_financial_fields["commission_percent"] == "15"


# ---------------------------------------------------------------------------
# T3 — Airbnb: payout_amount + booking_subtotal + taxes → PARTIAL
# ---------------------------------------------------------------------------

class TestAirbnbExtractor:
    def _payload(self, **overrides):
        base = {
            "payout_amount": "180.00",
            "booking_subtotal": "200.00",
            "taxes": "20.00",
            "currency": "USD",
        }
        base.update(overrides)
        return base

    def test_full_payload_confidence_full(self):
        """payout_amount + booking_subtotal both present → FULL."""
        facts = extract_financial_facts("airbnb", self._payload())
        assert facts.source_confidence == CONFIDENCE_FULL

    def test_net_to_property_is_payout_amount(self):
        facts = extract_financial_facts("airbnb", self._payload())
        assert facts.net_to_property == Decimal("180.00")

    def test_total_price_is_booking_subtotal(self):
        facts = extract_financial_facts("airbnb", self._payload())
        assert facts.total_price == Decimal("200.00")

    def test_taxes_extracted(self):
        facts = extract_financial_facts("airbnb", self._payload())
        assert facts.taxes == Decimal("20.00")

    def test_commission_not_exposed(self):
        """Airbnb does not expose OTA commission directly."""
        facts = extract_financial_facts("airbnb", self._payload())
        assert facts.ota_commission is None

    def test_partial_when_payout_missing(self):
        payload = self._payload()
        del payload["payout_amount"]
        facts = extract_financial_facts("airbnb", payload)
        assert facts.source_confidence == CONFIDENCE_PARTIAL
        assert facts.net_to_property is None

    def test_empty_payload_no_exception(self):
        facts = extract_financial_facts("airbnb", {})
        assert facts.total_price is None
        assert facts.net_to_property is None
        assert facts.taxes is None


# ---------------------------------------------------------------------------
# T4 — Agoda: selling_rate + net_rate → FULL confidence, implied commission
# ---------------------------------------------------------------------------

class TestAgodaExtractor:
    def _payload(self, **overrides):
        base = {
            "selling_rate": "220.00",
            "net_rate": "176.00",
            "currency": "THB",
        }
        base.update(overrides)
        return base

    def test_full_payload_confidence_full(self):
        facts = extract_financial_facts("agoda", self._payload())
        assert facts.source_confidence == CONFIDENCE_FULL

    def test_total_price_is_selling_rate(self):
        facts = extract_financial_facts("agoda", self._payload())
        assert facts.total_price == Decimal("220.00")

    def test_net_to_property_is_net_rate(self):
        facts = extract_financial_facts("agoda", self._payload())
        assert facts.net_to_property == Decimal("176.00")

    def test_implied_commission_derived(self):
        """commission = selling_rate - net_rate."""
        facts = extract_financial_facts("agoda", self._payload())
        assert facts.ota_commission == Decimal("44.00")

    def test_partial_when_net_rate_missing(self):
        payload = self._payload()
        del payload["net_rate"]
        facts = extract_financial_facts("agoda", payload)
        assert facts.source_confidence == CONFIDENCE_PARTIAL
        assert facts.net_to_property is None
        assert facts.ota_commission is None

    def test_empty_payload_no_exception(self):
        facts = extract_financial_facts("agoda", {})
        assert facts.total_price is None
        assert facts.net_to_property is None

    def test_raw_financial_fields_preserved(self):
        facts = extract_financial_facts("agoda", self._payload())
        assert facts.raw_financial_fields["selling_rate"] == "220.00"
        assert facts.raw_financial_fields["net_rate"] == "176.00"


# ---------------------------------------------------------------------------
# T5 — Trip.com: order_amount + channel_fee → ESTIMATED (derived net)
# ---------------------------------------------------------------------------

class TestTripComExtractor:
    def _payload(self, **overrides):
        base = {
            "order_amount": "400.00",
            "channel_fee": "40.00",
            "currency": "CNY",
        }
        base.update(overrides)
        return base

    def test_full_payload_confidence_estimated(self):
        """order_amount + channel_fee → derived net → ESTIMATED."""
        facts = extract_financial_facts("tripcom", self._payload())
        assert facts.source_confidence == CONFIDENCE_ESTIMATED

    def test_total_price_is_order_amount(self):
        facts = extract_financial_facts("tripcom", self._payload())
        assert facts.total_price == Decimal("400.00")

    def test_channel_fee_as_ota_commission(self):
        facts = extract_financial_facts("tripcom", self._payload())
        assert facts.ota_commission == Decimal("40.00")

    def test_net_derived(self):
        """net = order_amount - channel_fee."""
        facts = extract_financial_facts("tripcom", self._payload())
        assert facts.net_to_property == Decimal("360.00")

    def test_partial_when_channel_fee_missing(self):
        payload = self._payload()
        del payload["channel_fee"]
        facts = extract_financial_facts("tripcom", payload)
        assert facts.source_confidence == CONFIDENCE_PARTIAL
        assert facts.net_to_property is None

    def test_empty_payload_no_exception(self):
        facts = extract_financial_facts("tripcom", {})
        assert facts.total_price is None
        assert facts.net_to_property is None


# ---------------------------------------------------------------------------
# T6 — Unknown provider raises ValueError (programming error guard)
# ---------------------------------------------------------------------------

class TestUnknownProvider:
    def test_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="No financial extractor registered"):
            extract_financial_facts("unknown_ota", {})


# ---------------------------------------------------------------------------
# T7 — Integration: adapter.normalize() attaches financial_facts
# ---------------------------------------------------------------------------

def _base_payload_for(provider: str) -> dict:
    """Minimal valid payload for each provider (identity fields only, no financial)."""
    bases = {
        "bookingcom": {
            "tenant_id": "t1",
            "event_id": "e1",
            "reservation_id": "r1",
            "property_id": "p1",
            "occurred_at": "2026-03-08T12:00:00",
            "event_type": "reservation_created",
        },
        "expedia": {
            "tenant_id": "t1",
            "event_id": "e1",
            "reservation_id": "r1",
            "property_id": "p1",
            "occurred_at": "2026-03-08T12:00:00",
            "event_type": "reservation_created",
        },
        "airbnb": {
            "tenant_id": "t1",
            "event_id": "e1",
            "reservation_id": "r1",
            "listing_id": "p1",          # Airbnb uses listing_id
            "occurred_at": "2026-03-08T12:00:00",
            "event_type": "reservation_created",
        },
        "agoda": {
            "tenant_id": "t1",
            "event_id": "e1",
            "booking_ref": "r1",         # Agoda uses booking_ref
            "property_id": "p1",
            "occurred_at": "2026-03-08T12:00:00",
            "event_type": "reservation_created",
        },
        "tripcom": {
            "tenant_id": "t1",
            "event_id": "e1",
            "order_id": "r1",            # Trip.com uses order_id
            "hotel_id": "p1",            # Trip.com uses hotel_id
            "occurred_at": "2026-03-08T12:00:00",
            "event_type": "booking_created",
        },
    }
    return bases[provider]


class TestAdapterIntegration:
    @pytest.mark.parametrize("adapter,provider", [
        (BookingComAdapter(), "bookingcom"),
        (ExpediaAdapter(), "expedia"),
        (AirbnbAdapter(), "airbnb"),
        (AgodaAdapter(), "agoda"),
        (TripComAdapter(), "tripcom"),
    ])
    def test_normalize_returns_financial_facts_instance(self, adapter, provider):
        """All 5 adapters must return BookingFinancialFacts from normalize()."""
        payload = _base_payload_for(provider)
        normalized = adapter.normalize(payload)
        assert isinstance(normalized.financial_facts, BookingFinancialFacts)

    @pytest.mark.parametrize("adapter,provider", [
        (BookingComAdapter(), "bookingcom"),
        (ExpediaAdapter(), "expedia"),
        (AirbnbAdapter(), "airbnb"),
        (AgodaAdapter(), "agoda"),
        (TripComAdapter(), "tripcom"),
    ])
    def test_normalize_financial_facts_provider_matches(self, adapter, provider):
        """financial_facts.provider matches the adapter's provider string."""
        payload = _base_payload_for(provider)
        normalized = adapter.normalize(payload)
        assert normalized.financial_facts.provider == provider

    def test_bookingcom_with_financial_fields_attached(self):
        """Booking.com normalize() with financial fields produces non-None total_price."""
        payload = _base_payload_for("bookingcom")
        payload["total_price"] = "150.00"
        payload["currency"] = "USD"
        payload["commission"] = "22.50"
        payload["net"] = "127.50"

        adapter = BookingComAdapter()
        normalized = adapter.normalize(payload)

        assert normalized.financial_facts.total_price == Decimal("150.00")
        assert normalized.financial_facts.currency == "USD"
        assert normalized.financial_facts.ota_commission == Decimal("22.50")
        assert normalized.financial_facts.net_to_property == Decimal("127.50")
        assert normalized.financial_facts.source_confidence == CONFIDENCE_FULL

    def test_financial_facts_not_in_canonical_envelope(self):
        """
        financial_facts must NOT appear in the canonical envelope.
        Invariant: booking_state must never contain financial data.
        """
        from adapters.ota.service import ingest_provider_event

        payload = _base_payload_for("bookingcom")
        payload["total_price"] = "150.00"
        payload["currency"] = "USD"

        envelope = ingest_provider_event(
            provider="bookingcom",
            payload=payload,
            tenant_id="t1",
        )
        # financial_facts must not leak into the canonical envelope payload
        assert "financial_facts" not in envelope.payload
        assert "total_price" not in envelope.payload    # only in raw provider_payload
        assert "currency" not in envelope.payload
