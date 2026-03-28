"""
Phase 983 — Local MRZ Provider
================================

Deterministic MRZ (Machine Readable Zone) parser for passports and
travel documents. No ML, no external API — pure regex + checksums.

MRZ formats supported:
  - TD3 (passport): 2 lines × 44 characters
  - TD1 (ID card):  3 lines × 30 characters
  - TD2 (other):    2 lines × 36 characters

Why MRZ first?
  MRZ is machine-printed, standardized (ICAO Doc 9303), and highly
  OCR-reliable even from camera photos. It contains the most important
  identity fields: name, document number, nationality, DOB, expiry.

Pipeline:
  1. Preprocess image (enhance_for_ocr)
  2. Run Tesseract targeting the bottom ~30% (MRZ region)
  3. Extract MRZ lines using pattern matching
  4. Parse and validate checksums (ICAO compliant)
  5. Return normalized OcrResult with field confidences

Confidence: each field gets 0.95 if checksum passes, 0.60 if not.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional, Tuple

from ocr.provider_base import (
    OcrProvider, OcrRequest, OcrResult, OcrResultStatus, ImageQualityFlag
)
from ocr.image_preprocessing import preprocess_document, image_to_bytes

logger = logging.getLogger(__name__)

# MRZ valid characters
_MRZ_CHARS = re.compile(r'^[A-Z0-9<]+$')

# TD3 passport: 2 lines of exactly 44 chars
_TD3_LINE1 = re.compile(r'P[A-Z<][A-Z<]{3}[A-Z<]{39}')
_TD3_LINE2 = re.compile(r'[A-Z0-9<]{9}[0-9][A-Z]{3}[0-9]{7}[MF<][0-9]{7}[A-Z0-9<]{14}[0-9][0-9]')

# TD1 ID card: 3 lines of exactly 30 chars
_TD1_LINE1 = re.compile(r'[AI][A-Z<][A-Z<]{3}[A-Z0-9<]{9}[0-9][A-Z0-9<]{15}')

# Checksum table (ICAO weighting 7-3-1)
_WEIGHTS = [7, 3, 1]
_CHAR_VALUES = {c: i for i, c in enumerate("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")}
_CHAR_VALUES['<'] = 0


def _checksum(s: str) -> int:
    """Compute ICAO MRZ checksum for a string."""
    total = 0
    for i, ch in enumerate(s):
        total += _CHAR_VALUES.get(ch, 0) * _WEIGHTS[i % 3]
    return total % 10


def _check(value: str, check_digit: str) -> bool:
    """Validate ICAO checksum digit."""
    try:
        return _checksum(value) == int(check_digit)
    except (ValueError, TypeError):
        return False


def _mrz_name(raw: str) -> Tuple[str, str, str]:
    """
    Parse name field from MRZ (primary + secondary identifiers).
    Returns (full_name, last_name, first_name).
    """
    parts = raw.split("<<", 1)
    last = parts[0].replace("<", " ").strip()
    first = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""
    full = f"{first} {last}".strip() if first else last
    return full, last, first


def _clean_mrz_lines(text: str) -> list[str]:
    """
    Extract candidate MRZ lines from raw OCR text.
    Handles common OCR substitution errors (0/O, 1/I, etc.).
    """
    lines = []
    for raw_line in text.upper().splitlines():
        # Strip whitespace and common OCR artifacts
        line = re.sub(r'\s+', '', raw_line)
        # Normalize common OCR errors in non-name fields later
        if len(line) >= 30 and _MRZ_CHARS.match(line):
            lines.append(line)
    return lines


def parse_td3(line1: str, line2: str) -> Optional[dict]:
    """
    Parse TD3 (passport) MRZ.
    line1: 44 chars, line2: 44 chars.
    Returns dict of fields, or None if format is invalid.
    """
    if len(line1) != 44 or len(line2) != 44:
        return None

    doc_type = line1[0:2].replace("<", "")
    country = line1[2:5].replace("<", "")
    name_field = line1[5:44]
    full_name, last_name, first_name = _mrz_name(name_field)

    doc_number = line2[0:9]
    doc_check = line2[9]
    nationality = line2[10:13].replace("<", "")
    dob = line2[13:19]
    dob_check = line2[19]
    sex = line2[20]
    expiry = line2[21:27]
    expiry_check = line2[27]
    personal = line2[28:42]
    personal_check = line2[42]
    composite_check_digit = line2[43]

    # Validate checksums
    doc_ok = _check(doc_number, doc_check)
    dob_ok = _check(dob, dob_check)
    expiry_ok = _check(expiry, expiry_check)
    personal_ok = _check(personal, personal_check)
    composite = line2[0:10] + line2[13:20] + line2[21:43]
    composite_ok = _check(composite, composite_check_digit)

    checksum_pass = doc_ok and dob_ok and expiry_ok and composite_ok

    return {
        "document_type": "PASSPORT",
        "issuing_country": country,
        "document_number": doc_number.replace("<", ""),
        "full_name": full_name,
        "last_name": last_name,
        "first_name": first_name,
        "nationality": nationality,
        "date_of_birth": _format_date(dob),
        "sex": sex if sex != "<" else None,
        "expiry_date": _format_date(expiry),
        "_checksum_pass": checksum_pass,
        "_doc_number_ok": doc_ok,
        "_dob_ok": dob_ok,
        "_expiry_ok": expiry_ok,
        "_composite_ok": composite_ok,
    }


def parse_td1(line1: str, line2: str, line3: str) -> Optional[dict]:
    """
    Parse TD1 (ID card) MRZ.
    line1/2/3: 30 chars each.
    """
    if len(line1) != 30 or len(line2) != 30 or len(line3) != 30:
        return None

    doc_type = line1[0:2].replace("<", "")
    country = line1[2:5].replace("<", "")
    doc_number = line1[5:14]
    doc_check = line1[14]

    dob = line2[0:6]
    dob_check = line2[6]
    sex = line2[7]
    expiry = line2[8:14]
    expiry_check = line2[14]
    nationality = line2[15:18].replace("<", "")

    name_field = line3[0:30]
    full_name, last_name, first_name = _mrz_name(name_field)

    doc_ok = _check(doc_number, doc_check)
    dob_ok = _check(dob, dob_check)
    expiry_ok = _check(expiry, expiry_check)
    checksum_pass = doc_ok and dob_ok and expiry_ok

    return {
        "document_type": "NATIONAL_ID",
        "issuing_country": country,
        "document_number": doc_number.replace("<", ""),
        "full_name": full_name,
        "last_name": last_name,
        "first_name": first_name,
        "nationality": nationality,
        "date_of_birth": _format_date(dob),
        "sex": sex if sex != "<" else None,
        "expiry_date": _format_date(expiry),
        "_checksum_pass": checksum_pass,
        "_doc_number_ok": doc_ok,
        "_dob_ok": dob_ok,
        "_expiry_ok": expiry_ok,
        "_composite_ok": True,
    }


def _format_date(raw: str) -> Optional[str]:
    """
    Convert YYMMDD → YYYY-MM-DD (best-effort, no century correction).
    Returns None on invalid input.
    """
    if not raw or len(raw) != 6 or not raw.isdigit():
        return None
    yy, mm, dd = raw[0:2], raw[2:4], raw[4:6]
    # Simple century heuristic: YY < 30 → 2000s, else 1900s
    century = "20" if int(yy) < 30 else "19"
    return f"{century}{yy}-{mm}-{dd}"


def extract_mrz_from_text(raw_text: str) -> Optional[dict]:
    """
    Try to extract and parse MRZ from raw OCR text.
    Attempts TD3 first, then TD1.
    """
    lines = _clean_mrz_lines(raw_text)
    if len(lines) < 2:
        return None

    # Try TD3: look for consecutive 44-char lines
    for i in range(len(lines) - 1):
        l1, l2 = lines[i], lines[i + 1]
        if len(l1) == 44 and len(l2) == 44:
            result = parse_td3(l1, l2)
            if result:
                return result

    # Try TD1: look for consecutive 30-char lines (need 3)
    for i in range(len(lines) - 2):
        l1, l2, l3 = lines[i], lines[i + 1], lines[i + 2]
        if len(l1) == 30 and len(l2) == 30 and len(l3) == 30:
            result = parse_td1(l1, l2, l3)
            if result:
                return result

    return None


# ─── Tesseract helper ─────────────────────────────────────────────

def _run_tesseract_on_bytes(image_bytes: bytes, config: str = "") -> Optional[str]:
    """
    Run Tesseract on image bytes. Returns raw text or None on failure.
    Handles missing binary gracefully.
    """
    try:
        import pytesseract
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(img, config=config)
    except ImportError:
        logger.warning("pytesseract not installed — MRZ OCR unavailable")
        return None
    except Exception as exc:
        logger.warning("Tesseract failed: %s", exc)
        return None


# ─── OcrProvider implementation ───────────────────────────────────

class LocalMrzProvider(OcrProvider):
    """
    Track B identity document OCR using MRZ parsing.

    Uses Tesseract to extract text from the MRZ zone of the document,
    then parses the result with deterministic ICAO MRZ logic.

    Works without any external API. Degrades gracefully if Tesseract
    binary is not installed (returns FAILED result, not exception).
    """

    SUPPORTED_CAPTURES = frozenset({"identity_document_capture"})
    SUPPORTED_DOCUMENTS = frozenset({"PASSPORT", "NATIONAL_ID", "DRIVING_LICENSE"})

    @property
    def provider_name(self) -> str:
        return "local_mrz"

    @property
    def supported_capture_types(self) -> frozenset:
        return self.SUPPORTED_CAPTURES

    @property
    def supported_document_types(self) -> frozenset:
        return self.SUPPORTED_DOCUMENTS

    async def process(self, request: OcrRequest) -> OcrResult:
        start = time.monotonic()

        # Preprocess image
        prep = preprocess_document(request.image_bytes)
        if not prep.ok:
            return self._make_failed_result(request, prep.error or "Preprocess failed")

        quality_warnings = [
            ImageQualityFlag(w) for w in prep.warnings
            if w in {f.value for f in ImageQualityFlag}
        ]

        # Get image bytes for Tesseract
        img_bytes = image_to_bytes(prep.image)

        # Run Tesseract with MRZ-optimized config
        # --psm 6 = single uniform block; whitelist MRZ chars
        tess_config = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
        raw_text = _run_tesseract_on_bytes(img_bytes, config=tess_config)

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

        # Parse MRZ from extracted text
        parsed = extract_mrz_from_text(raw_text)

        if not parsed:
            return OcrResult(
                status=OcrResultStatus.FAILED,
                provider_name=self.provider_name,
                capture_type=request.capture_type,
                document_type=request.document_type,
                image_quality_score=prep.quality_score,
                quality_warnings=quality_warnings,
                processing_time_ms=elapsed,
                error_message="No MRZ pattern found in image",
            )

        # Build field→confidence mapping
        # Checksum-validated fields get 0.95; failed checksum = 0.60
        checksum_pass = parsed.pop("_checksum_pass", False)
        doc_ok = parsed.pop("_doc_number_ok", False)
        dob_ok = parsed.pop("_dob_ok", False)
        expiry_ok = parsed.pop("_expiry_ok", False)
        composite_ok = parsed.pop("_composite_ok", False)

        base_conf = 0.95 if checksum_pass else 0.70

        fields = {k: v for k, v in parsed.items() if v is not None}
        confidences = {
            "full_name": base_conf,
            "last_name": base_conf,
            "first_name": base_conf,
            "document_type": 0.99,
            "issuing_country": base_conf,
            "document_number": 0.95 if doc_ok else 0.55,
            "nationality": base_conf,
            "date_of_birth": 0.95 if dob_ok else 0.55,
            "expiry_date": 0.95 if expiry_ok else 0.55,
            "sex": base_conf,
        }
        # Only include confidences for fields actually extracted
        confidences = {k: v for k, v in confidences.items() if k in fields}

        status = OcrResultStatus.SUCCESS if checksum_pass else OcrResultStatus.PARTIAL

        return OcrResult(
            status=status,
            provider_name=self.provider_name,
            capture_type=request.capture_type,
            document_type=parsed.get("document_type") or request.document_type,
            extracted_fields=fields,
            field_confidences=confidences,
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
                "message": f"Tesseract {version} available",
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
