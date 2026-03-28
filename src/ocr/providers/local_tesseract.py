"""
Phase 983 — Local Tesseract Provider
======================================

General-purpose Tesseract OCR for identity documents without MRZ
(or as fallback when MRZ parsing fails).

Use cases:
  - National ID cards where MRZ is absent/damaged
  - Extracting visible text fields (name, ID number) not in MRZ
  - Driving licenses with no machine-readable zone

Pipeline:
  1. Preprocess for document OCR
  2. Run Tesseract in auto-page-segmentation mode
  3. Try to heuristically extract identity fields from raw text:
       - Name: first non-numeric multiword line
       - Document number: alphanumeric pattern
  4. Return OcrResult with lower confidence than MRZ (text-only is lossy)

Confidence: always lower than MRZ (0.55–0.75) — fields require review.
This provider is a FALLBACK of last resort for identity documents.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional

from ocr.provider_base import (
    OcrProvider, OcrRequest, OcrResult, OcrResultStatus, ImageQualityFlag
)
from ocr.image_preprocessing import preprocess_document, image_to_bytes

logger = logging.getLogger(__name__)

# Heuristic patterns for identity field extraction from free text
_DOC_NUMBER_PATTERN = re.compile(r'\b([A-Z]{1,3}[-\s]?\d{6,9}|\d{8,12})\b')
_NAME_MIN_WORDS = 2
_NAME_MAX_WORDS = 6


def _extract_name(text: str) -> Optional[str]:
    """
    Heuristically extract a person's name from OCR text.
    Looks for lines with 2–6 capitalized words, no digits.
    """
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        words = line.split()
        if _NAME_MIN_WORDS <= len(words) <= _NAME_MAX_WORDS:
            # Must be mostly alphabetic (allow spaces and hyphens)
            alpha_ratio = sum(1 for c in line if c.isalpha() or c in " -'") / max(len(line), 1)
            if alpha_ratio > 0.85:
                # Reject lines that look like labels
                lower = line.lower()
                if any(kw in lower for kw in ["name", "surname", "given", "date", "place", "republic", "national"]):
                    continue
                return line.title()
    return None


def _extract_doc_number(text: str) -> Optional[str]:
    """Heuristically extract document number from OCR text."""
    matches = _DOC_NUMBER_PATTERN.findall(text.upper())
    if matches:
        # Take the first plausible match
        return matches[0].replace(" ", "").replace("-", "")
    return None


def _run_tesseract_document(image_bytes: bytes) -> Optional[str]:
    """Run Tesseract in document mode. Returns text or None."""
    try:
        import pytesseract
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_bytes))
        # --psm 3: fully automatic page segmentation
        config = "--psm 3"
        return pytesseract.image_to_string(img, config=config, lang="eng")
    except ImportError:
        logger.warning("pytesseract not installed — Tesseract document OCR unavailable")
        return None
    except Exception as exc:
        logger.warning("Tesseract document OCR failed: %s", exc)
        return None


class LocalTesseractProvider(OcrProvider):
    """
    Track B fallback: Tesseract free-text OCR for identity documents.

    Lower confidence than MRZ provider. Provides partial extraction
    when MRZ is absent or damaged. Always yields requires_review=True.
    """

    SUPPORTED_CAPTURES = frozenset({"identity_document_capture"})
    SUPPORTED_DOCUMENTS = frozenset({"NATIONAL_ID", "DRIVING_LICENSE", "PASSPORT"})

    @property
    def provider_name(self) -> str:
        return "local_tesseract"

    @property
    def supported_capture_types(self) -> frozenset:
        return self.SUPPORTED_CAPTURES

    @property
    def supported_document_types(self) -> frozenset:
        return self.SUPPORTED_DOCUMENTS

    async def process(self, request: OcrRequest) -> OcrResult:
        start = time.monotonic()

        prep = preprocess_document(request.image_bytes)
        if not prep.ok:
            return self._make_failed_result(request, prep.error or "Preprocess failed")

        quality_warnings = [
            ImageQualityFlag(w) for w in prep.warnings
            if w in {f.value for f in ImageQualityFlag}
        ]

        img_bytes = image_to_bytes(prep.image)
        raw_text = _run_tesseract_document(img_bytes)

        elapsed = int((time.monotonic() - start) * 1000)

        if raw_text is None:
            return OcrResult(
                status=OcrResultStatus.FAILED,
                provider_name=self.provider_name,
                capture_type=request.capture_type,
                document_type=request.document_type,
                image_quality_score=prep.quality_score,
                quality_warnings=quality_warnings,
                processing_time_ms=elapsed,
                error_message="Tesseract binary not available",
            )

        # Heuristic field extraction
        name = _extract_name(raw_text)
        doc_number = _extract_doc_number(raw_text)

        extracted: dict = {}
        confidences: dict = {}

        if name:
            extracted["full_name"] = name
            confidences["full_name"] = 0.65  # text extraction, always lower confidence

        if doc_number:
            extracted["document_number"] = doc_number
            confidences["document_number"] = 0.60

        if not extracted:
            return OcrResult(
                status=OcrResultStatus.FAILED,
                provider_name=self.provider_name,
                capture_type=request.capture_type,
                document_type=request.document_type,
                image_quality_score=prep.quality_score,
                quality_warnings=quality_warnings,
                processing_time_ms=elapsed,
                error_message="Could not extract any identity fields from document",
            )

        return OcrResult(
            status=OcrResultStatus.PARTIAL,  # Always PARTIAL — needs review
            provider_name=self.provider_name,
            capture_type=request.capture_type,
            document_type=request.document_type,
            extracted_fields=extracted,
            field_confidences=confidences,
            image_quality_score=prep.quality_score,
            quality_warnings=quality_warnings,
            processing_time_ms=elapsed,
        )

    async def test_connection(self) -> dict:
        try:
            import pytesseract
            version = pytesseract.get_tesseract_version()
            return {
                "success": True,
                "message": f"Tesseract {version} available for document OCR",
                "response_time_ms": 0,
            }
        except ImportError:
            return {"success": False, "message": "pytesseract not installed", "response_time_ms": 0}
        except Exception as exc:
            return {"success": False, "message": f"Tesseract unavailable: {exc}", "response_time_ms": 0}
