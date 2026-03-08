"""
Phase 74 — OTA Date/Timezone Normalization

Provides a single `normalize_date(raw)` function that accepts any date string
format used by OTA providers and returns a canonical ISO date string "YYYY-MM-DD",
or None if the input is None/empty/unparseable.

Supported input formats:
  "2026-09-01"                  ← ISO date (Booking.com, Expedia plain)
  "2026-09-01T00:00:00Z"        ← ISO datetime UTC (Airbnb)
  "2026-09-01T00:00:00"         ← ISO datetime no tz (some providers)
  "2026-09-01T00:00:00+07:00"   ← ISO datetime with tz offset (Agoda)
  "20260901"                    ← compact YYYYMMDD (Trip.com alternative)
  "01/09/2026"                  ← DD/MM/YYYY (some regional providers)
  "09/01/2026"                  ← MM/DD/YYYY (US-style, very rare OTAs)

Strategy:
  1. Strip whitespace and Z suffix
  2. Try %Y-%m-%d (most common — fast path)
  3. Try ISO 8601 datetime using fromisoformat (handles offsets on Python 3.11+)
  4. Try compact YYYYMMDD
  5. Try DD/MM/YYYY and MM/DD/YYYY (best-effort — ambiguous, logged as warning)
  6. Return None and log warning if nothing matches

Output is always "YYYY-MM-DD" — no time component, no timezone.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Primary normalizer
# ---------------------------------------------------------------------------

def normalize_date(raw: Optional[str]) -> Optional[str]:
    """
    Normalize a raw OTA date string to canonical ISO date format "YYYY-MM-DD".

    Returns None if input is None, empty, or unparseable.
    Never raises — silently returns None and logs a warning on failure.

    Args:
        raw: raw date string from any OTA provider

    Returns:
        "YYYY-MM-DD" string, or None
    """
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None

    # --- Fast path: already "YYYY-MM-DD" ---
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        try:
            date.fromisoformat(s)   # validate it's a real date
            return s
        except ValueError:
            pass

    # --- Strip trailing Z (UTC shorthand) ---
    s_noz = s.rstrip("Z").strip()

    # --- ISO 8601 datetime (handles +HH:MM offsets, T separator) ---
    # Strategy: parse to datetime, extract date part only
    iso_candidates = [s, s_noz]
    for candidate in iso_candidates:
        parsed = _try_fromisoformat(candidate)
        if parsed is not None:
            return parsed.strftime("%Y-%m-%d")

    # --- Compact YYYYMMDD ---
    if re.fullmatch(r"\d{8}", s):
        try:
            parsed = datetime.strptime(s, "%Y%m%d")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # --- Slash-delimited: DD/MM/YYYY (primary) vs MM/DD/YYYY (fallback) ---
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", s):
        parts = s.split("/")
        # Try DD/MM/YYYY first
        dd_mm = _try_strptime(s, "%d/%m/%Y")
        if dd_mm:
            logger.warning(
                "normalize_date: ambiguous slash date '%s' — interpreted as DD/MM/YYYY → %s",
                raw, dd_mm.strftime("%Y-%m-%d"),
            )
            return dd_mm.strftime("%Y-%m-%d")
        # Try MM/DD/YYYY
        mm_dd = _try_strptime(s, "%m/%d/%Y")
        if mm_dd:
            logger.warning(
                "normalize_date: ambiguous slash date '%s' — interpreted as MM/DD/YYYY → %s",
                raw, mm_dd.strftime("%Y-%m-%d"),
            )
            return mm_dd.strftime("%Y-%m-%d")

    logger.warning("normalize_date: could not parse '%s' — returning None", raw)
    return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _try_fromisoformat(s: str) -> Optional[datetime]:
    """Try datetime.fromisoformat. Returns None on failure."""
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _try_strptime(s: str, fmt: str) -> Optional[datetime]:
    """Try datetime.strptime with a given format. Returns None on failure."""
    try:
        return datetime.strptime(s, fmt)
    except (ValueError, TypeError):
        return None
