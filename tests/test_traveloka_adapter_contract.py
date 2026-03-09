"""
Phase 88 — Contract tests for Traveloka Adapter.

Tests:
  A — TravelokaAdapter structure and provider name
  B — normalize: standard fields, TV- prefix stripping, financial extraction
  C — to_canonical_envelope: CREATE / CANCEL / BOOKING_AMENDED
  D — Financial extraction: _extract_traveloka (FULL / ESTIMATED / PARTIAL)
  E — Schema normalization: check_in_date, check_out_date, currency_code, booking_total
  F — Registry: TravelokaAdapter registered under "traveloka"
  G — Booking identity: TV- prefix stripped, unknown ID passthrough
  H — Amendment extraction: extract_amendment_traveloka
  I — Architectural notes: Traveloka vs other OTA adapters
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from adapters.ota.traveloka import TravelokaAdapter
from adapters.ota.registry import get_adapter
from adapters.ota.financial_extractor import extract_financial_facts
from adapters.ota.schema_normalizer import normalize_schema
from adapters.ota.booking_identity import normalize_reservation_ref
from adapters.ota.amendment_extractor import extract_amendment_traveloka
from adapters.ota.schemas import NormalizedBookingEvent, CanonicalEnvelope


# ---------------------------------------------------------------------------
# Test payloads
# ---------------------------------------------------------------------------

def _create_payload(
    booking_code="TV-98765432",
    event_reference="EVT-001",
    property_code="PROP-BALI-1",
    check_in_date="2026-12-01",
    check_out_date="2026-12-08",
    num_guests=2,
    booking_total="1200.00",
    traveloka_fee="120.00",
    net_payout="1080.00",
    currency_code="THB",
    event_type="BOOKING_CONFIRMED",
    tenant_id="tenant-th-01",
    occurred_at="2026-11-01T10:00:00",
) -> dict:
    return {
        "booking_code": booking_code,
        "event_reference": event_reference,
        "property_code": property_code,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "num_guests": num_guests,
        "booking_total": booking_total,
        "traveloka_fee": traveloka_fee,
        "net_payout": net_payout,
        "currency_code": currency_code,
        "event_type": event_type,
        "tenant_id": tenant_id,
        "occurred_at": occurred_at,
    }


def _classified(normalized, semantic_kind="CREATE"):
    mock = MagicMock()
    mock.normalized = normalized
    mock.semantic_kind = semantic_kind
    return mock


ADAPTER = TravelokaAdapter()


# ---------------------------------------------------------------------------
# Group A — Adapter structure
# ---------------------------------------------------------------------------

class TestAdapterStructure:

    def test_A1_provider_name_is_traveloka(self) -> None:
        assert ADAPTER.provider == "traveloka"

    def test_A2_has_normalize_method(self) -> None:
        assert callable(ADAPTER.normalize)

    def test_A3_has_to_canonical_envelope_method(self) -> None:
        assert callable(ADAPTER.to_canonical_envelope)


# ---------------------------------------------------------------------------
# Group B — normalize()
# ---------------------------------------------------------------------------

class TestNormalize:

    def test_B1_returns_normalized_booking_event(self) -> None:
        result = ADAPTER.normalize(_create_payload())
        assert isinstance(result, NormalizedBookingEvent)

    def test_B2_tv_prefix_stripped_from_booking_code(self) -> None:
        result = ADAPTER.normalize(_create_payload(booking_code="TV-98765432"))
        # normalize_reservation_ref strips TV- and lowercases
        assert result.reservation_id == "98765432"

    def test_B3_booking_code_without_prefix_unchanged(self) -> None:
        result = ADAPTER.normalize(_create_payload(booking_code="98765432"))
        assert result.reservation_id == "98765432"

    def test_B4_provider_is_traveloka(self) -> None:
        result = ADAPTER.normalize(_create_payload())
        assert result.provider == "traveloka"

    def test_B5_tenant_id_preserved(self) -> None:
        result = ADAPTER.normalize(_create_payload(tenant_id="tenant-id-12"))
        assert result.tenant_id == "tenant-id-12"

    def test_B6_property_code_becomes_property_id(self) -> None:
        result = ADAPTER.normalize(_create_payload(property_code="PROP-CM-7"))
        assert result.property_id == "PROP-CM-7"

    def test_B7_external_event_id_from_event_reference(self) -> None:
        result = ADAPTER.normalize(_create_payload(event_reference="EVT-XYZ-999"))
        assert result.external_event_id == "EVT-XYZ-999"

    def test_B8_occurred_at_parsed(self) -> None:
        result = ADAPTER.normalize(_create_payload(occurred_at="2026-12-01T09:30:00"))
        assert isinstance(result.occurred_at, datetime)

    def test_B9_financial_facts_populated(self) -> None:
        result = ADAPTER.normalize(_create_payload())
        assert result.financial_facts is not None
        assert result.financial_facts.provider == "traveloka"

    def test_B10_tv_prefix_case_insensitive_stripped(self) -> None:
        result = ADAPTER.normalize(_create_payload(booking_code="tv-12345678"))
        assert result.reservation_id == "12345678"


# ---------------------------------------------------------------------------
# Group C — to_canonical_envelope()
# ---------------------------------------------------------------------------

class TestToCanonicalEnvelope:

    def _normalize(self, **kwargs) -> NormalizedBookingEvent:
        return ADAPTER.normalize(_create_payload(**kwargs))

    def test_C1_create_produces_booking_created(self) -> None:
        classified = _classified(self._normalize(), semantic_kind="CREATE")
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.type == "BOOKING_CREATED"

    def test_C2_cancel_produces_booking_canceled(self) -> None:
        classified = _classified(self._normalize(), semantic_kind="CANCEL")
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.type == "BOOKING_CANCELED"

    def test_C3_amended_produces_booking_amended(self) -> None:
        payload = _create_payload()
        payload["modification"] = {
            "check_in_date": "2026-12-05",
            "check_out_date": "2026-12-12",
            "num_guests": 3,
            "modification_reason": "Guest request",
        }
        classified = _classified(ADAPTER.normalize(payload), semantic_kind="BOOKING_AMENDED")
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.type == "BOOKING_AMENDED"

    def test_C4_envelope_has_tenant_id(self) -> None:
        classified = _classified(self._normalize(tenant_id="t-001"), semantic_kind="CREATE")
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.tenant_id == "t-001"

    def test_C5_envelope_has_idempotency_key(self) -> None:
        classified = _classified(self._normalize(), semantic_kind="CREATE")
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.idempotency_key

    def test_C6_idempotency_key_is_deterministic(self) -> None:
        normalized = self._normalize(event_reference="EVT-FIXED-123")
        c1 = _classified(normalized, semantic_kind="CREATE")
        c2 = _classified(normalized, semantic_kind="CREATE")
        key1 = ADAPTER.to_canonical_envelope(c1).idempotency_key
        key2 = ADAPTER.to_canonical_envelope(c2).idempotency_key
        assert key1 == key2

    def test_C7_create_payload_has_provider(self) -> None:
        classified = _classified(self._normalize(), semantic_kind="CREATE")
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.payload["provider"] == "traveloka"

    def test_C8_amended_payload_has_amendment_fields(self) -> None:
        payload = _create_payload()
        payload["modification"] = {
            "check_in_date": "2026-12-05",
            "check_out_date": "2026-12-12",
            "num_guests": 3,
            "modification_reason": "Reschedule",
        }
        classified = _classified(ADAPTER.normalize(payload), semantic_kind="BOOKING_AMENDED")
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert "new_check_in" in envelope.payload
        assert "amendment_reason" in envelope.payload

    def test_C9_unsupported_kind_raises(self) -> None:
        classified = _classified(self._normalize(), semantic_kind="UNKNOWN_KIND")
        with pytest.raises(ValueError, match="Unsupported semantic kind"):
            ADAPTER.to_canonical_envelope(classified)

    def test_C10_returns_canonical_envelope(self) -> None:
        classified = _classified(self._normalize(), semantic_kind="CREATE")
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert isinstance(envelope, CanonicalEnvelope)


# ---------------------------------------------------------------------------
# Group D — Financial extraction
# ---------------------------------------------------------------------------

class TestFinancialExtraction:

    def test_D1_full_confidence_when_all_fields_present(self) -> None:
        facts = extract_financial_facts("traveloka", _create_payload())
        assert facts.source_confidence == "FULL"

    def test_D2_total_price_extracted(self) -> None:
        facts = extract_financial_facts("traveloka", _create_payload(booking_total="1500.00"))
        assert facts.total_price == Decimal("1500.00")

    def test_D3_traveloka_fee_extracted(self) -> None:
        facts = extract_financial_facts("traveloka", _create_payload(traveloka_fee="150.00"))
        assert facts.ota_commission == Decimal("150.00")

    def test_D4_net_payout_extracted(self) -> None:
        facts = extract_financial_facts("traveloka", _create_payload(net_payout="1350.00"))
        assert facts.net_to_property == Decimal("1350.00")

    def test_D5_currency_from_currency_code_field(self) -> None:
        facts = extract_financial_facts("traveloka", _create_payload(currency_code="IDR"))
        assert facts.currency == "IDR"

    def test_D6_estimated_when_net_payout_absent_but_derivable(self) -> None:
        payload = _create_payload()
        del payload["net_payout"]
        facts = extract_financial_facts("traveloka", payload)
        assert facts.source_confidence == "ESTIMATED"
        # net = 1200.00 - 120.00 = 1080.00
        assert facts.net_to_property == Decimal("1080.00")

    def test_D7_partial_when_no_booking_total(self) -> None:
        payload = _create_payload()
        del payload["booking_total"]
        del payload["net_payout"]
        del payload["traveloka_fee"]
        facts = extract_financial_facts("traveloka", payload)
        assert facts.source_confidence == "PARTIAL"

    def test_D8_provider_is_traveloka(self) -> None:
        facts = extract_financial_facts("traveloka", _create_payload())
        assert facts.provider == "traveloka"

    def test_D9_taxes_always_none(self) -> None:
        facts = extract_financial_facts("traveloka", _create_payload())
        assert facts.taxes is None


# ---------------------------------------------------------------------------
# Group E — Schema normalization
# ---------------------------------------------------------------------------

class TestSchemaNormalization:

    def test_E1_canonical_check_in_from_check_in_date(self) -> None:
        result = normalize_schema("traveloka", _create_payload(check_in_date="2026-12-01"))
        assert result["canonical_check_in"] == "2026-12-01"

    def test_E2_canonical_check_out_from_check_out_date(self) -> None:
        result = normalize_schema("traveloka", _create_payload(check_out_date="2026-12-08"))
        assert result["canonical_check_out"] == "2026-12-08"

    def test_E3_canonical_currency_from_currency_code(self) -> None:
        result = normalize_schema("traveloka", _create_payload(currency_code="VND"))
        assert result["canonical_currency"] == "VND"

    def test_E4_canonical_total_price_from_booking_total(self) -> None:
        result = normalize_schema("traveloka", _create_payload(booking_total="999.00"))
        assert result["canonical_total_price"] == "999.00"

    def test_E5_canonical_guest_count_from_num_guests(self) -> None:
        result = normalize_schema("traveloka", _create_payload(num_guests=4))
        assert result["canonical_guest_count"] == 4

    def test_E6_canonical_booking_ref_from_booking_code(self) -> None:
        result = normalize_schema("traveloka", _create_payload(booking_code="TV-11112222"))
        assert result["canonical_booking_ref"] == "TV-11112222"

    def test_E7_original_keys_preserved(self) -> None:
        payload = _create_payload()
        result = normalize_schema("traveloka", payload)
        assert result["booking_code"] == payload["booking_code"]
        assert result["property_code"] == payload["property_code"]


# ---------------------------------------------------------------------------
# Group F — Registry
# ---------------------------------------------------------------------------

class TestRegistry:

    def test_F1_traveloka_registered(self) -> None:
        adapter = get_adapter("traveloka")
        assert adapter is not None

    def test_F2_adapter_is_traveloka_adapter(self) -> None:
        adapter = get_adapter("traveloka")
        assert isinstance(adapter, TravelokaAdapter)

    def test_F3_provider_field_correct(self) -> None:
        adapter = get_adapter("traveloka")
        assert adapter.provider == "traveloka"


# ---------------------------------------------------------------------------
# Group G — Booking identity
# ---------------------------------------------------------------------------

class TestBookingIdentity:

    def test_G1_tv_prefix_stripped(self) -> None:
        result = normalize_reservation_ref("traveloka", "TV-12345678")
        assert result == "12345678"

    def test_G2_tv_prefix_case_insensitive(self) -> None:
        result = normalize_reservation_ref("traveloka", "tv-12345678")
        assert result == "12345678"

    def test_G3_no_prefix_unchanged(self) -> None:
        result = normalize_reservation_ref("traveloka", "12345678")
        assert result == "12345678"

    def test_G4_result_is_lowercase(self) -> None:
        result = normalize_reservation_ref("traveloka", "TV-ABCD1234")
        assert result == result.lower()

    def test_G5_whitespace_stripped(self) -> None:
        result = normalize_reservation_ref("traveloka", "  TV-12345678  ")
        assert "12345678" in result


# ---------------------------------------------------------------------------
# Group H — Amendment extraction
# ---------------------------------------------------------------------------

class TestAmendmentExtraction:

    def _mod_payload(self, **kwargs) -> dict:
        return {"modification": {
            "check_in_date": "2026-12-10",
            "check_out_date": "2026-12-17",
            "num_guests": 3,
            "modification_reason": "Dates changed",
            **kwargs
        }}

    def test_H1_new_check_in_extracted(self) -> None:
        result = extract_amendment_traveloka(self._mod_payload())
        assert result.new_check_in == "2026-12-10"

    def test_H2_new_check_out_extracted(self) -> None:
        result = extract_amendment_traveloka(self._mod_payload())
        assert result.new_check_out == "2026-12-17"

    def test_H3_new_guest_count_extracted(self) -> None:
        result = extract_amendment_traveloka(self._mod_payload())
        assert result.new_guest_count == 3

    def test_H4_amendment_reason_extracted(self) -> None:
        result = extract_amendment_traveloka(self._mod_payload())
        assert result.amendment_reason == "Dates changed"

    def test_H5_missing_modification_gives_none_fields(self) -> None:
        result = extract_amendment_traveloka({})
        assert result.new_check_in is None
        assert result.new_check_out is None
        assert result.new_guest_count is None
        assert result.amendment_reason is None


# ---------------------------------------------------------------------------
# Group I — Architectural / integration notes
# ---------------------------------------------------------------------------

class TestArchitecturalNotes:

    def test_I1_adapter_is_tier_15_sea_provider(self) -> None:
        """TravelokaAdapter.provider == 'traveloka' marks it Tier 1.5 SE Asia context."""
        assert ADAPTER.provider == "traveloka"

    def test_I2_booking_id_prefix_follows_phase_36_rule(self) -> None:
        """booking_id must be '{provider}_{reservation_id}' per Phase 36."""
        normalized = ADAPTER.normalize(_create_payload(booking_code="TV-12345678"))
        classified = _classified(normalized, semantic_kind="BOOKING_AMENDED")
        payload = _create_payload(booking_code="TV-12345678")
        payload["modification"] = {"check_in_date": "2026-12-10", "check_out_date": "2026-12-17"}
        classified2 = _classified(ADAPTER.normalize(payload), semantic_kind="BOOKING_AMENDED")
        envelope = ADAPTER.to_canonical_envelope(classified2)
        booking_id = envelope.payload["booking_id"]
        assert booking_id.startswith("traveloka_")
        assert "12345678" in booking_id

    def test_I3_financial_extractor_registered_separately(self) -> None:
        """extract_financial_facts dispatches to _extract_traveloka."""
        facts = extract_financial_facts("traveloka", _create_payload())
        assert facts.provider == "traveloka"
