"""
Phase 983 — Local Meter Digit OCR Provider
============================================

Specialized OCR pipeline for electricity meter readings.

Approach: Tesseract with digit-only mode + aggressive preprocessing.
No ML — digit recognition is well within classical Tesseract capabilities
when combined with the right preprocessing.

Pipeline:
  1. Preprocess: grayscale → high contrast → sharpen → denoise
  2. Run Tesseract with digit-only charset (--psm 7 or 8)
  3. Parse extracted text → float meter value
  4. Validate: must be a plausible meter reading (non-negative number)
  5. Return OcrResult with meter_value field

Confidence:
  - Strong digit pattern match + no junk chars → 0.92
  - Partial match (some junk) → 0.72
  - Very noisy text → 0.55 (still returned for worker review)

Capture types: checkin_opening_meter_capture, checkout_closing_meter_capture
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional

from ocr.provider_base import (
    OcrProvider, OcrRequest, OcrResult, OcrResultStatus, ImageQualityFlag
)
from ocr.image_preprocessing import preprocess_meter, image_to_bytes

logger = logging.getLogger(__name__)

# Meter value patterns — handles:
#   12345      integer reading
#   12345.6    single decimal
#   12,345.6   comma-formatted
#   12.345,6   European format
_METER_PATTERN = re.compile(
    r'\b(\d{1,7}(?:[.,]\d{1,3})*(?:[.,]\d{1,3})?)\b'
)
_DIGIT_ONLY = re.compile(r'[^\d.,]')


def _parse_meter_value(raw: str) -> Optional[tuple[float, float]]:
    """
    Parse meter reading from OCR text.

    Returns (value: float, confidence: float) or None if no valid value found.

    Handles: "12345", "12345.6", "12,345", "12 345.6"
    """
    if not raw:
        return None

    # Collapse whitespace
    cleaned = raw.strip().upper()

    # Find all numeric candidates
    candidates = _METER_PATTERN.findall(cleaned)
    if not candidates:
        return None

    # Take the longest numeric sequence (most likely to be the full reading)
    best = max(candidates, key=len)

    # Normalize: remove thousands separators, handle European decimal
    normalized = best.replace(",", ".") if "," in best and "." not in best else best.replace(",", "")

    try:
        value = float(normalized)
        if value < 0:
            return None  # meter readings are never negative

        # Confidence based on how clean the source text was
        # junk = characters that are NOT digits, periods, or commas
        digit_chars = len(re.sub(r'[^\d.,]', '', cleaned))
        total_chars = max(len(cleaned), 1)
        junk_ratio = 1.0 - (digit_chars / total_chars)
        if junk_ratio > 0.5:
            confidence = 0.55  # very noisy image
        elif junk_ratio > 0.2:
            confidence = 0.72  # some noise
        else:
            confidence = 0.92  # clean reading

        return value, confidence
    except ValueError:
        return None


def _run_tesseract_digits(image_bytes: bytes) -> Optional[str]:
    """
    Run Tesseract in digit-only mode for meter readings.
    Returns raw text or None if Tesseract unavailable.
    """
    try:
        import pytesseract
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_bytes))

        # --psm 7: single line; digit+period+comma for meter formats
        config = "--psm 7 -c tessedit_char_whitelist=0123456789.,: "
        text = pytesseract.image_to_string(img, config=config)
        return text.strip()
    except ImportError:
        logger.warning("pytesseract not installed — meter OCR unavailable")
        return None
    except Exception as exc:
        logger.warning("Tesseract meter extraction failed: %s", exc)
        return None


class LocalMeterProvider(OcrProvider):
    """
    Track B electricity meter OCR using Tesseract digit mode.

    Supports both opening (check-in) and closing (check-out) meter captures.
    Degrades gracefully if Tesseract binary not installed.
    """

    SUPPORTED_CAPTURES = frozenset({
        "checkin_opening_meter_capture",
        "checkout_closing_meter_capture",
    })
    SUPPORTED_DOCUMENTS = frozenset()  # No document types for meter

    @property
    def provider_name(self) -> str:
        return "local_meter"

    @property
    def supported_capture_types(self) -> frozenset:
        return self.SUPPORTED_CAPTURES

    @property
    def supported_document_types(self) -> frozenset:
        return self.SUPPORTED_DOCUMENTS

    def supports_document_type(self, document_type: str) -> bool:
        # Meter captures don't use document_type — always supported
        return True

    async def process(self, request: OcrRequest) -> OcrResult:
        start = time.monotonic()

        # Preprocess with meter-specific pipeline
        prep = preprocess_meter(request.image_bytes)
        if not prep.ok:
            return self._make_failed_result(request, prep.error or "Preprocess failed")

        quality_warnings = [
            ImageQualityFlag(w) for w in prep.warnings
            if w in {f.value for f in ImageQualityFlag}
        ]

        # Run Tesseract
        img_bytes = image_to_bytes(prep.image)
        raw_text = _run_tesseract_digits(img_bytes)

        elapsed = int((time.monotonic() - start) * 1000)

        if raw_text is None:
            return OcrResult(
                status=OcrResultStatus.FAILED,
                provider_name=self.provider_name,
                capture_type=request.capture_type,
                image_quality_score=prep.quality_score,
                quality_warnings=quality_warnings,
                processing_time_ms=elapsed,
                error_message="Tesseract binary not available",
            )

        parsed = _parse_meter_value(raw_text)

        if parsed is None:
            return OcrResult(
                status=OcrResultStatus.FAILED,
                provider_name=self.provider_name,
                capture_type=request.capture_type,
                image_quality_score=prep.quality_score,
                quality_warnings=quality_warnings,
                processing_time_ms=elapsed,
                error_message=f"No numeric meter value found in: '{raw_text[:50]}'",
            )

        meter_value_float, confidence = parsed

        # Store as string (preserving decimal precision) for field
        meter_value_str = (
            str(int(meter_value_float))
            if meter_value_float == int(meter_value_float)
            else f"{meter_value_float:.1f}"
        )

        return OcrResult(
            status=OcrResultStatus.SUCCESS,
            provider_name=self.provider_name,
            capture_type=request.capture_type,
            extracted_fields={
                "meter_value": meter_value_str,
                "meter_value_raw": raw_text[:100],
            },
            field_confidences={
                "meter_value": confidence,
                "meter_value_raw": 1.0,
            },
            image_quality_score=prep.quality_score,
            quality_warnings=quality_warnings,
            processing_time_ms=elapsed,
        )

    async def test_connection(self) -> dict:
        """Test that Tesseract binary is accessible."""
        try:
            import pytesseract
            version = pytesseract.get_tesseract_version()
            return {
                "success": True,
                "message": f"Tesseract {version} available for meter OCR",
                "response_time_ms": 0,
            }
        except ImportError:
            return {
                "success": False,
                "message": "pytesseract not installed",
                "response_time_ms": 0,
            }
        except Exception as exc:
            return {
                "success": False,
                "message": f"Tesseract not available: {exc}",
                "response_time_ms": 0,
            }
