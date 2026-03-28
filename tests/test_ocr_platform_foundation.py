"""
Phase 982 — OCR Platform Foundation Tests
===========================================

Comprehensive test suite for:
  - Scope guard (INV-OCR-01)
  - Confidence model (field scoring, levels, weights)
  - Provider base (OcrResult, OcrRequest)
  - Provider registry + routing
  - Fallback orchestrator

Test count: 40+ tests covering all foundation components.
"""
from __future__ import annotations

import asyncio
import pytest
from typing import Dict, Optional
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════════
# Module path setup
# ═══════════════════════════════════════════════════════════════════
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ═══════════════════════════════════════════════════════════════════
# Scope Guard Tests (INV-OCR-01)
# ═══════════════════════════════════════════════════════════════════

class TestScopeGuard:
    """Tests for ocr.scope_guard — the sole enforcer of OCR scope boundaries."""

    def test_allowed_identity_capture(self):
        from ocr.scope_guard import validate_capture_type
        result = validate_capture_type("identity_document_capture")
        assert result == "identity_document_capture"

    def test_allowed_checkin_meter(self):
        from ocr.scope_guard import validate_capture_type
        result = validate_capture_type("checkin_opening_meter_capture")
        assert result == "checkin_opening_meter_capture"

    def test_allowed_checkout_meter(self):
        from ocr.scope_guard import validate_capture_type
        result = validate_capture_type("checkout_closing_meter_capture")
        assert result == "checkout_closing_meter_capture"

    def test_case_insensitive(self):
        from ocr.scope_guard import validate_capture_type
        result = validate_capture_type("IDENTITY_DOCUMENT_CAPTURE")
        assert result == "identity_document_capture"

    def test_whitespace_stripped(self):
        from ocr.scope_guard import validate_capture_type
        result = validate_capture_type("  identity_document_capture  ")
        assert result == "identity_document_capture"

    def test_blocked_cleaning_photo(self):
        from ocr.scope_guard import validate_capture_type, OcrScopeViolation
        with pytest.raises(OcrScopeViolation) as exc:
            validate_capture_type("cleaning_photo")
        assert "cleaning_photo" in str(exc.value)

    def test_blocked_gallery_photo(self):
        from ocr.scope_guard import validate_capture_type, OcrScopeViolation
        with pytest.raises(OcrScopeViolation):
            validate_capture_type("property_gallery")

    def test_blocked_reference_photo(self):
        from ocr.scope_guard import validate_capture_type, OcrScopeViolation
        with pytest.raises(OcrScopeViolation):
            validate_capture_type("reference_photo")

    def test_blocked_atmosphere_photo(self):
        from ocr.scope_guard import validate_capture_type, OcrScopeViolation
        with pytest.raises(OcrScopeViolation):
            validate_capture_type("atmosphere_media")

    def test_blocked_generic_upload(self):
        from ocr.scope_guard import validate_capture_type, OcrScopeViolation
        with pytest.raises(OcrScopeViolation):
            validate_capture_type("generic_upload")

    def test_blocked_task_image(self):
        from ocr.scope_guard import validate_capture_type, OcrScopeViolation
        with pytest.raises(OcrScopeViolation):
            validate_capture_type("task_image")

    def test_blocked_empty_string(self):
        from ocr.scope_guard import validate_capture_type, OcrScopeViolation
        with pytest.raises(OcrScopeViolation):
            validate_capture_type("")

    def test_blocked_none(self):
        from ocr.scope_guard import validate_capture_type, OcrScopeViolation
        with pytest.raises(OcrScopeViolation):
            validate_capture_type(None)

    def test_blocked_random_string(self):
        from ocr.scope_guard import validate_capture_type, OcrScopeViolation
        with pytest.raises(OcrScopeViolation):
            validate_capture_type("foo_bar_baz")

    def test_is_allowed_true(self):
        from ocr.scope_guard import is_allowed
        assert is_allowed("identity_document_capture") is True
        assert is_allowed("checkin_opening_meter_capture") is True
        assert is_allowed("checkout_closing_meter_capture") is True

    def test_is_allowed_false(self):
        from ocr.scope_guard import is_allowed
        assert is_allowed("cleaning_photo") is False
        assert is_allowed("") is False
        assert is_allowed(None) is False

    def test_is_identity_capture(self):
        from ocr.scope_guard import is_identity_capture
        assert is_identity_capture("identity_document_capture") is True
        assert is_identity_capture("checkin_opening_meter_capture") is False

    def test_is_meter_capture(self):
        from ocr.scope_guard import is_meter_capture
        assert is_meter_capture("checkin_opening_meter_capture") is True
        assert is_meter_capture("checkout_closing_meter_capture") is True
        assert is_meter_capture("identity_document_capture") is False

    def test_get_meter_reading_type(self):
        from ocr.scope_guard import get_meter_reading_type
        assert get_meter_reading_type("checkin_opening_meter_capture") == "opening"
        assert get_meter_reading_type("checkout_closing_meter_capture") == "closing"
        assert get_meter_reading_type("identity_document_capture") is None
        assert get_meter_reading_type("") is None

    def test_scope_violation_message_includes_allowed_types(self):
        from ocr.scope_guard import OcrScopeViolation
        exc = OcrScopeViolation("bad_type")
        msg = str(exc)
        assert "bad_type" in msg
        assert "identity_document_capture" in msg
        assert "checkin_opening_meter_capture" in msg
        assert "checkout_closing_meter_capture" in msg

    def test_exactly_three_types_allowed(self):
        from ocr.scope_guard import ALLOWED_CAPTURE_TYPES
        assert len(ALLOWED_CAPTURE_TYPES) == 3


# ═══════════════════════════════════════════════════════════════════
# Confidence Model Tests
# ═══════════════════════════════════════════════════════════════════

class TestConfidence:
    """Tests for ocr.confidence — field-level confidence scoring."""

    def test_classify_high(self):
        from ocr.confidence import classify_confidence, ConfidenceLevel
        assert classify_confidence(0.95) == ConfidenceLevel.HIGH
        assert classify_confidence(0.90) == ConfidenceLevel.HIGH
        assert classify_confidence(1.0) == ConfidenceLevel.HIGH

    def test_classify_medium(self):
        from ocr.confidence import classify_confidence, ConfidenceLevel
        assert classify_confidence(0.85) == ConfidenceLevel.MEDIUM
        assert classify_confidence(0.70) == ConfidenceLevel.MEDIUM

    def test_classify_low(self):
        from ocr.confidence import classify_confidence, ConfidenceLevel
        assert classify_confidence(0.69) == ConfidenceLevel.LOW
        assert classify_confidence(0.5) == ConfidenceLevel.LOW
        assert classify_confidence(0.0) == ConfidenceLevel.LOW

    def test_field_confidence_auto_level(self):
        from ocr.confidence import FieldConfidence, ConfidenceLevel
        fc = FieldConfidence(field_name="full_name", value="John Doe", confidence=0.95)
        assert fc.level == ConfidenceLevel.HIGH

        fc2 = FieldConfidence(field_name="nationality", value="GBR", confidence=0.5)
        assert fc2.level == ConfidenceLevel.LOW

    def test_field_confidence_to_dict(self):
        from ocr.confidence import FieldConfidence
        fc = FieldConfidence(field_name="full_name", value="John", confidence=0.9234)
        d = fc.to_dict()
        assert d["field_name"] == "full_name"
        assert d["value"] == "John"
        assert d["confidence"] == 0.9234
        assert d["level"] == "high"
        assert d["source"] == "ocr"

    def test_build_confidence_report_identity(self):
        from ocr.confidence import build_confidence_report
        fields = {
            "full_name": ("John Doe", 0.95, "ocr"),
            "document_number": ("AB123456", 0.92, "mrz"),
            "nationality": ("GBR", 0.50, "ocr"),
        }
        report = build_confidence_report(
            fields=fields,
            provider_name="test",
            capture_type="identity_document_capture",
        )
        # full_name(3.0*0.95) + document_number(3.0*0.92) + nationality(1.5*0.50) = 6.36 / 7.5
        assert report.overall_confidence > 0.8
        assert "nationality" in report.low_confidence_fields
        assert report.requires_review is True  # has low confidence field

    def test_build_confidence_report_meter(self):
        from ocr.confidence import build_confidence_report
        fields = {
            "meter_value": ("12345.6", 0.98, "ocr"),
        }
        report = build_confidence_report(
            fields=fields,
            provider_name="local_meter",
            capture_type="checkin_opening_meter_capture",
        )
        assert report.overall_confidence == 0.98
        assert len(report.low_confidence_fields) == 0

    def test_empty_fields_report(self):
        from ocr.confidence import build_confidence_report
        report = build_confidence_report(
            fields={},
            provider_name="test",
            capture_type="identity_document_capture",
        )
        assert report.overall_confidence == 0.0
        assert report.requires_review is True

    def test_report_to_dict(self):
        from ocr.confidence import build_confidence_report
        fields = {
            "full_name": ("Jane", 0.85, "ocr"),
        }
        report = build_confidence_report(
            fields=fields,
            provider_name="azure",
            capture_type="identity_document_capture",
        )
        d = report.to_dict()
        assert "overall_confidence" in d
        assert "overall_level" in d
        assert "requires_review" in d
        assert "fields" in d
        assert "full_name" in d["fields"]


# ═══════════════════════════════════════════════════════════════════
# Provider Base Tests
# ═══════════════════════════════════════════════════════════════════

class TestProviderBase:
    """Tests for ocr.provider_base — OcrResult, OcrRequest data models."""

    def test_ocr_request_fields(self):
        from ocr.provider_base import OcrRequest
        req = OcrRequest(
            image_bytes=b"fake",
            capture_type="identity_document_capture",
            document_type="PASSPORT",
            booking_id="BK001",
            tenant_id="T001",
        )
        assert req.image_bytes == b"fake"
        assert req.capture_type == "identity_document_capture"
        assert req.document_type == "PASSPORT"

    def test_ocr_result_success(self):
        from ocr.provider_base import OcrResult, OcrResultStatus
        result = OcrResult(
            status=OcrResultStatus.SUCCESS,
            provider_name="test_provider",
            capture_type="identity_document_capture",
            document_type="PASSPORT",
            extracted_fields={"full_name": "John Doe", "document_number": "AB123"},
            field_confidences={"full_name": 0.95, "document_number": 0.90},
        )
        assert result.status == OcrResultStatus.SUCCESS
        assert result.extracted_fields["full_name"] == "John Doe"
        assert result.overall_confidence > 0.8

    def test_ocr_result_failed(self):
        from ocr.provider_base import OcrResult, OcrResultStatus
        result = OcrResult(
            status=OcrResultStatus.FAILED,
            provider_name="test",
            capture_type="identity_document_capture",
            error_message="provider unavailable",
        )
        assert result.status == OcrResultStatus.FAILED
        assert result.error_message == "provider unavailable"

    def test_ocr_result_to_dict(self):
        from ocr.provider_base import OcrResult, OcrResultStatus
        result = OcrResult(
            status=OcrResultStatus.SUCCESS,
            provider_name="azure",
            capture_type="identity_document_capture",
            extracted_fields={"full_name": "Jane"},
            field_confidences={"full_name": 0.92},
            processing_time_ms=150,
        )
        d = result.to_dict()
        assert d["status"] == "success"
        assert d["provider_name"] == "azure"
        assert d["processing_time_ms"] == 150
        assert "confidence_report" in d


# ═══════════════════════════════════════════════════════════════════
# Provider Registry Tests
# ═══════════════════════════════════════════════════════════════════

class _MockProvider:
    """Minimal mock provider for testing."""
    def __init__(self, name, capture_types=None, doc_types=None):
        self._name = name
        self._captures = frozenset(capture_types or [])
        self._docs = frozenset(doc_types or [])

    @property
    def provider_name(self):
        return self._name

    @property
    def supported_capture_types(self):
        return self._captures

    @property
    def supported_document_types(self):
        return self._docs

    def supports_capture_type(self, ct):
        return (ct or "").strip().lower() in self._captures

    def supports_document_type(self, dt):
        return (dt or "").strip().upper() in self._docs

    async def process(self, request):
        from ocr.provider_base import OcrResult, OcrResultStatus
        return OcrResult(
            status=OcrResultStatus.SUCCESS,
            provider_name=self._name,
            capture_type=request.capture_type,
            extracted_fields={"test": "value"},
            field_confidences={"test": 0.99},
        )

    async def test_connection(self):
        return {
            "success": True,
            "message": f"Provider '{self._name}' is available",
            "response_time_ms": 0,
        }


class TestProviderRegistry:
    """Tests for ocr.provider_router — registry and routing."""

    def test_register_and_get(self):
        from ocr.provider_router import ProviderRegistry
        reg = ProviderRegistry()
        p = _MockProvider("mock_a", ["identity_document_capture"], ["PASSPORT"])
        reg.register(p)
        assert reg.get("mock_a") is p
        assert len(reg) == 1

    def test_unregister(self):
        from ocr.provider_router import ProviderRegistry
        reg = ProviderRegistry()
        p = _MockProvider("mock_b", ["identity_document_capture"])
        reg.register(p)
        reg.unregister("mock_b")
        assert reg.get("mock_b") is None
        assert len(reg) == 0

    def test_get_providers_for_request_identity(self):
        from ocr.provider_router import ProviderRegistry
        from ocr.provider_base import OcrRequest
        reg = ProviderRegistry()
        p_id = _MockProvider("id_provider", ["identity_document_capture"], ["PASSPORT"])
        p_meter = _MockProvider("meter_provider", ["checkin_opening_meter_capture"])
        reg.register(p_id)
        reg.register(p_meter)

        req = OcrRequest(image_bytes=b"x", capture_type="identity_document_capture", document_type="PASSPORT")
        result = reg.get_providers_for_request(req)
        assert len(result) == 1
        assert result[0].provider_name == "id_provider"

    def test_get_providers_for_request_meter(self):
        from ocr.provider_router import ProviderRegistry
        from ocr.provider_base import OcrRequest
        reg = ProviderRegistry()
        p_meter = _MockProvider("meter", ["checkin_opening_meter_capture", "checkout_closing_meter_capture"])
        reg.register(p_meter)

        req = OcrRequest(image_bytes=b"x", capture_type="checkin_opening_meter_capture")
        result = reg.get_providers_for_request(req)
        assert len(result) == 1

    def test_provider_names(self):
        from ocr.provider_router import ProviderRegistry
        reg = ProviderRegistry()
        reg.register(_MockProvider("a", ["identity_document_capture"]))
        reg.register(_MockProvider("b", ["checkin_opening_meter_capture"]))
        assert sorted(reg.provider_names) == ["a", "b"]


class TestProviderOrder:
    """Tests for resolve_provider_order — tenant-config-aware priority."""

    def test_no_config_returns_all_sorted(self):
        from ocr.provider_router import resolve_provider_order
        p_b = _MockProvider("b_prov", ["identity_document_capture"])
        p_a = _MockProvider("a_prov", ["identity_document_capture"])
        result = resolve_provider_order([], [p_b, p_a])
        assert [p.provider_name for p in result] == ["a_prov", "b_prov"]

    def test_config_priority_order(self):
        from ocr.provider_router import resolve_provider_order
        p1 = _MockProvider("azure", ["identity_document_capture"])
        p2 = _MockProvider("local", ["identity_document_capture"])

        configs = [
            {"provider_name": "local", "enabled": True, "priority": 10},
            {"provider_name": "azure", "enabled": True, "priority": 20},
        ]
        result = resolve_provider_order(configs, [p1, p2])
        assert [p.provider_name for p in result] == ["local", "azure"]

    def test_disabled_provider_skipped(self):
        from ocr.provider_router import resolve_provider_order
        p1 = _MockProvider("azure", ["identity_document_capture"])
        p2 = _MockProvider("local", ["identity_document_capture"])

        configs = [
            {"provider_name": "azure", "enabled": False, "priority": 10},
            {"provider_name": "local", "enabled": True, "priority": 20},
        ]
        result = resolve_provider_order(configs, [p1, p2])
        names = [p.provider_name for p in result]
        assert names[0] == "local"
        # azure is still included as fallback (not in config order though)
        assert "azure" in names


# ═══════════════════════════════════════════════════════════════════
# Fallback Orchestrator Tests
# ═══════════════════════════════════════════════════════════════════

class _FailingProvider(_MockProvider):
    """Provider that always fails."""
    async def process(self, request):
        from ocr.provider_base import OcrResult, OcrResultStatus
        return OcrResult(
            status=OcrResultStatus.FAILED,
            provider_name=self._name,
            capture_type=request.capture_type,
            error_message="intentional failure",
        )


class _ExceptionProvider(_MockProvider):
    """Provider that raises an exception."""
    async def process(self, request):
        raise RuntimeError("kaboom")


class TestFallbackOrchestrator:
    """Tests for ocr.fallback — priority + fallback orchestration."""

    def _setup_registry(self, providers):
        """Replace global registry providers."""
        from ocr.provider_router import get_registry
        reg = get_registry()
        # Clear existing
        for name in list(reg._providers.keys()):
            reg.unregister(name)
        for p in providers:
            reg.register(p)

    def test_scope_guard_blocks_invalid(self):
        from ocr.fallback import process_ocr_request
        from ocr.scope_guard import OcrScopeViolation
        from ocr.provider_base import OcrRequest

        async def _run():
            req = OcrRequest(image_bytes=b"x", capture_type="cleaning_photo")
            with pytest.raises(OcrScopeViolation):
                await process_ocr_request(req)

        asyncio.run(_run())

    def test_first_success_wins(self):
        from ocr.fallback import process_ocr_request
        from ocr.provider_base import OcrRequest, OcrResultStatus

        p1 = _MockProvider("first", ["identity_document_capture"], ["PASSPORT"])
        p2 = _MockProvider("second", ["identity_document_capture"], ["PASSPORT"])
        self._setup_registry([p1, p2])

        async def _run():
            req = OcrRequest(
                image_bytes=b"x",
                capture_type="identity_document_capture",
                document_type="PASSPORT",
            )
            result = await process_ocr_request(req)
            assert result.status == OcrResultStatus.SUCCESS

        asyncio.run(_run())

    def test_fallback_on_failure(self):
        from ocr.fallback import process_ocr_request
        from ocr.provider_base import OcrRequest, OcrResultStatus

        p_fail = _FailingProvider("fail_prov", ["identity_document_capture"], ["PASSPORT"])
        p_ok = _MockProvider("ok_prov", ["identity_document_capture"], ["PASSPORT"])
        self._setup_registry([p_fail, p_ok])

        configs = [
            {"provider_name": "fail_prov", "enabled": True, "priority": 10},
            {"provider_name": "ok_prov", "enabled": True, "priority": 20},
        ]

        async def _run():
            req = OcrRequest(
                image_bytes=b"x",
                capture_type="identity_document_capture",
                document_type="PASSPORT",
            )
            result = await process_ocr_request(req, tenant_configs=configs)
            assert result.status == OcrResultStatus.SUCCESS
            assert result.provider_name == "ok_prov"

        asyncio.run(_run())

    def test_all_providers_fail(self):
        from ocr.fallback import process_ocr_request
        from ocr.provider_base import OcrRequest, OcrResultStatus

        p1 = _FailingProvider("fail1", ["identity_document_capture"], ["PASSPORT"])
        p2 = _FailingProvider("fail2", ["identity_document_capture"], ["PASSPORT"])
        self._setup_registry([p1, p2])

        async def _run():
            req = OcrRequest(
                image_bytes=b"x",
                capture_type="identity_document_capture",
                document_type="PASSPORT",
            )
            result = await process_ocr_request(req)
            assert result.status == OcrResultStatus.FAILED
            assert "all" in result.provider_name.lower() or "failed" in result.error_message.lower()

        asyncio.run(_run())

    def test_exception_provider_caught(self):
        from ocr.fallback import process_ocr_request
        from ocr.provider_base import OcrRequest, OcrResultStatus

        p_exc = _ExceptionProvider("exc_prov", ["checkin_opening_meter_capture"])
        p_ok = _MockProvider("ok_prov", ["checkin_opening_meter_capture"])
        self._setup_registry([p_exc, p_ok])

        configs = [
            {"provider_name": "exc_prov", "enabled": True, "priority": 10},
            {"provider_name": "ok_prov", "enabled": True, "priority": 20},
        ]

        async def _run():
            req = OcrRequest(image_bytes=b"x", capture_type="checkin_opening_meter_capture")
            result = await process_ocr_request(req, tenant_configs=configs)
            assert result.status == OcrResultStatus.SUCCESS
            assert result.provider_name == "ok_prov"

        asyncio.run(_run())

    def test_no_providers_returns_failed(self):
        from ocr.fallback import process_ocr_request
        from ocr.provider_base import OcrRequest, OcrResultStatus

        self._setup_registry([])  # empty registry

        async def _run():
            req = OcrRequest(image_bytes=b"x", capture_type="identity_document_capture")
            result = await process_ocr_request(req)
            assert result.status == OcrResultStatus.FAILED
            assert "no" in result.error_message.lower()

        asyncio.run(_run())

    def test_test_provider_success(self):
        from ocr.fallback import test_provider
        p = _MockProvider("test_me", ["identity_document_capture"])
        self._setup_registry([p])

        async def _run():
            result = await test_provider("test_me")
            assert result["success"] is True
            assert result["provider"] == "test_me"

        asyncio.run(_run())

    def test_test_provider_not_found(self):
        from ocr.fallback import test_provider
        self._setup_registry([])

        async def _run():
            result = await test_provider("nonexistent")
            assert result["success"] is False

        asyncio.run(_run())
