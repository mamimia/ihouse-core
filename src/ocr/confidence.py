"""
Phase 982 — OCR Confidence Model
==================================

Field-level confidence scoring for OCR results.

Design decisions:
  - Each extracted field gets its own confidence score (0.0–1.0)
  - Overall confidence = weighted average of field confidences
  - Confidence thresholds determine review requirements:
      HIGH   (≥ 0.90): auto-fill, minor review
      MEDIUM (≥ 0.70): auto-fill, mandatory review
      LOW    (< 0.70): auto-fill with highlight, mandatory correction prompt
  - Workers ALWAYS review OCR results (INV-OCR-02), but the UX
    emphasis changes based on confidence level.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ConfidenceLevel(str, Enum):
    HIGH = "high"       # ≥ 0.90
    MEDIUM = "medium"   # ≥ 0.70
    LOW = "low"         # < 0.70
    NONE = "none"       # field not extracted


# Thresholds
HIGH_THRESHOLD = 0.90
MEDIUM_THRESHOLD = 0.70


def classify_confidence(score: float) -> ConfidenceLevel:
    """Classify a confidence score into HIGH/MEDIUM/LOW."""
    if score >= HIGH_THRESHOLD:
        return ConfidenceLevel.HIGH
    elif score >= MEDIUM_THRESHOLD:
        return ConfidenceLevel.MEDIUM
    else:
        return ConfidenceLevel.LOW


@dataclass
class FieldConfidence:
    """Confidence data for a single extracted field."""
    field_name: str
    value: Optional[str]
    confidence: float           # 0.0–1.0
    level: ConfidenceLevel = field(init=False)
    source: str = "ocr"         # 'ocr', 'mrz', 'manual', 'corrected'

    def __post_init__(self) -> None:
        self.level = classify_confidence(self.confidence)

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "value": self.value,
            "confidence": round(self.confidence, 4),
            "level": self.level.value,
            "source": self.source,
        }


@dataclass
class OcrConfidenceReport:
    """
    Aggregated confidence report for an OCR result.
    Contains per-field confidences and an overall score.
    """
    fields: Dict[str, FieldConfidence]
    provider_name: str
    capture_type: str

    @property
    def overall_confidence(self) -> float:
        """Weighted average of all field confidences."""
        if not self.fields:
            return 0.0
        scored = [f for f in self.fields.values() if f.confidence > 0]
        if not scored:
            return 0.0
        # Identity fields have higher weight than ancillary fields
        weights = _get_field_weights(self.capture_type)
        total_weight = 0.0
        weighted_sum = 0.0
        for fc in scored:
            w = weights.get(fc.field_name, 1.0)
            weighted_sum += fc.confidence * w
            total_weight += w
        return round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0

    @property
    def overall_level(self) -> ConfidenceLevel:
        return classify_confidence(self.overall_confidence)

    @property
    def low_confidence_fields(self) -> List[str]:
        """Fields that need mandatory review/correction."""
        return [
            name for name, fc in self.fields.items()
            if fc.level == ConfidenceLevel.LOW and fc.value is not None
        ]

    @property
    def requires_review(self) -> bool:
        """True if any field has LOW confidence or overall is below HIGH."""
        # INV-OCR-02: workers always review, but this flag drives UX emphasis
        return (
            self.overall_level != ConfidenceLevel.HIGH
            or len(self.low_confidence_fields) > 0
        )

    def to_dict(self) -> dict:
        return {
            "overall_confidence": self.overall_confidence,
            "overall_level": self.overall_level.value,
            "requires_review": self.requires_review,
            "low_confidence_fields": self.low_confidence_fields,
            "fields": {
                name: fc.to_dict() for name, fc in self.fields.items()
            },
            "provider": self.provider_name,
            "capture_type": self.capture_type,
        }


# ─── Field weight maps ─────────────────────────────────────────────

_IDENTITY_FIELD_WEIGHTS: Dict[str, float] = {
    "full_name": 3.0,
    "document_number": 3.0,
    "nationality": 1.5,
    "date_of_birth": 2.0,
    "expiry_date": 1.5,
    "issuing_country": 1.0,
    "document_type": 1.0,
    "first_name": 2.0,
    "last_name": 2.0,
}

_METER_FIELD_WEIGHTS: Dict[str, float] = {
    "meter_value": 5.0,   # the only field that really matters
}


def _get_field_weights(capture_type: str) -> Dict[str, float]:
    """Return field weights for the given capture type."""
    ct = (capture_type or "").strip().lower()
    if ct == "identity_document_capture":
        return _IDENTITY_FIELD_WEIGHTS
    elif ct in {"checkin_opening_meter_capture", "checkout_closing_meter_capture"}:
        return _METER_FIELD_WEIGHTS
    return {}


# ─── Builder helpers ────────────────────────────────────────────────

def build_confidence_report(
    fields: Dict[str, tuple],  # {field_name: (value, confidence, source)}
    provider_name: str,
    capture_type: str,
) -> OcrConfidenceReport:
    """
    Build a confidence report from raw extraction data.

    Args:
        fields: Dict of {field_name: (value, confidence_score, source_label)}
        provider_name: Name of the provider that produced the result
        capture_type: The capture type this result is for

    Returns:
        OcrConfidenceReport with per-field and overall scoring.
    """
    fc_map: Dict[str, FieldConfidence] = {}
    for name, data in fields.items():
        if len(data) == 3:
            value, confidence, source = data
        elif len(data) == 2:
            value, confidence = data
            source = "ocr"
        else:
            continue
        fc_map[name] = FieldConfidence(
            field_name=name,
            value=value,
            confidence=max(0.0, min(1.0, float(confidence))),
            source=source,
        )
    return OcrConfidenceReport(
        fields=fc_map,
        provider_name=provider_name,
        capture_type=capture_type,
    )
