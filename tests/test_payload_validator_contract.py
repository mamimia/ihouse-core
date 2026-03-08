"""
Phase 47 — Contract tests for OTA Payload Boundary Validator.

Verifies that:
1. Valid payload → valid=True, errors=[]
2. Missing reservation_id → RESERVATION_ID_REQUIRED
3. Missing tenant_id → TENANT_ID_REQUIRED
4. Missing/invalid occurred_at → OCCURRED_AT_INVALID
5. Missing event_type → EVENT_TYPE_REQUIRED
6. Empty provider → PROVIDER_REQUIRED
7. Non-dict payload → PAYLOAD_MUST_BE_DICT
8. Multiple errors collected at once (not fail-fast)
9. PayloadValidationResult is frozen dataclass
10. pipeline.py raises ValueError on invalid payload
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_payload() -> dict:
    return {
        "reservation_id": "res_001",
        "tenant_id": "tenant_001",
        "property_id": "prop_001",
        "occurred_at": "2026-03-08T10:00:00Z",
        "event_type": "reservation_created",
    }


# ---------------------------------------------------------------------------
# Valid payload
# ---------------------------------------------------------------------------

class TestValidPayload:

    def test_valid_payload_returns_valid_true(self) -> None:
        from adapters.ota.payload_validator import validate_ota_payload
        result = validate_ota_payload("bookingcom", _valid_payload())
        assert result.valid is True
        assert result.errors == []

    def test_valid_payload_has_event_type_raw(self) -> None:
        from adapters.ota.payload_validator import validate_ota_payload
        result = validate_ota_payload("bookingcom", _valid_payload())
        assert result.event_type_raw == "reservation_created"

    def test_valid_payload_has_provider(self) -> None:
        from adapters.ota.payload_validator import validate_ota_payload
        result = validate_ota_payload("expedia", _valid_payload())
        assert result.provider == "expedia"

    def test_accepts_type_field_as_event_type(self) -> None:
        """Should accept 'type' as an alternative to 'event_type'."""
        payload = _valid_payload()
        del payload["event_type"]
        payload["type"] = "reservation_created"
        from adapters.ota.payload_validator import validate_ota_payload
        result = validate_ota_payload("bookingcom", payload)
        assert result.valid is True

    def test_accepts_action_field_as_event_type(self) -> None:
        payload = _valid_payload()
        del payload["event_type"]
        payload["action"] = "created"
        from adapters.ota.payload_validator import validate_ota_payload
        result = validate_ota_payload("bookingcom", payload)
        assert result.valid is True


# ---------------------------------------------------------------------------
# Individual rule failures
# ---------------------------------------------------------------------------

class TestValidationRules:

    def test_empty_provider_gives_provider_required(self) -> None:
        from adapters.ota.payload_validator import validate_ota_payload, PROVIDER_REQUIRED
        result = validate_ota_payload("", _valid_payload())
        assert result.valid is False
        assert PROVIDER_REQUIRED in result.errors

    def test_missing_reservation_id(self) -> None:
        payload = _valid_payload()
        del payload["reservation_id"]
        from adapters.ota.payload_validator import validate_ota_payload, RESERVATION_ID_REQUIRED
        result = validate_ota_payload("bookingcom", payload)
        assert RESERVATION_ID_REQUIRED in result.errors

    def test_empty_reservation_id(self) -> None:
        payload = {**_valid_payload(), "reservation_id": ""}
        from adapters.ota.payload_validator import validate_ota_payload, RESERVATION_ID_REQUIRED
        result = validate_ota_payload("bookingcom", payload)
        assert RESERVATION_ID_REQUIRED in result.errors

    def test_missing_tenant_id(self) -> None:
        payload = _valid_payload()
        del payload["tenant_id"]
        from adapters.ota.payload_validator import validate_ota_payload, TENANT_ID_REQUIRED
        result = validate_ota_payload("bookingcom", payload)
        assert TENANT_ID_REQUIRED in result.errors

    def test_missing_occurred_at(self) -> None:
        payload = _valid_payload()
        del payload["occurred_at"]
        from adapters.ota.payload_validator import validate_ota_payload, OCCURRED_AT_INVALID
        result = validate_ota_payload("bookingcom", payload)
        assert OCCURRED_AT_INVALID in result.errors

    def test_invalid_occurred_at_format(self) -> None:
        payload = {**_valid_payload(), "occurred_at": "not-a-date"}
        from adapters.ota.payload_validator import validate_ota_payload, OCCURRED_AT_INVALID
        result = validate_ota_payload("bookingcom", payload)
        assert OCCURRED_AT_INVALID in result.errors

    def test_missing_event_type(self) -> None:
        payload = _valid_payload()
        del payload["event_type"]
        from adapters.ota.payload_validator import validate_ota_payload, EVENT_TYPE_REQUIRED
        result = validate_ota_payload("bookingcom", payload)
        assert EVENT_TYPE_REQUIRED in result.errors

    def test_non_dict_payload_gives_payload_must_be_dict(self) -> None:
        from adapters.ota.payload_validator import validate_ota_payload, PAYLOAD_MUST_BE_DICT
        result = validate_ota_payload("bookingcom", "not a dict")
        assert PAYLOAD_MUST_BE_DICT in result.errors
        assert result.valid is False

    def test_multiple_errors_collected_at_once(self) -> None:
        """Not fail-fast — all errors returned together."""
        bad_payload = {
            "occurred_at": "bad-date",
            # missing reservation_id, tenant_id, event_type
        }
        from adapters.ota.payload_validator import (
            validate_ota_payload,
            RESERVATION_ID_REQUIRED, TENANT_ID_REQUIRED,
            OCCURRED_AT_INVALID, EVENT_TYPE_REQUIRED,
        )
        result = validate_ota_payload("bookingcom", bad_payload)
        assert result.valid is False
        assert RESERVATION_ID_REQUIRED in result.errors
        assert TENANT_ID_REQUIRED in result.errors
        assert OCCURRED_AT_INVALID in result.errors
        assert EVENT_TYPE_REQUIRED in result.errors

    def test_result_is_frozen(self) -> None:
        from adapters.ota.payload_validator import validate_ota_payload
        result = validate_ota_payload("bookingcom", _valid_payload())
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            result.valid = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------

class TestPipelineIntegration:

    def test_pipeline_raises_on_missing_reservation_id(self) -> None:
        """process_ota_event must raise before normalize() if payload invalid."""
        from adapters.ota.pipeline import process_ota_event
        bad_payload = {
            "event_id": "ev_001",
            "property_id": "prop_001",
            "occurred_at": "2026-03-08T10:00:00Z",
            "event_type": "reservation_created",
            # no reservation_id
        }
        with pytest.raises(ValueError, match="RESERVATION_ID_REQUIRED"):
            process_ota_event("bookingcom", bad_payload, "tenant_001")
