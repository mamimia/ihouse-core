"""
Phase 125 — Hotelbeds Adapter — Contract Tests

Tests for adapters/ota/hotelbeds.py, financial_extractor (hotelbeds),
booking_identity (hotelbeds), and registry.

Groups:
    A — HB- prefix stripping (booking_identity)
    B — normalize() shape and field mapping
    C — to_canonical_envelope() — CREATE / CANCEL / AMENDED
    D — financial_extractor — B2B semantics (net_rate, markup, contract_price)
    E — registry presence
    F — Replay / fixture contract (deterministic)
    G — Invariants (no booking_state reads, pure extraction)
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from adapters.ota.hotelbeds import HotelbedsAdapter
from adapters.ota.booking_identity import normalize_reservation_ref, build_booking_id
from adapters.ota.financial_extractor import extract_financial_facts
from adapters.ota.registry import get_adapter
from adapters.ota.schemas import ClassifiedBookingEvent, NormalizedBookingEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _base_payload(
    event_type: str = "BOOKING_CONFIRMED",
    voucher_ref: str = "HB-20260101-88991",
    guest_count: int = 2,
    contract_price: str = "350.00",
    net_rate: str = "280.00",
    markup_amount: str | None = "70.00",
    currency: str = "EUR",
) -> dict:
    payload = {
        "voucher_ref": voucher_ref,
        "hotel_code": "HTB-PROP-001",
        "event_id": "evt-hb-001",
        "event_type": event_type,
        "check_in": "2026-04-10",
        "check_out": "2026-04-15",
        "room_count": 1,
        "guest_count": guest_count,
        "contract_price": contract_price,
        "net_rate": net_rate,
        "currency": currency,
        "occurred_at": "2026-03-09T10:00:00",
        "tenant_id": "tenant_test",
    }
    if markup_amount is not None:
        payload["markup_amount"] = markup_amount
    return payload


def _amendment_payload() -> dict:
    p = _base_payload(event_type="BOOKING_AMENDED")
    p["amendment"] = {
        "check_in": "2026-04-12",
        "check_out": "2026-04-17",
        "room_count": 2,
        "guest_count": 4,
        "reason": "Guest changed dates",
    }
    return p


def _normalize(payload: dict) -> NormalizedBookingEvent:
    return HotelbedsAdapter().normalize(payload)


def _classify(normalized: NormalizedBookingEvent, kind: str) -> ClassifiedBookingEvent:
    return ClassifiedBookingEvent(normalized=normalized, semantic_kind=kind)


# ===========================================================================
# Group A — HB- prefix stripping
# ===========================================================================

class TestGroupA_PrefixStripping:

    def test_a1_hb_prefix_stripped(self) -> None:
        """A1: 'HB-20260101-88991' → '20260101-88991'."""
        assert normalize_reservation_ref("hotelbeds", "HB-20260101-88991") == "20260101-88991"

    def test_a2_lowercase_hb_prefix_stripped(self) -> None:
        """A2: 'hb-20260101-88991' → '20260101-88991'."""
        assert normalize_reservation_ref("hotelbeds", "hb-20260101-88991") == "20260101-88991"

    def test_a3_no_prefix_unchanged(self) -> None:
        """A3: Ref without HB- prefix left unchanged (lowercased)."""
        assert normalize_reservation_ref("hotelbeds", "20260101-88991") == "20260101-88991"

    def test_a4_whitespace_stripped(self) -> None:
        """A4: Leading/trailing whitespace removed before prefix strip."""
        assert normalize_reservation_ref("hotelbeds", "  HB-REF999  ") == "ref999"

    def test_a5_booking_id_format(self) -> None:
        """A5: build_booking_id produces 'hotelbeds_20260101-88991'."""
        assert build_booking_id("hotelbeds", "HB-20260101-88991") == "hotelbeds_20260101-88991"

    def test_a6_empty_ref_handled(self) -> None:
        """A6: Empty string returns empty string (no crash)."""
        assert normalize_reservation_ref("hotelbeds", "") == ""


# ===========================================================================
# Group B — normalize() shape and field mapping
# ===========================================================================

class TestGroupB_Normalize:

    def test_b1_provider_is_hotelbeds(self) -> None:
        """B1: provider = 'hotelbeds'."""
        norm = _normalize(_base_payload())
        assert norm.provider == "hotelbeds"

    def test_b2_tenant_id_preserved(self) -> None:
        """B2: tenant_id from payload is preserved."""
        norm = _normalize(_base_payload())
        assert norm.tenant_id == "tenant_test"

    def test_b3_reservation_id_stripped(self) -> None:
        """B3: reservation_id has HB- stripped."""
        norm = _normalize(_base_payload(voucher_ref="HB-20260101-88991"))
        assert norm.reservation_id == "20260101-88991"

    def test_b4_property_id_from_hotel_code(self) -> None:
        """B4: property_id = hotel_code field."""
        norm = _normalize(_base_payload())
        assert norm.property_id == "HTB-PROP-001"

    def test_b5_external_event_id_from_event_id(self) -> None:
        """B5: external_event_id = event_id field."""
        norm = _normalize(_base_payload())
        assert norm.external_event_id == "evt-hb-001"

    def test_b6_occurred_at_is_datetime(self) -> None:
        """B6: occurred_at is a datetime instance."""
        norm = _normalize(_base_payload())
        assert isinstance(norm.occurred_at, datetime)

    def test_b7_financial_facts_present(self) -> None:
        """B7: financial_facts is populated."""
        norm = _normalize(_base_payload())
        assert norm.financial_facts is not None

    def test_b8_financial_facts_provider_is_hotelbeds(self) -> None:
        """B8: financial_facts.provider = 'hotelbeds'."""
        norm = _normalize(_base_payload())
        assert norm.financial_facts.provider == "hotelbeds"


# ===========================================================================
# Group C — to_canonical_envelope()
# ===========================================================================

class TestGroupC_CanonicalEnvelope:

    def test_c1_create_type(self) -> None:
        """C1: BOOKING_CONFIRMED → BOOKING_CREATED."""
        norm = _normalize(_base_payload(event_type="BOOKING_CONFIRMED"))
        classified = _classify(norm, "CREATE")
        env = HotelbedsAdapter().to_canonical_envelope(classified)
        assert env.type == "BOOKING_CREATED"

    def test_c2_cancel_type(self) -> None:
        """C2: BOOKING_CANCELLED → BOOKING_CANCELED."""
        norm = _normalize(_base_payload(event_type="BOOKING_CANCELLED"))
        classified = _classify(norm, "CANCEL")
        env = HotelbedsAdapter().to_canonical_envelope(classified)
        assert env.type == "BOOKING_CANCELED"

    def test_c3_amended_type(self) -> None:
        """C3: BOOKING_AMENDED → BOOKING_AMENDED."""
        norm = _normalize(_amendment_payload())
        classified = _classify(norm, "BOOKING_AMENDED")
        env = HotelbedsAdapter().to_canonical_envelope(classified)
        assert env.type == "BOOKING_AMENDED"

    def test_c4_booking_id_format(self) -> None:
        """C4: AMENDED payload → booking_id='hotelbeds_{ref}'."""
        norm = _normalize(_amendment_payload())
        classified = _classify(norm, "BOOKING_AMENDED")
        env = HotelbedsAdapter().to_canonical_envelope(classified)
        assert env.payload["booking_id"].startswith("hotelbeds_")

    def test_c5_tenant_id_in_envelope(self) -> None:
        """C5: tenant_id is preserved in envelope."""
        norm = _normalize(_base_payload())
        classified = _classify(norm, "CREATE")
        env = HotelbedsAdapter().to_canonical_envelope(classified)
        assert env.tenant_id == "tenant_test"

    def test_c6_idempotency_key_stable(self) -> None:
        """C6: Same payload → same idempotency_key (deterministic)."""
        p = _base_payload()
        env1 = HotelbedsAdapter().to_canonical_envelope(
            _classify(_normalize(p), "CREATE")
        )
        env2 = HotelbedsAdapter().to_canonical_envelope(
            _classify(_normalize(p), "CREATE")
        )
        assert env1.idempotency_key == env2.idempotency_key

    def test_c7_unsupported_kind_raises(self) -> None:
        """C7: Unknown semantic_kind → ValueError."""
        norm = _normalize(_base_payload())
        classified = _classify(norm, "UNKNOWN_KIND")
        with pytest.raises(ValueError):
            HotelbedsAdapter().to_canonical_envelope(classified)

    def test_c8_create_payload_has_provider(self) -> None:
        """C8: CREATE envelope has 'provider' = 'hotelbeds'."""
        norm = _normalize(_base_payload())
        env = HotelbedsAdapter().to_canonical_envelope(_classify(norm, "CREATE"))
        assert env.payload["provider"] == "hotelbeds"


# ===========================================================================
# Group D — financial_extractor B2B semantics
# ===========================================================================

class TestGroupD_FinancialExtractor:

    def test_d1_net_to_property_is_net_rate(self) -> None:
        """D1: net_to_property = net_rate (what property actually receives)."""
        facts = extract_financial_facts("hotelbeds", {
            "contract_price": "350.00",
            "net_rate": "280.00",
            "currency": "EUR",
        })
        assert facts.net_to_property == Decimal("280.00")

    def test_d2_total_price_is_contract_price(self) -> None:
        """D2: total_price = contract_price (what buyer pays Hotelbeds)."""
        facts = extract_financial_facts("hotelbeds", {
            "contract_price": "350.00",
            "net_rate": "280.00",
            "currency": "EUR",
        })
        assert facts.total_price == Decimal("350.00")

    def test_d3_explicit_markup_used_when_present(self) -> None:
        """D3: If markup_amount is present, use it as ota_commission."""
        facts = extract_financial_facts("hotelbeds", {
            "contract_price": "350.00",
            "net_rate": "280.00",
            "markup_amount": "70.00",
            "currency": "EUR",
        })
        assert facts.ota_commission == Decimal("70.00")

    def test_d4_markup_derived_when_absent_estimation(self) -> None:
        """D4: markup absent → derived = contract_price - net_rate → ESTIMATED."""
        facts = extract_financial_facts("hotelbeds", {
            "contract_price": "350.00",
            "net_rate": "280.00",
            "currency": "EUR",
        })
        assert facts.ota_commission == Decimal("70.00")
        assert facts.source_confidence == "ESTIMATED"

    def test_d5_full_confidence_when_all_present(self) -> None:
        """D5: All 3 fields + explicit markup → FULL confidence."""
        facts = extract_financial_facts("hotelbeds", {
            "contract_price": "350.00",
            "net_rate": "280.00",
            "markup_amount": "70.00",
            "currency": "EUR",
        })
        assert facts.source_confidence == "FULL"

    def test_d6_partial_when_net_rate_missing(self) -> None:
        """D6: Missing net_rate → PARTIAL confidence."""
        facts = extract_financial_facts("hotelbeds", {
            "contract_price": "350.00",
            "currency": "EUR",
        })
        assert facts.source_confidence == "PARTIAL"
        assert facts.net_to_property is None

    def test_d7_partial_when_currency_missing(self) -> None:
        """D7: Missing currency → PARTIAL confidence."""
        facts = extract_financial_facts("hotelbeds", {
            "net_rate": "280.00",
        })
        assert facts.source_confidence == "PARTIAL"

    def test_d8_raw_financial_fields_preserved(self) -> None:
        """D8: raw_financial_fields contains verbatim provider values."""
        facts = extract_financial_facts("hotelbeds", {
            "contract_price": "350.00",
            "net_rate": "280.00",
            "markup_amount": "70.00",
            "currency": "EUR",
        })
        assert facts.raw_financial_fields["net_rate"] == "280.00"

    def test_d9_b2b_null_taxes(self) -> None:
        """D9: Hotelbeds does not expose taxes separately → taxes=None."""
        facts = extract_financial_facts("hotelbeds", {
            "net_rate": "280.00",
            "currency": "EUR",
        })
        assert facts.taxes is None

    def test_d10_provider_is_hotelbeds(self) -> None:
        """D10: facts.provider = 'hotelbeds'."""
        facts = extract_financial_facts("hotelbeds", {
            "net_rate": "280.00",
            "currency": "EUR",
        })
        assert facts.provider == "hotelbeds"

    def test_d11_gbp_currency_preserved(self) -> None:
        """D11: GBP currency preserved as-is."""
        facts = extract_financial_facts("hotelbeds", {
            "net_rate": "200.00",
            "currency": "GBP",
        })
        assert facts.currency == "GBP"


# ===========================================================================
# Group E — Registry
# ===========================================================================

class TestGroupE_Registry:

    def test_e1_hotelbeds_in_registry(self) -> None:
        """E1: get_adapter('hotelbeds') returns HotelbedsAdapter."""
        adapter = get_adapter("hotelbeds")
        assert isinstance(adapter, HotelbedsAdapter)

    def test_e2_adapter_provider_slug(self) -> None:
        """E2: adapter.provider = 'hotelbeds'."""
        assert get_adapter("hotelbeds").provider == "hotelbeds"


# ===========================================================================
# Group F — Replay / fixture contract
# ===========================================================================

class TestGroupF_ReplayFixture:

    def test_f1_idempotency_same_event_id(self) -> None:
        """F1: Same event_id → same idempotency_key regardless of processing order."""
        p1 = _base_payload()
        p2 = _base_payload()
        n1 = _normalize(p1)
        n2 = _normalize(p2)
        e1 = HotelbedsAdapter().to_canonical_envelope(_classify(n1, "CREATE"))
        e2 = HotelbedsAdapter().to_canonical_envelope(_classify(n2, "CREATE"))
        assert e1.idempotency_key == e2.idempotency_key

    def test_f2_different_event_ids_different_keys(self) -> None:
        """F2: Different event_ids → different idempotency_keys."""
        p1 = _base_payload()
        p1["event_id"] = "evt-001"
        p2 = _base_payload()
        p2["event_id"] = "evt-002"
        e1 = HotelbedsAdapter().to_canonical_envelope(_classify(_normalize(p1), "CREATE"))
        e2 = HotelbedsAdapter().to_canonical_envelope(_classify(_normalize(p2), "CREATE"))
        assert e1.idempotency_key != e2.idempotency_key

    def test_f3_replay_fixture_booking_id(self) -> None:
        """F3: Canonical replay fixture booking_id format check."""
        norm = _normalize(_base_payload(voucher_ref="HB-20260101-88991"))
        env = HotelbedsAdapter().to_canonical_envelope(_classify(norm, "CREATE"))
        # booking_id must appear in envelope payload
        assert "hotelbeds" in str(env.payload)


# ===========================================================================
# Group G — Invariants
# ===========================================================================

class TestGroupG_Invariants:

    def test_g1_financial_facts_not_in_booking_state(self) -> None:
        """G1: financial_facts is on NormalizedBookingEvent, not in canonical_payload."""
        norm = _normalize(_base_payload())
        env = HotelbedsAdapter().to_canonical_envelope(_classify(norm, "CREATE"))
        # financial_facts must NOT be in the canonical payload
        assert "financial_facts" not in env.payload
        assert "net_rate" not in env.payload
        assert "contract_price" not in env.payload

    def test_g2_normalize_is_pure_no_side_effects(self) -> None:
        """G2: normalize does not mutate input payload."""
        p = _base_payload()
        before = dict(p)
        _normalize(p)
        assert p == before

    def test_g3_financial_extractor_is_pure(self) -> None:
        """G3: extract_financial_facts does not mutate input."""
        p = {"net_rate": "280.00", "currency": "EUR"}
        before = dict(p)
        extract_financial_facts("hotelbeds", p)
        assert p == before

    def test_g4_no_float_in_financial_facts(self) -> None:
        """G4: All monetary values are Decimal, not float."""
        facts = extract_financial_facts("hotelbeds", {
            "contract_price": "350.00",
            "net_rate": "280.00",
            "currency": "EUR",
        })
        for field in (facts.total_price, facts.net_to_property, facts.ota_commission):
            if field is not None:
                assert isinstance(field, Decimal), f"Expected Decimal, got {type(field)}"
