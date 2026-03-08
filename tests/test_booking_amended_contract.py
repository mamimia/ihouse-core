"""
Phase 51 Contract Tests: BOOKING_AMENDED Python Pipeline

Verifies that the OTA adapter pipeline correctly routes reservation_modified
events through to BOOKING_AMENDED canonical envelopes.

These are unit/contract tests — no live Supabase required.
For E2E live tests, see tests/test_booking_amended_e2e.py.

Run:
    cd "/Users/clawadmin/Antigravity Proj/ihouse-core"
    source .venv/bin/activate
    PYTHONPATH=src python3 -m pytest tests/test_booking_amended_contract.py -v -s
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from adapters.ota.service import ingest_provider_event
from adapters.ota.semantics import classify_normalized_event, BookingSemanticKind
from adapters.ota.validator import validate_classified_event, validate_canonical_envelope, SUPPORTED_CANONICAL_TYPES
from adapters.ota.schemas import NormalizedBookingEvent, ClassifiedBookingEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bookingcom_payload(
    *,
    event_id: str = "evt_amend_001",
    event_type: str = "reservation_modified",
    reservation_id: str = "res_amend_001",
    property_id: str = "prop_amend_001",
    tenant_id: str = "tenant_contract",
    new_check_in: str | None = "2026-10-01",
    new_check_out: str | None = "2026-10-07",
) -> Dict[str, Any]:
    """Build a minimal Booking.com webhook payload for an amendment event."""
    payload: Dict[str, Any] = {
        "event_id": event_id,
        "reservation_id": reservation_id,
        "property_id": property_id,
        "occurred_at": "2026-03-08T18:00:00",
        "event_type": event_type,
        "tenant_id": tenant_id,
        "new_reservation_info": {},
    }
    if new_check_in is not None:
        payload["new_reservation_info"]["arrival_date"] = new_check_in
    if new_check_out is not None:
        payload["new_reservation_info"]["departure_date"] = new_check_out
    return payload


def _normalized(event_type: str = "reservation_modified") -> NormalizedBookingEvent:
    return NormalizedBookingEvent(
        tenant_id="tenant_contract",
        provider="bookingcom",
        external_event_id="evt_001",
        reservation_id="res_001",
        property_id="prop_001",
        occurred_at=datetime(2026, 3, 8, 18, 0, 0, tzinfo=timezone.utc),
        payload={"event_type": event_type, "tenant_id": "tenant_contract"},
    )


# ---------------------------------------------------------------------------
# T1: Semantics layer
# ---------------------------------------------------------------------------

class TestSemanticsLayer:
    def test_reservation_modified_classifies_as_booking_amended(self):
        """reservation_modified → BOOKING_AMENDED semantic kind."""
        classified = classify_normalized_event(_normalized("reservation_modified"))
        assert classified.semantic_kind == "BOOKING_AMENDED"

    def test_modified_alias_classifies_as_booking_amended(self):
        """'modified' shorthand → BOOKING_AMENDED."""
        classified = classify_normalized_event(_normalized("modified"))
        assert classified.semantic_kind == "BOOKING_AMENDED"

    def test_amended_alias_classifies_as_booking_amended(self):
        """'amended' alias → BOOKING_AMENDED."""
        classified = classify_normalized_event(_normalized("amended"))
        assert classified.semantic_kind == "BOOKING_AMENDED"

    def test_create_still_classifies_as_create(self):
        """Regression: CREATE classification unchanged."""
        classified = classify_normalized_event(_normalized("reservation_created"))
        assert classified.semantic_kind == "CREATE"

    def test_cancel_still_classifies_as_cancel(self):
        """Regression: CANCEL classification unchanged."""
        classified = classify_normalized_event(_normalized("reservation_cancelled"))
        assert classified.semantic_kind == "CANCEL"

    def test_booking_amended_is_in_enum(self):
        """BOOKING_AMENDED exists as a BookingSemanticKind enum value."""
        assert BookingSemanticKind.BOOKING_AMENDED == "BOOKING_AMENDED"

    def test_modify_still_in_enum_for_backward_compat(self):
        """MODIFY is still in the enum (backward-compat), but not produced."""
        assert BookingSemanticKind.MODIFY == "MODIFY"


# ---------------------------------------------------------------------------
# T2: Validator layer
# ---------------------------------------------------------------------------

class TestValidatorLayer:
    def test_booking_amended_passes_classified_validation(self):
        """validate_classified_event allows BOOKING_AMENDED."""
        classified = ClassifiedBookingEvent(normalized=_normalized(), semantic_kind="BOOKING_AMENDED")
        # must not raise
        validate_classified_event(classified)

    def test_modify_raises_in_validator(self):
        """MODIFY semantic kind is unsupported — raises ValueError."""
        classified = ClassifiedBookingEvent(normalized=_normalized(), semantic_kind="MODIFY")
        with pytest.raises(ValueError, match="unsupported"):
            validate_classified_event(classified)

    def test_booking_amended_in_supported_canonical_types(self):
        """BOOKING_AMENDED is in SUPPORTED_CANONICAL_TYPES."""
        assert "BOOKING_AMENDED" in SUPPORTED_CANONICAL_TYPES

    def test_booking_created_still_in_supported_canonical_types(self):
        """Regression: BOOKING_CREATED remains in SUPPORTED_CANONICAL_TYPES."""
        assert "BOOKING_CREATED" in SUPPORTED_CANONICAL_TYPES

    def test_booking_canceled_still_in_supported_canonical_types(self):
        """Regression: BOOKING_CANCELED remains in SUPPORTED_CANONICAL_TYPES."""
        assert "BOOKING_CANCELED" in SUPPORTED_CANONICAL_TYPES


# ---------------------------------------------------------------------------
# T3: Pipeline — ingest_provider_event produces correct canonical envelope
# ---------------------------------------------------------------------------

class TestPipelineEnvelopeShape:
    def test_envelope_type_is_booking_amended(self):
        """Full pipeline: reservation_modified → type=BOOKING_AMENDED."""
        envelope = ingest_provider_event(
            provider="bookingcom",
            payload=_bookingcom_payload(),
            tenant_id="tenant_contract",
        )
        assert envelope.type == "BOOKING_AMENDED"

    def test_envelope_has_booking_id(self):
        """Canonical booking_id = {provider}_{reservation_id}."""
        envelope = ingest_provider_event(
            provider="bookingcom",
            payload=_bookingcom_payload(reservation_id="res_999"),
            tenant_id="tenant_contract",
        )
        assert envelope.payload["booking_id"] == "bookingcom_res_999"

    def test_envelope_has_new_check_in(self):
        """new_check_in from new_reservation_info.checkin propagates to envelope payload."""
        envelope = ingest_provider_event(
            provider="bookingcom",
            payload=_bookingcom_payload(new_check_in="2026-11-01"),
            tenant_id="tenant_contract",
        )
        assert envelope.payload["new_check_in"] == "2026-11-01"

    def test_envelope_has_new_check_out(self):
        """new_check_out from new_reservation_info.checkout propagates to envelope payload."""
        envelope = ingest_provider_event(
            provider="bookingcom",
            payload=_bookingcom_payload(new_check_out="2026-11-08"),
            tenant_id="tenant_contract",
        )
        assert envelope.payload["new_check_out"] == "2026-11-08"

    def test_envelope_missing_dates_are_none(self):
        """If no amendment dates in payload, new_check_in / new_check_out are None."""
        envelope = ingest_provider_event(
            provider="bookingcom",
            payload=_bookingcom_payload(new_check_in=None, new_check_out=None),
            tenant_id="tenant_contract",
        )
        assert envelope.payload["new_check_in"] is None
        assert envelope.payload["new_check_out"] is None

    def test_envelope_idempotency_key_format(self):
        """Idempotency key follows: {provider}:{canonical_type_lower}:{event_id}."""
        envelope = ingest_provider_event(
            provider="bookingcom",
            payload=_bookingcom_payload(event_id="evt_key_check"),
            tenant_id="tenant_contract",
        )
        assert envelope.idempotency_key == "bookingcom:booking_amended:evt_key_check"

    def test_envelope_tenant_id_propagated(self):
        """tenant_id is correctly propagated to the canonical envelope."""
        envelope = ingest_provider_event(
            provider="bookingcom",
            payload=_bookingcom_payload(),
            tenant_id="tenant_abc",
        )
        assert envelope.tenant_id == "tenant_abc"

    def test_envelope_passes_canonical_validation(self):
        """validate_canonical_envelope must not raise for BOOKING_AMENDED envelope."""
        envelope = ingest_provider_event(
            provider="bookingcom",
            payload=_bookingcom_payload(),
            tenant_id="tenant_contract",
        )
        # must not raise
        validate_canonical_envelope(envelope)


# ---------------------------------------------------------------------------
# T4: Regression — BOOKING_CREATED and BOOKING_CANCELED unaffected
# ---------------------------------------------------------------------------

class TestRegressionExistingKinds:
    def test_created_still_works(self):
        """BOOKING_CREATED pipeline path unaffected by Phase 51."""
        envelope = ingest_provider_event(
            provider="bookingcom",
            payload={
                "event_id": "evt_reg_create",
                "reservation_id": "res_reg_001",
                "property_id": "prop_reg_001",
                "occurred_at": "2026-03-08T18:00:00",
                "event_type": "reservation_created",
                "tenant_id": "tenant_reg",
            },
            tenant_id="tenant_reg",
        )
        assert envelope.type == "BOOKING_CREATED"
        assert envelope.idempotency_key == "bookingcom:booking_created:evt_reg_create"

    def test_canceled_still_works(self):
        """BOOKING_CANCELED pipeline path unaffected by Phase 51."""
        envelope = ingest_provider_event(
            provider="bookingcom",
            payload={
                "event_id": "evt_reg_cancel",
                "reservation_id": "res_reg_002",
                "property_id": "prop_reg_002",
                "occurred_at": "2026-03-08T18:00:00",
                "event_type": "reservation_cancelled",
                "tenant_id": "tenant_reg",
            },
            tenant_id="tenant_reg",
        )
        assert envelope.type == "BOOKING_CANCELED"
        assert envelope.idempotency_key == "bookingcom:booking_canceled:evt_reg_cancel"
