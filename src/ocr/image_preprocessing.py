"""
Phase 983 — Image Pre-processing Utilities
============================================

Shared image preparation used by all Track B local providers.

Pipeline:
  - Decode base64 or raw bytes → PIL Image
  - Normalize orientation (EXIF correction)
  - Crop targeting (document region / meter digit region)
  - Contrast + brightness enhancement
  - Noise reduction / sharpening
  - Output: preprocessed PIL Image + quality metadata

These utilities are provider-agnostic — each provider calls what it needs.
"""
from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ─── PIL import (required: Pillow already in requirements) ─────────
try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    _PILLOW_AVAILABLE = True
except ImportError:
    _PILLOW_AVAILABLE = False
    logger.warning("Pillow not available — image preprocessing disabled")


@dataclass
class PreprocessResult:
    """Result of image preprocessing."""
    image: object              # PIL.Image.Image or None
    width: int = 0
    height: int = 0
    quality_score: float = 1.0  # 0.0–1.0 estimated quality
    warnings: list = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.image is not None and self.error is None


def decode_image(image_input: bytes | str) -> Optional[object]:
    """
    Decode image bytes or base64-encoded string to PIL Image.

    Returns None on failure.
    """
    if not _PILLOW_AVAILABLE:
        return None

    try:
        if isinstance(image_input, str):
            # May or may not have data URI prefix
            if "," in image_input:
                image_input = image_input.split(",", 1)[1]
            raw = base64.b64decode(image_input)
        else:
            raw = image_input

        img = Image.open(io.BytesIO(raw))
        img.load()  # force decode now to catch corrupt files
        return img
    except Exception as exc:
        logger.warning("Failed to decode image: %s", exc)
        return None


def fix_orientation(img: object) -> object:
    """Correct EXIF orientation (common on mobile photos)."""
    if not _PILLOW_AVAILABLE:
        return img
    try:
        return ImageOps.exif_transpose(img)
    except Exception:
        return img


def to_rgb(img: object) -> object:
    """Convert to RGB (handle RGBA, grayscale, palette modes)."""
    if not _PILLOW_AVAILABLE:
        return img
    try:
        if img.mode != "RGB":
            return img.convert("RGB")
        return img
    except Exception:
        return img


def enhance_for_ocr(img: object, *, sharpness: float = 2.0, contrast: float = 1.5) -> object:
    """
    Sharpen and increase contrast for better OCR accuracy.
    Default values tuned for document text recognition.
    """
    if not _PILLOW_AVAILABLE:
        return img
    try:
        img = ImageEnhance.Sharpness(img).enhance(sharpness)
        img = ImageEnhance.Contrast(img).enhance(contrast)
        return img
    except Exception:
        return img


def enhance_for_meter(img: object) -> object:
    """
    Aggressive preprocessing for meter digit recognition.
    Higher contrast helps with digit segmentation.
    """
    if not _PILLOW_AVAILABLE:
        return img
    try:
        img = img.convert("L")                          # grayscale
        img = ImageEnhance.Contrast(img).enhance(2.5)   # high contrast
        img = ImageEnhance.Sharpness(img).enhance(3.0)  # aggressive sharpen
        img = img.filter(ImageFilter.MedianFilter(size=3))  # denoise
        return img
    except Exception:
        return img


def resize_for_ocr(img: object, max_side: int = 2000) -> object:
    """
    Downscale if very large (preserves aspect ratio).
    Tessersact works best at ~300 DPI — overly large images slow it down.
    """
    if not _PILLOW_AVAILABLE:
        return img
    try:
        w, h = img.size
        if max(w, h) > max_side:
            scale = max_side / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        return img
    except Exception:
        return img


def estimate_quality(img: object) -> Tuple[float, list]:
    """
    Fast quality estimation using variance (blur proxy) and brightness.

    Returns:
        (score 0.0-1.0, list of warning flags)
    """
    if not _PILLOW_AVAILABLE:
        return 0.5, []

    warnings = []
    score = 1.0

    try:
        gray = img.convert("L")
        try:
            pixels = list(gray.get_flattened_data())  # Pillow 14+ compatible
        except AttributeError:
            pixels = list(gray.getdata())  # Pillow < 14 fallback
        n = len(pixels)
        if n == 0:
            return 0.0, ["empty_image"]

        mean = sum(pixels) / n
        variance = sum((p - mean) ** 2 for p in pixels) / n

        # Blur: low variance = blurry
        if variance < 100:
            warnings.append("blur")
            score -= 0.4
        elif variance < 300:
            warnings.append("possible_blur")
            score -= 0.15

        # Brightness: too dark or too bright
        if mean < 40:
            warnings.append("dark")
            score -= 0.3
        elif mean > 220:
            warnings.append("glare")
            score -= 0.25

        score = max(0.0, min(1.0, score))

    except Exception as exc:
        logger.debug("Quality estimation failed: %s", exc)
        return 0.5, []

    return round(score, 3), warnings


def preprocess_document(image_input: bytes | str) -> PreprocessResult:
    """
    Full preprocessing pipeline for identity document images.

    Steps: decode → orient → rgb → resize → enhance → quality check
    """
    img = decode_image(image_input)
    if img is None:
        return PreprocessResult(image=None, error="Failed to decode image")

    img = fix_orientation(img)
    img = to_rgb(img)
    img = resize_for_ocr(img, max_side=2000)
    quality_score, warnings = estimate_quality(img)
    img = enhance_for_ocr(img, sharpness=2.0, contrast=1.5)

    w, h = img.size
    return PreprocessResult(
        image=img,
        width=w,
        height=h,
        quality_score=quality_score,
        warnings=warnings,
    )


def preprocess_meter(image_input: bytes | str) -> PreprocessResult:
    """
    Full preprocessing pipeline for electricity meter images.

    More aggressive than document pipeline — targets digit clarity.
    """
    img = decode_image(image_input)
    if img is None:
        return PreprocessResult(image=None, error="Failed to decode image")

    img = fix_orientation(img)
    img = to_rgb(img)
    img = resize_for_ocr(img, max_side=1600)
    quality_score, warnings = estimate_quality(img)
    img = enhance_for_meter(img)

    w, h = img.size
    return PreprocessResult(
        image=img,
        width=w,
        height=h,
        quality_score=quality_score,
        warnings=warnings,
    )


def image_to_bytes(img: object, fmt: str = "PNG") -> bytes:
    """Convert PIL Image back to bytes for passing to OCR engine."""
    if not _PILLOW_AVAILABLE or img is None:
        return b""
    try:
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        return buf.getvalue()
    except Exception:
        return b""
