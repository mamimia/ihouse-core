"""
Phase 48 — Contract tests for idempotency key standardization.

Verifies that:
1. generate_idempotency_key produces expected format
2. Different providers → different keys for same event_id
3. Same event_id, different event_type → different keys
4. Keys are lowercase and stripped
5. Colons in values are sanitized
6. Empty components raise ValueError
7. validate_idempotency_key accepts valid, rejects malformed
8. BookingCom adapter emits standard key format
9. Expedia adapter emits standard key format
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# generate_idempotency_key
# ---------------------------------------------------------------------------

class TestGenerateIdempotencyKey:

    def test_produces_expected_format(self) -> None:
        from adapters.ota.idempotency import generate_idempotency_key
        key = generate_idempotency_key("bookingcom", "ev_001", "BOOKING_CREATED")
        assert key == "bookingcom:booking_created:ev_001"

    def test_different_providers_different_keys(self) -> None:
        from adapters.ota.idempotency import generate_idempotency_key
        k1 = generate_idempotency_key("bookingcom", "ev_001", "BOOKING_CREATED")
        k2 = generate_idempotency_key("expedia", "ev_001", "BOOKING_CREATED")
        assert k1 != k2

    def test_same_event_id_different_type_different_keys(self) -> None:
        from adapters.ota.idempotency import generate_idempotency_key
        k_create = generate_idempotency_key("bookingcom", "ev_001", "BOOKING_CREATED")
        k_cancel = generate_idempotency_key("bookingcom", "ev_001", "BOOKING_CANCELED")
        assert k_create != k_cancel

    def test_keys_are_lowercase(self) -> None:
        from adapters.ota.idempotency import generate_idempotency_key
        key = generate_idempotency_key("BookingCom", "EV_001", "BOOKING_CREATED")
        assert key == key.lower()

    def test_leading_trailing_whitespace_stripped(self) -> None:
        from adapters.ota.idempotency import generate_idempotency_key
        key = generate_idempotency_key("  bookingcom  ", "  ev_001  ", "  BOOKING_CREATED  ")
        assert " " not in key

    def test_colon_in_event_id_is_sanitized(self) -> None:
        from adapters.ota.idempotency import generate_idempotency_key
        key = generate_idempotency_key("bookingcom", "ev:001", "BOOKING_CREATED")
        # colon in event_id replaced with underscore → 3 segments still
        parts = key.split(":")
        assert len(parts) == 3

    def test_deterministic_same_input_same_output(self) -> None:
        from adapters.ota.idempotency import generate_idempotency_key
        k1 = generate_idempotency_key("bookingcom", "ev_999", "BOOKING_CANCELED")
        k2 = generate_idempotency_key("bookingcom", "ev_999", "BOOKING_CANCELED")
        assert k1 == k2

    def test_empty_provider_raises(self) -> None:
        from adapters.ota.idempotency import generate_idempotency_key
        with pytest.raises(ValueError, match="provider"):
            generate_idempotency_key("", "ev_001", "BOOKING_CREATED")

    def test_empty_event_id_raises(self) -> None:
        from adapters.ota.idempotency import generate_idempotency_key
        with pytest.raises(ValueError, match="event_id"):
            generate_idempotency_key("bookingcom", "", "BOOKING_CREATED")

    def test_empty_event_type_raises(self) -> None:
        from adapters.ota.idempotency import generate_idempotency_key
        with pytest.raises(ValueError, match="event_type"):
            generate_idempotency_key("bookingcom", "ev_001", "")


# ---------------------------------------------------------------------------
# validate_idempotency_key
# ---------------------------------------------------------------------------

class TestValidateIdempotencyKey:

    def test_valid_key_returns_true(self) -> None:
        from adapters.ota.idempotency import validate_idempotency_key
        assert validate_idempotency_key("bookingcom:booking_created:ev_001") is True

    def test_empty_string_returns_false(self) -> None:
        from adapters.ota.idempotency import validate_idempotency_key
        assert validate_idempotency_key("") is False

    def test_none_returns_false(self) -> None:
        from adapters.ota.idempotency import validate_idempotency_key
        assert validate_idempotency_key(None) is False  # type: ignore[arg-type]

    def test_two_segments_returns_false(self) -> None:
        from adapters.ota.idempotency import validate_idempotency_key
        assert validate_idempotency_key("bookingcom:ev_001") is False

    def test_four_segments_returns_false(self) -> None:
        from adapters.ota.idempotency import validate_idempotency_key
        assert validate_idempotency_key("a:b:c:d") is False

    def test_expedia_key_valid(self) -> None:
        from adapters.ota.idempotency import generate_idempotency_key, validate_idempotency_key
        key = generate_idempotency_key("expedia", "XID-9182", "BOOKING_CANCELED")
        assert validate_idempotency_key(key) is True


# ---------------------------------------------------------------------------
# Adapter integration
# ---------------------------------------------------------------------------

class TestAdapterIdempotencyKeyFormat:

    def _base_payload(self, event_type: str) -> dict:
        return {
            "tenant_id": "tenant_001",
            "event_id": "ev_adapter_001",
            "reservation_id": "res_001",
            "property_id": "prop_001",
            "occurred_at": "2026-03-08T10:00:00",
            "event_type": event_type,
        }

    def test_bookingcom_create_key_uses_standard_format(self) -> None:
        from adapters.ota.bookingcom import BookingComAdapter
        from adapters.ota.idempotency import validate_idempotency_key
        adapter = BookingComAdapter()
        normalized = adapter.normalize(self._base_payload("reservation_created"))
        from adapters.ota.semantics import classify_normalized_event
        classified = classify_normalized_event(normalized)
        envelope = adapter.to_canonical_envelope(classified)
        assert validate_idempotency_key(envelope.idempotency_key)
        assert "bookingcom" in envelope.idempotency_key
        assert "booking_created" in envelope.idempotency_key

    def test_expedia_cancel_key_uses_standard_format(self) -> None:
        from adapters.ota.expedia import ExpediaAdapter
        from adapters.ota.idempotency import validate_idempotency_key
        adapter = ExpediaAdapter()
        normalized = adapter.normalize(self._base_payload("reservation_cancelled"))
        from adapters.ota.semantics import classify_normalized_event
        classified = classify_normalized_event(normalized)
        envelope = adapter.to_canonical_envelope(classified)
        assert validate_idempotency_key(envelope.idempotency_key)
        assert "expedia" in envelope.idempotency_key
        assert "booking_canceled" in envelope.idempotency_key

    def test_same_event_id_different_providers_different_keys(self) -> None:
        """Cross-provider collision prevention."""
        from adapters.ota.bookingcom import BookingComAdapter
        from adapters.ota.expedia import ExpediaAdapter
        from adapters.ota.semantics import classify_normalized_event

        payload = self._base_payload("reservation_created")

        bc_adapter = BookingComAdapter()
        bc_normalized = bc_adapter.normalize(payload)
        bc_classified = classify_normalized_event(bc_normalized)
        bc_envelope = bc_adapter.to_canonical_envelope(bc_classified)

        ex_adapter = ExpediaAdapter()
        ex_normalized = ex_adapter.normalize(payload)
        ex_classified = classify_normalized_event(ex_normalized)
        ex_envelope = ex_adapter.to_canonical_envelope(ex_classified)

        assert bc_envelope.idempotency_key != ex_envelope.idempotency_key
