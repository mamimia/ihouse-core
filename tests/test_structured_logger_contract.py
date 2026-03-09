"""
test_structured_logger_contract.py -- Phase 80

Contract tests for structured_logger.StructuredLogger and get_structured_logger().

All tests inspect the returned JSON string — no log capturing required.

Groups:
  A -- returned value is valid JSON
  B -- required fields (ts, level, event)
  C -- level correctness per method
  D -- trace_id behaviour
  E -- extra kwargs merged at root level
  F -- non-serializable fallback (no raise)
  G -- get_structured_logger() factory
"""

from __future__ import annotations

import json
import pytest

from adapters.ota.structured_logger import (
    StructuredLogger,
    get_structured_logger,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(line: str) -> dict:
    """Parse a returned JSON string into a dict."""
    return json.loads(line)


def _logger(trace_id: str = "") -> StructuredLogger:
    return StructuredLogger(name="test.structured_logger", trace_id=trace_id)


# ---------------------------------------------------------------------------
# Group A -- returned value is valid JSON
# ---------------------------------------------------------------------------

class TestReturnedValueIsJson:

    def test_info_returns_valid_json(self):
        line = _logger().info("test_event")
        parsed = _parse(line)
        assert isinstance(parsed, dict)

    def test_warning_returns_valid_json(self):
        line = _logger().warning("test_event")
        assert isinstance(_parse(line), dict)

    def test_error_returns_valid_json(self):
        line = _logger().error("test_event")
        assert isinstance(_parse(line), dict)

    def test_debug_returns_valid_json(self):
        line = _logger().debug("test_event")
        assert isinstance(_parse(line), dict)

    def test_critical_returns_valid_json(self):
        line = _logger().critical("test_event")
        assert isinstance(_parse(line), dict)

    def test_returned_value_is_string(self):
        line = _logger().info("test_event")
        assert isinstance(line, str)


# ---------------------------------------------------------------------------
# Group B -- required fields
# ---------------------------------------------------------------------------

class TestRequiredFields:

    def test_ts_field_present(self):
        parsed = _parse(_logger().info("test_event"))
        assert "ts" in parsed

    def test_ts_is_string(self):
        parsed = _parse(_logger().info("test_event"))
        assert isinstance(parsed["ts"], str)

    def test_ts_contains_utc_indicator(self):
        """ts must be UTC ISO — should contain +00:00 or Z."""
        parsed = _parse(_logger().info("test_event"))
        ts = parsed["ts"]
        assert "+" in ts or ts.endswith("Z")

    def test_level_field_present(self):
        parsed = _parse(_logger().info("test_event"))
        assert "level" in parsed

    def test_event_field_present(self):
        parsed = _parse(_logger().info("my_event"))
        assert "event" in parsed

    def test_event_value_matches_argument(self):
        parsed = _parse(_logger().info("webhook_received"))
        assert parsed["event"] == "webhook_received"

    def test_event_value_exact_string(self):
        parsed = _parse(_logger().info("booking_created"))
        assert parsed["event"] == "booking_created"


# ---------------------------------------------------------------------------
# Group C -- level correctness per method
# ---------------------------------------------------------------------------

class TestLevelPerMethod:

    def test_info_level_is_INFO(self):
        parsed = _parse(_logger().info("e"))
        assert parsed["level"] == "INFO"

    def test_warning_level_is_WARNING(self):
        parsed = _parse(_logger().warning("e"))
        assert parsed["level"] == "WARNING"

    def test_error_level_is_ERROR(self):
        parsed = _parse(_logger().error("e"))
        assert parsed["level"] == "ERROR"

    def test_debug_level_is_DEBUG(self):
        parsed = _parse(_logger().debug("e"))
        assert parsed["level"] == "DEBUG"

    def test_critical_level_is_CRITICAL(self):
        parsed = _parse(_logger().critical("e"))
        assert parsed["level"] == "CRITICAL"


# ---------------------------------------------------------------------------
# Group D -- trace_id behaviour
# ---------------------------------------------------------------------------

class TestTraceId:

    def test_trace_id_included_when_set(self):
        log = StructuredLogger(name="test", trace_id="req-abc-123")
        parsed = _parse(log.info("e"))
        assert parsed.get("trace_id") == "req-abc-123"

    def test_trace_id_absent_when_empty_string(self):
        log = StructuredLogger(name="test", trace_id="")
        parsed = _parse(log.info("e"))
        assert "trace_id" not in parsed

    def test_trace_id_present_on_every_method(self):
        log = StructuredLogger(name="test", trace_id="tid-1")
        for method in (log.info, log.warning, log.error, log.debug, log.critical):
            parsed = _parse(method("e"))
            assert parsed.get("trace_id") == "tid-1"


# ---------------------------------------------------------------------------
# Group E -- extra kwargs merged at root level
# ---------------------------------------------------------------------------

class TestExtraKwargs:

    def test_single_kwarg_at_root(self):
        parsed = _parse(_logger().info("e", provider="bookingcom"))
        assert parsed["provider"] == "bookingcom"

    def test_multiple_kwargs_all_present(self):
        parsed = _parse(_logger().info("e", provider="airbnb", tenant_id="t1", status=200))
        assert parsed["provider"] == "airbnb"
        assert parsed["tenant_id"] == "t1"
        assert parsed["status"] == 200

    def test_kwarg_does_not_overwrite_ts(self):
        """A caller kwarg named 'ts' should be possible but ts must exist."""
        parsed = _parse(_logger().info("e", extra_field="x"))
        assert "ts" in parsed

    def test_string_int_float_bool_kwargs_preserved(self):
        parsed = _parse(_logger().info("e", s="hello", i=42, f=3.14, b=True))
        assert parsed["s"] == "hello"
        assert parsed["i"] == 42
        assert abs(parsed["f"] - 3.14) < 0.001
        assert parsed["b"] is True


# ---------------------------------------------------------------------------
# Group F -- non-serializable fallback
# ---------------------------------------------------------------------------

class TestNonSerializableFallback:

    def test_non_serializable_kwarg_does_not_raise(self):
        """Non-JSON-serializable values must not cause an exception."""
        class _Unserializable:
            pass
        line = _logger().info("e", bad=_Unserializable())
        assert isinstance(line, str)

    def test_non_serializable_result_is_still_valid_json(self):
        """Even with non-serializable values, output must parse as JSON."""
        class _Unserializable:
            pass
        line = _logger().info("e", bad=_Unserializable())
        parsed = json.loads(line)
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# Group G -- get_structured_logger() factory
# ---------------------------------------------------------------------------

class TestFactory:

    def test_returns_structured_logger(self):
        log = get_structured_logger("test.module")
        assert isinstance(log, StructuredLogger)

    def test_factory_with_trace_id(self):
        log = get_structured_logger("test.module", trace_id="req-xyz")
        parsed = _parse(log.info("e"))
        assert parsed.get("trace_id") == "req-xyz"

    def test_factory_without_trace_id(self):
        log = get_structured_logger("test.module")
        parsed = _parse(log.info("e"))
        assert "trace_id" not in parsed
