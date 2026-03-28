"""
Phase 982 — OCR Provider Base
===============================

Abstract base class for all OCR providers.
Both Track A (Azure) and Track B (local) implement this interface.

Each provider:
  - Receives a capture request with image bytes + capture_type + document_type
  - Returns an OcrResult with extracted fields + per-field confidences
  - Reports processing time and provider metadata
  - Never raises on OCR failure — returns OcrResult with status='failed'
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ocr.confidence import OcrConfidenceReport, build_confidence_report

logger = logging.getLogger(__name__)


class OcrResultStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"           # some fields extracted, some failed
    FAILED = "failed"             # provider entirely failed
    UNSUPPORTED = "unsupported"   # provider doesn't support this capture/doc type


class ImageQualityFlag(str, Enum):
    BLUR = "blur"
    GLARE = "glare"
    DARK = "dark"
    CROPPED = "cropped"
    ANGLED = "angled"
    LOW_RESOLUTION = "low_resolution"


@dataclass
class OcrResult:
    """
    Normalized result from any OCR provider.

    This is the canonical output format — all providers produce this.
    The frontend consumes this structure for field review + confirmation.
    """
    status: OcrResultStatus
    provider_name: str
    capture_type: str
    document_type: Optional[str] = None

    # Extracted data
    extracted_fields: Dict[str, Optional[str]] = field(default_factory=dict)
    field_confidences: Dict[str, float] = field(default_factory=dict)

    # Quality
    image_quality_score: Optional[float] = None
    quality_warnings: List[ImageQualityFlag] = field(default_factory=list)

    # Metadata
    processing_time_ms: int = 0
    raw_response: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    @property
    def confidence_report(self) -> OcrConfidenceReport:
        """Build a confidence report from the extraction data."""
        fields_data = {}
        for name, value in self.extracted_fields.items():
            conf = self.field_confidences.get(name, 0.0)
            fields_data[name] = (value, conf, "ocr")
        return build_confidence_report(
            fields=fields_data,
            provider_name=self.provider_name,
            capture_type=self.capture_type,
        )

    @property
    def overall_confidence(self) -> float:
        return self.confidence_report.overall_confidence

    def to_dict(self) -> dict:
        """Serialize for API response / DB storage."""
        return {
            "status": self.status.value,
            "provider_name": self.provider_name,
            "capture_type": self.capture_type,
            "document_type": self.document_type,
            "extracted_fields": self.extracted_fields,
            "field_confidences": {
                k: round(v, 4) for k, v in self.field_confidences.items()
            },
            "overall_confidence": round(self.overall_confidence, 4),
            "confidence_report": self.confidence_report.to_dict(),
            "image_quality_score": (
                round(self.image_quality_score, 4)
                if self.image_quality_score is not None else None
            ),
            "quality_warnings": [w.value for w in self.quality_warnings],
            "processing_time_ms": self.processing_time_ms,
            "error_message": self.error_message,
        }


@dataclass
class OcrRequest:
    """Input to an OCR provider."""
    image_bytes: bytes
    capture_type: str              # validated by scope_guard before reaching provider
    document_type: Optional[str] = None  # 'PASSPORT', 'NATIONAL_ID', etc. (identity only)
    booking_id: Optional[str] = None
    tenant_id: Optional[str] = None
    hints: Optional[Dict[str, Any]] = None  # provider-specific hints


class OcrProvider(ABC):
    """
    Abstract base class for OCR providers.

    Implementations:
      - Track A: AzureDocumentIntelligenceProvider
      - Track B: LocalMrzProvider, LocalTesseractProvider, LocalMeterProvider
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'azure_document_intelligence')."""
        ...

    @property
    @abstractmethod
    def supported_capture_types(self) -> frozenset:
        """Set of capture_type values this provider handles."""
        ...

    @property
    @abstractmethod
    def supported_document_types(self) -> frozenset:
        """Set of document_type values this provider handles (for identity captures)."""
        ...

    @abstractmethod
    async def process(self, request: OcrRequest) -> OcrResult:
        """
        Process an OCR request and return normalized results.

        MUST NOT raise exceptions — return OcrResult with status=FAILED on error.

        Args:
            request: The OCR request with image bytes and metadata.

        Returns:
            OcrResult with extracted fields and confidence scores.
        """
        ...

    async def test_connection(self) -> dict:
        """
        Test the provider connection (for admin config page).

        Returns:
            {"success": bool, "message": str, "response_time_ms": int}
        """
        return {
            "success": True,
            "message": f"Provider '{self.provider_name}' is available",
            "response_time_ms": 0,
        }

    def supports_capture_type(self, capture_type: str) -> bool:
        """Check if this provider can handle the given capture type."""
        return (capture_type or "").strip().lower() in self.supported_capture_types

    def supports_document_type(self, document_type: str) -> bool:
        """Check if this provider can handle the given document type."""
        return (document_type or "").strip().upper() in self.supported_document_types

    def _make_failed_result(
        self,
        request: OcrRequest,
        error: str,
        elapsed_ms: int = 0,
    ) -> OcrResult:
        """Helper to create a FAILED result."""
        return OcrResult(
            status=OcrResultStatus.FAILED,
            provider_name=self.provider_name,
            capture_type=request.capture_type,
            document_type=request.document_type,
            processing_time_ms=elapsed_ms,
            error_message=error,
        )

    def _make_unsupported_result(self, request: OcrRequest) -> OcrResult:
        """Helper for unsupported capture/document type."""
        return OcrResult(
            status=OcrResultStatus.UNSUPPORTED,
            provider_name=self.provider_name,
            capture_type=request.capture_type,
            document_type=request.document_type,
            error_message=(
                f"Provider '{self.provider_name}' does not support "
                f"capture_type='{request.capture_type}' "
                f"document_type='{request.document_type}'"
            ),
        )
