"""
structured_logger.py -- Phase 80

A thin, zero-dependency wrapper around stdlib logging that emits consistent
JSON log entries and returns them as strings for easy introspection / testing.

Log entry format:
    {
        "ts":       "<UTC ISO 8601>",
        "level":    "INFO",
        "event":    "webhook_received",
        "trace_id": "req-abc-123",   # omitted if empty
        ...                          # any caller-supplied kwargs
    }

Public API:
    StructuredLogger          -- class (construct with name + optional trace_id)
    get_structured_logger()   -- factory function (drop-in for logging.getLogger)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_utc_iso() -> str:
    """Return current UTC timestamp as ISO 8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _build_entry(
    level: str,
    event: str,
    trace_id: str,
    kwargs: dict,
) -> dict:
    """Build the structured log dict. Never raises."""
    entry: dict[str, Any] = {
        "ts": _now_utc_iso(),
        "level": level,
        "event": event,
    }
    if trace_id:
        entry["trace_id"] = trace_id
    entry.update(kwargs)
    return entry


def _serialize(entry: dict) -> str:
    """Serialize entry to JSON string. Falls back safely on non-serializable values."""
    try:
        return json.dumps(entry, default=str)
    except Exception:  # noqa: BLE001
        return json.dumps({"ts": entry.get("ts", ""), "level": entry.get("level", ""), "event": entry.get("event", ""), "error": "serialization_failed"})


# ---------------------------------------------------------------------------
# StructuredLogger
# ---------------------------------------------------------------------------

class StructuredLogger:
    """
    Emits structured JSON log entries via stdlib logging.

    Each method:
      1. Builds the entry dict
      2. Serializes to JSON
      3. Emits via self._logger at the matching level
      4. Returns the JSON string

    Args:
        name:     Logger name passed to logging.getLogger (e.g. __name__)
        trace_id: Optional request/trace ID included in every entry.
    """

    def __init__(self, name: str, trace_id: str = "") -> None:
        self._logger = logging.getLogger(name)
        self._trace_id = trace_id

    # ------------------------------------------------------------------
    # Public logging methods
    # ------------------------------------------------------------------

    def debug(self, event: str, **kwargs: Any) -> str:
        """Emit a DEBUG entry. Returns the JSON string."""
        return self._emit(logging.DEBUG, "DEBUG", event, kwargs)

    def info(self, event: str, **kwargs: Any) -> str:
        """Emit an INFO entry. Returns the JSON string."""
        return self._emit(logging.INFO, "INFO", event, kwargs)

    def warning(self, event: str, **kwargs: Any) -> str:
        """Emit a WARNING entry. Returns the JSON string."""
        return self._emit(logging.WARNING, "WARNING", event, kwargs)

    def error(self, event: str, **kwargs: Any) -> str:
        """Emit an ERROR entry. Returns the JSON string."""
        return self._emit(logging.ERROR, "ERROR", event, kwargs)

    def critical(self, event: str, **kwargs: Any) -> str:
        """Emit a CRITICAL entry. Returns the JSON string."""
        return self._emit(logging.CRITICAL, "CRITICAL", event, kwargs)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit(self, log_level: int, level_str: str, event: str, kwargs: dict) -> str:
        entry = _build_entry(level_str, event, self._trace_id, kwargs)
        line = _serialize(entry)
        self._logger.log(log_level, line)
        return line


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_structured_logger(name: str, trace_id: str = "") -> StructuredLogger:
    """
    Return a StructuredLogger for the given name.

    Drop-in replacement for logging.getLogger() that returns a
    StructuredLogger instead of a stdlib Logger.

    Args:
        name:     Module name (typically __name__)
        trace_id: Optional request/trace ID to include in every entry.

    Returns:
        StructuredLogger
    """
    return StructuredLogger(name=name, trace_id=trace_id)
