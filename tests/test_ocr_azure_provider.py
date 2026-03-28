"""
Phase 984 — Azure Document Intelligence Provider Tests
=======================================================

All Azure calls are mocked — no real credentials required.
Tests cover:
  - Provider interface properties
  - Response parsing (success, partial, empty, error)
  - Field mapping (Azure fields → normalized fields)
  - Credential masking (INV-OCR-03)
  - Fallback integration (Azure FAILED → Track B takes over)
  - Configuration (from_config, from_config_row)
  - test_connection (configured / unconfigured)
"""
from __future__ import annotations

import asyncio
import io
import json
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _make_jpeg_bytes():
    """Create minimal JPEG bytes for testing."""
    try:
        from PIL import Image
        img = Image.new("RGB", (100, 80), (180, 180, 180))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()
    except ImportError:
        return b"\xff\xd8\xff\xe0" + b"\x00" * 100  # minimal JPEG-like header


def _make_azure_response(fields: dict, doc_type: str = "idDocument.passport", confidence: float = 0.98) -> dict:
    """Build a synthetic Azure DI analyze response."""
    azure_fields = {}
    for name, (value, conf) in fields.items():
        azure_fields[name] = {
            "content": value,
            "confidence": conf,
            "valueString": value,
        }
    return {
        "status": "succeeded",
        "analyzeResult": {
            "documents": [{
                "docType": doc_type,
                "confidence": confidence,
                "fields": azure_fields,
            }]
        }
    }


# ═══════════════════════════════════════════════════════════════════
# Provider Interface Tests
# ═══════════════════════════════════════════════════════════════════

class TestAzureProviderInterface:
    """Basic interface checks."""

    def test_provider_name(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        p = AzureDocumentIntelligenceProvider()
        assert p.provider_name == "azure_document_intelligence"

    def test_supported_capture_types(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        p = AzureDocumentIntelligenceProvider()
        assert p.supports_capture_type("identity_document_capture")
        assert not p.supports_capture_type("checkin_opening_meter_capture")
        assert not p.supports_capture_type("checkout_closing_meter_capture")

    def test_supported_document_types(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        p = AzureDocumentIntelligenceProvider()
        assert p.supports_document_type("PASSPORT")
        assert p.supports_document_type("NATIONAL_ID")
        assert p.supports_document_type("DRIVING_LICENSE")
        assert not p.supports_document_type("METER")

    def test_from_config(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        p = AzureDocumentIntelligenceProvider.from_config({
            "endpoint": "https://myresource.cognitiveservices.azure.com",
            "api_key": "abc123",
            "timeout": 15,
        })
        assert p._endpoint == "https://myresource.cognitiveservices.azure.com"
        assert p._api_key == "abc123"
        assert p._timeout == 15.0

    def test_from_config_defaults(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        p = AzureDocumentIntelligenceProvider.from_config({})
        assert p._endpoint == ""
        assert p._api_key == ""
        assert p._timeout == 30.0

    def test_is_configured_false_when_empty(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        p = AzureDocumentIntelligenceProvider()
        assert not p._is_configured

    def test_is_configured_true(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        p = AzureDocumentIntelligenceProvider(
            endpoint="https://x.cognitiveservices.azure.com",
            api_key="key123",
        )
        assert p._is_configured

    def test_make_from_db_config(self):
        from ocr.providers.azure_di import make_azure_provider_from_db_config
        row = {
            "provider_name": "azure_document_intelligence",
            "config": {
                "endpoint": "https://test.cognitiveservices.azure.com",
                "api_key": "sk-test-key",
            }
        }
        p = make_azure_provider_from_db_config(row)
        assert p._endpoint == "https://test.cognitiveservices.azure.com"
        assert p._api_key == "sk-test-key"

    def test_make_from_db_config_json_string(self):
        """Config stored as JSON string in DB (edge case)."""
        from ocr.providers.azure_di import make_azure_provider_from_db_config
        row = {
            "config": json.dumps({"endpoint": "https://x.cog.azure.com", "api_key": "k"})
        }
        p = make_azure_provider_from_db_config(row)
        assert p._endpoint == "https://x.cog.azure.com"


# ═══════════════════════════════════════════════════════════════════
# Credential Masking Tests (INV-OCR-03)
# ═══════════════════════════════════════════════════════════════════

class TestCredentialMasking:
    """Verify credentials are never exposed in logs/output."""

    def test_key_masked_in_property(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        p = AzureDocumentIntelligenceProvider(api_key="sk-abcdefgh1234")
        masked = p._masked_key
        assert "sk-a" in masked      # first 4 chars
        assert "1234" in masked      # last 4 chars
        # Full key NOT in masked output
        assert "abcdefgh" not in masked

    def test_short_key_masked(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        p = AzureDocumentIntelligenceProvider(api_key="short")
        assert p._masked_key == "****"

    def test_empty_key_label(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        p = AzureDocumentIntelligenceProvider(api_key="")
        assert p._masked_key == "<not set>"

    def test_sanitize_response_removes_secrets(self):
        from ocr.providers.azure_di import _sanitize_response
        raw = {
            "analyzeResult": {"documents": []},
            "api_key": "secret123",
            "token": "bearer_xyz",
        }
        sanitized = _sanitize_response(raw)
        assert "api_key" not in sanitized
        assert "token" not in sanitized
        assert "analyzeResult" in sanitized


# ═══════════════════════════════════════════════════════════════════
# Response Parsing Tests
# ═══════════════════════════════════════════════════════════════════

class TestAzureResponseParsing:
    """Tests for _parse_response with synthetic Azure responses."""

    def _make_provider(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        return AzureDocumentIntelligenceProvider(
            endpoint="https://test.cognitiveservices.azure.com",
            api_key="test-key-12345678",
        )

    def _make_request(self, doc_type="PASSPORT"):
        from ocr.provider_base import OcrRequest
        return OcrRequest(
            image_bytes=_make_jpeg_bytes(),
            capture_type="identity_document_capture",
            document_type=doc_type,
        )

    def test_parse_full_passport_response(self):
        from ocr.provider_base import OcrResultStatus
        p = self._make_provider()
        req = self._make_request("PASSPORT")

        response = _make_azure_response({
            "FirstName": ("JOHN", 0.99),
            "LastName": ("SMITH", 0.99),
            "DocumentNumber": ("AB123456", 0.98),
            "DateOfBirth": ("1985-01-15", 0.97),
            "DateOfExpiration": ("2030-06-30", 0.97),
            "Nationality": ("GBR", 0.99),
            "CountryRegion": ("GBR", 0.99),
            "Sex": ("M", 0.99),
        }, doc_type="idDocument.passport")

        result = p._parse_response(
            raw_response=response,
            request=req,
            quality_warnings=[],
            image_quality_score=0.9,
            processing_time_ms=500,
        )

        assert result.status == OcrResultStatus.SUCCESS
        assert result.extracted_fields["first_name"] == "JOHN"
        assert result.extracted_fields["last_name"] == "SMITH"
        assert result.extracted_fields["document_number"] == "AB123456"
        assert result.extracted_fields["date_of_birth"] == "1985-01-15"
        assert result.extracted_fields["nationality"] == "GBR"
        assert result.extracted_fields["full_name"] == "JOHN SMITH"

    def test_parse_builds_full_name(self):
        """full_name assembled from first + last when not directly provided."""
        from ocr.provider_base import OcrResultStatus
        p = self._make_provider()
        req = self._make_request()

        response = _make_azure_response({
            "FirstName": ("ANNA", 0.95),
            "LastName": ("KOWALSKI", 0.95),
        })

        result = p._parse_response(
            raw_response=response, request=req,
            quality_warnings=[], image_quality_score=0.85, processing_time_ms=300,
        )

        assert result.status == OcrResultStatus.SUCCESS
        assert result.extracted_fields.get("full_name") == "ANNA KOWALSKI"

    def test_parse_detects_passport_doc_type(self):
        from ocr.provider_base import OcrResultStatus
        p = self._make_provider()
        req = self._make_request()

        response = _make_azure_response(
            {"FirstName": ("JANE", 0.95)},
            doc_type="idDocument.passport"
        )
        result = p._parse_response(
            raw_response=response, request=req,
            quality_warnings=[], image_quality_score=0.9, processing_time_ms=200,
        )
        assert result.document_type == "PASSPORT"

    def test_parse_detects_national_id_doc_type(self):
        from ocr.provider_base import OcrResultStatus
        p = self._make_provider()
        req = self._make_request("NATIONAL_ID")

        response = _make_azure_response(
            {"FirstName": ("JANE", 0.95)},
            doc_type="idDocument.nationalIdentityCard"
        )
        result = p._parse_response(
            raw_response=response, request=req,
            quality_warnings=[], image_quality_score=0.9, processing_time_ms=200,
        )
        assert result.document_type == "NATIONAL_ID"

    def test_parse_empty_documents_returns_failed(self):
        from ocr.provider_base import OcrResultStatus
        p = self._make_provider()
        req = self._make_request()

        response = {"status": "succeeded", "analyzeResult": {"documents": []}}
        result = p._parse_response(
            raw_response=response, request=req,
            quality_warnings=[], image_quality_score=0.9, processing_time_ms=200,
        )
        assert result.status == OcrResultStatus.FAILED
        assert "no documents" in result.error_message.lower()

    def test_parse_no_fields_returns_failed(self):
        from ocr.provider_base import OcrResultStatus
        p = self._make_provider()
        req = self._make_request()

        response = {
            "analyzeResult": {
                "documents": [{"docType": "idDocument.passport", "confidence": 0.5, "fields": {}}]
            }
        }
        result = p._parse_response(
            raw_response=response, request=req,
            quality_warnings=[], image_quality_score=0.9, processing_time_ms=200,
        )
        assert result.status == OcrResultStatus.FAILED

    def test_parse_confidence_capped_at_doc_confidence(self):
        """Field confidence never exceeds doc confidence + 0.05."""
        p = self._make_provider()
        req = self._make_request()

        doc_confidence = 0.70
        response = _make_azure_response(
            {"FirstName": ("JANE", 0.99)},  # field says 0.99
            confidence=doc_confidence,
        )
        result = p._parse_response(
            raw_response=response, request=req,
            quality_warnings=[], image_quality_score=0.9, processing_time_ms=200,
        )
        # Field confidence must be capped at doc_confidence + 0.05 = 0.75
        if "first_name" in result.field_confidences:
            assert result.field_confidences["first_name"] <= doc_confidence + 0.05 + 0.001

    def test_parse_quality_warnings_preserved(self):
        from ocr.provider_base import OcrResultStatus, ImageQualityFlag
        p = self._make_provider()
        req = self._make_request()

        response = _make_azure_response({"FirstName": ("JANE", 0.9)})
        result = p._parse_response(
            raw_response=response, request=req,
            quality_warnings=[ImageQualityFlag.BLUR, ImageQualityFlag.DARK],
            image_quality_score=0.4,
            processing_time_ms=300,
        )
        assert ImageQualityFlag.BLUR in result.quality_warnings
        assert ImageQualityFlag.DARK in result.quality_warnings
        assert result.image_quality_score == 0.4


# ═══════════════════════════════════════════════════════════════════
# Unconfigured Provider Tests
# ═══════════════════════════════════════════════════════════════════

class TestUnconfiguredProvider:
    """Provider returns FAILED cleanly when not configured."""

    def test_process_fails_when_not_configured(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        from ocr.provider_base import OcrRequest, OcrResultStatus

        p = AzureDocumentIntelligenceProvider()  # no credentials

        async def _run():
            req = OcrRequest(
                image_bytes=_make_jpeg_bytes(),
                capture_type="identity_document_capture",
                document_type="PASSPORT",
            )
            return await p.process(req)

        result = asyncio.run(_run())
        assert result.status == OcrResultStatus.FAILED
        assert "not configured" in result.error_message.lower()

    def test_test_connection_fails_when_not_configured(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider

        p = AzureDocumentIntelligenceProvider()

        async def _run():
            return await p.test_connection()

        result = asyncio.run(_run())
        assert result["success"] is False
        assert "not configured" in result["message"].lower()


# ═══════════════════════════════════════════════════════════════════
# Mocked HTTP Tests
# ═══════════════════════════════════════════════════════════════════

class TestAzureWithMockedHttp:
    """Azure provider with mocked httpx — tests the full process() flow."""

    def _make_provider(self):
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        return AzureDocumentIntelligenceProvider(
            endpoint="https://test.cognitiveservices.azure.com",
            api_key="test-key-12345678",
        )

    def test_process_success_via_mock(self):
        """Full process() with mocked Azure 202 → poll → succeeded."""
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        from ocr.provider_base import OcrRequest, OcrResultStatus
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_response = _make_azure_response({
            "FirstName": ("JOHN", 0.99),
            "LastName": ("DOE", 0.99),
            "DocumentNumber": ("X1234567", 0.98),
            "Nationality": ("USA", 0.97),
        })

        p = self._make_provider()

        async def _run():
            req = OcrRequest(
                image_bytes=_make_jpeg_bytes(),
                capture_type="identity_document_capture",
                document_type="PASSPORT",
            )
            # Mock _submit_analyze directly (avoids full httpx mock)
            p._submit_analyze = AsyncMock(return_value=(mock_response, "op-123"))
            return await p.process(req)

        result = asyncio.run(_run())
        assert result.status == OcrResultStatus.SUCCESS
        assert result.extracted_fields.get("first_name") == "JOHN"
        assert result.extracted_fields.get("last_name") == "DOE"
        assert result.extracted_fields.get("full_name") == "JOHN DOE"
        assert result.provider_name == "azure_document_intelligence"

    def test_process_fails_gracefully_on_http_error(self):
        """Azure HTTP failure → FAILED result, not exception."""
        from ocr.provider_base import OcrRequest, OcrResultStatus
        from unittest.mock import AsyncMock

        p = self._make_provider()

        async def _run():
            req = OcrRequest(
                image_bytes=_make_jpeg_bytes(),
                capture_type="identity_document_capture",
            )
            p._submit_analyze = AsyncMock(side_effect=RuntimeError("HTTP 503 from Azure"))
            return await p.process(req)

        result = asyncio.run(_run())
        assert result.status == OcrResultStatus.FAILED
        assert "Azure API error" in result.error_message

    def test_process_fails_gracefully_on_network_timeout(self):
        """Network timeout → FAILED result, not exception."""
        from ocr.provider_base import OcrRequest, OcrResultStatus
        from unittest.mock import AsyncMock

        p = self._make_provider()

        async def _run():
            req = OcrRequest(
                image_bytes=_make_jpeg_bytes(),
                capture_type="identity_document_capture",
            )
            import httpx
            p._submit_analyze = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            return await p.process(req)

        result = asyncio.run(_run())
        assert result.status == OcrResultStatus.FAILED

    def test_process_returns_correct_processing_time(self):
        """processing_time_ms is set and positive."""
        from ocr.provider_base import OcrRequest, OcrResultStatus
        from unittest.mock import AsyncMock

        mock_response = _make_azure_response({"FirstName": ("ANA", 0.9)})
        p = self._make_provider()

        async def _run():
            req = OcrRequest(
                image_bytes=_make_jpeg_bytes(),
                capture_type="identity_document_capture",
            )
            p._submit_analyze = AsyncMock(return_value=(mock_response, "op-456"))
            return await p.process(req)

        result = asyncio.run(_run())
        assert result.processing_time_ms >= 0


# ═══════════════════════════════════════════════════════════════════
# Fallback Integration Tests
# ═══════════════════════════════════════════════════════════════════

class TestAzureFallbackIntegration:
    """Azure as primary in the fallback chain → Track B takes over on failure."""

    def _setup_registry_azure_then_local(self):
        from ocr.provider_router import get_registry
        from ocr.providers.azure_di import AzureDocumentIntelligenceProvider
        from ocr.provider_base import OcrResult, OcrResultStatus

        reg = get_registry()
        for name in list(reg._providers.keys()):
            reg.unregister(name)

        # Azure unconfigured (will fail)
        azure = AzureDocumentIntelligenceProvider()  # no credentials
        reg.register(azure)

        # Inline mock local provider
        class _InlineMock:
            provider_name = "local_mrz"
            supported_capture_types = frozenset({"identity_document_capture"})
            supported_document_types = frozenset({"PASSPORT"})

            def supports_capture_type(self, ct):
                return ct in self.supported_capture_types

            def supports_document_type(self, dt):
                return dt in self.supported_document_types

            async def process(self, request):
                return OcrResult(
                    status=OcrResultStatus.SUCCESS,
                    provider_name="local_mrz",
                    capture_type=request.capture_type,
                    extracted_fields={"full_name": "MOCK RESULT"},
                    field_confidences={"full_name": 0.9},
                )

            async def test_connection(self):
                return {"success": True, "message": "ok", "response_time_ms": 0}

        reg.register(_InlineMock())
        return reg

    def test_azure_failure_triggers_local_fallback(self):
        from ocr.fallback import process_ocr_request
        from ocr.provider_base import OcrRequest, OcrResultStatus

        self._setup_registry_azure_then_local()
        configs = [
            {"provider_name": "azure_document_intelligence", "enabled": True, "priority": 10},
            {"provider_name": "local_mrz", "enabled": True, "priority": 20},
        ]

        async def _run():
            req = OcrRequest(
                image_bytes=_make_jpeg_bytes(),
                capture_type="identity_document_capture",
                document_type="PASSPORT",
            )
            return await process_ocr_request(req, tenant_configs=configs)

        result = asyncio.run(_run())
        # local_mrz (mock) should succeed
        assert result.status == OcrResultStatus.SUCCESS
        assert result.provider_name == "local_mrz"
