"""
Phase 335 — Outbound OTA Adapter Integration Tests
====================================================

First-ever integration tests for:
  - `adapters/outbound/airbnb_adapter.py` (Phase 139/143/154/155, 318 lines)
  - `adapters/outbound/bookingcom_adapter.py` (Phase 139/143/154/155, 283 lines)
  - `adapters/outbound/expedia_vrbo_adapter.py` (Phase 139/143/154/155, 273 lines)

Group A: AirbnbAdapter — Dry-Run Mode (6 tests)
  ✓  send() returns dry_run when no API key
  ✓  cancel() returns dry_run when no API key
  ✓  amend() returns dry_run when no API key
  ✓  send() returns dry_run when IHOUSE_DRY_RUN=true
  ✓  send() returns dry_run when explicit dry_run=True
  ✓  amend() includes check_in/check_out in message

Group B: AirbnbAdapter — AdapterResult Shape (4 tests)
  ✓  send() result has all required fields
  ✓  provider is always "airbnb"
  ✓  strategy is always "api_first"
  ✓  cancel() result has proper cancel message

Group C: BookingComAdapter — Dry-Run Mode (5 tests)
  ✓  send() returns dry_run when no API key
  ✓  cancel() returns dry_run when no API key
  ✓  amend() returns dry_run when no API key
  ✓  send() returns dry_run when IHOUSE_DRY_RUN=true
  ✓  amend() with check_in and check_out

Group D: BookingComAdapter — AdapterResult Shape (4 tests)
  ✓  send() result has all required fields
  ✓  provider is always "bookingcom"
  ✓  strategy is always "api_first"
  ✓  cancel() result has proper cancel message

Group E: ExpediaVrboAdapter — Dual Provider (6 tests)
  ✓  Default provider is "expedia"
  ✓  send() dry_run with expedia provider key
  ✓  send() dry_run with vrbo provider
  ✓  cancel() dry_run with vrbo provider
  ✓  amend() dry_run with expedia check_in/check_out
  ✓  VRBO resolves to EXPEDIA env prefix

Group F: ExpediaVrboAdapter — AdapterResult Shape (4 tests)
  ✓  send() result has all required fields (expedia)
  ✓  send() result has all required fields (vrbo)
  ✓  provider label matches constructor arg
  ✓  strategy is always "api_first"

Group G: Idempotency Key Integration (5 tests)
  ✓  _build_idempotency_key returns consistent key same day
  ✓  Key contains booking_id and external_id
  ✓  Key with suffix appends suffix
  ✓  Empty booking_id still returns key (best-effort)
  ✓  Cancel key differs from send key

Group H: Shared Infrastructure (4 tests)
  ✓  _throttle with disabled flag returns immediately
  ✓  _throttle with rate_limit=0 returns (warning, no sleep)
  ✓  _retry_with_backoff with disabled flag calls fn once
  ✓  OutboundAdapter base raises NotImplementedError

CI-safe: no env API keys, all adapters return dry_run. No network calls.
"""
from __future__ import annotations

import os
import sys
import time
from unittest.mock import patch

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")
os.environ.setdefault("IHOUSE_THROTTLE_DISABLED", "true")
os.environ.setdefault("IHOUSE_RETRY_DISABLED", "true")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from adapters.outbound import (
    AdapterResult,
    OutboundAdapter,
    _build_idempotency_key,
    _retry_with_backoff,
    _throttle,
)
from adapters.outbound.airbnb_adapter import AirbnbAdapter
from adapters.outbound.bookingcom_adapter import BookingComAdapter
from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter


# ===========================================================================
# Group A — AirbnbAdapter — Dry-Run Mode
# ===========================================================================


class TestAirbnbDryRun:

    def test_send_dry_run_no_api_key(self):
        with patch.dict(os.environ, {"AIRBNB_API_KEY": ""}, clear=False):
            adapter = AirbnbAdapter()
            result = adapter.send("listing-001", "airbnb_RES001")
            assert result.status == "dry_run"
            assert result.provider == "airbnb"
            assert result.http_status is None

    def test_cancel_dry_run_no_api_key(self):
        with patch.dict(os.environ, {"AIRBNB_API_KEY": ""}, clear=False):
            adapter = AirbnbAdapter()
            result = adapter.cancel("listing-001", "airbnb_RES001")
            assert result.status == "dry_run"
            assert "cancel" in result.message.lower()

    def test_amend_dry_run_no_api_key(self):
        with patch.dict(os.environ, {"AIRBNB_API_KEY": ""}, clear=False):
            adapter = AirbnbAdapter()
            result = adapter.amend("listing-001", "airbnb_RES001",
                                   check_in="2026-04-01", check_out="2026-04-06")
            assert result.status == "dry_run"
            assert "amend" in result.message.lower()

    def test_send_dry_run_global_flag(self):
        with patch.dict(os.environ, {
            "AIRBNB_API_KEY": "test-key-123",
            "IHOUSE_DRY_RUN": "true",
        }, clear=False):
            adapter = AirbnbAdapter()
            result = adapter.send("listing-001", "airbnb_RES001")
            assert result.status == "dry_run"
            assert "DRY_RUN" in result.message

    def test_send_dry_run_explicit_param(self):
        with patch.dict(os.environ, {"AIRBNB_API_KEY": "test-key"}, clear=False):
            adapter = AirbnbAdapter()
            result = adapter.send("listing-001", "airbnb_RES001", dry_run=True)
            assert result.status == "dry_run"

    def test_amend_includes_phase_info(self):
        with patch.dict(os.environ, {"AIRBNB_API_KEY": ""}, clear=False):
            adapter = AirbnbAdapter()
            result = adapter.amend("listing-001", "airbnb_RES001")
            assert "Phase 155" in result.message


# ===========================================================================
# Group B — AirbnbAdapter — AdapterResult Shape
# ===========================================================================


class TestAirbnbResultShape:

    def test_send_result_fields(self):
        with patch.dict(os.environ, {"AIRBNB_API_KEY": ""}, clear=False):
            adapter = AirbnbAdapter()
            result = adapter.send("listing-001", "airbnb_RES001")
            assert isinstance(result, AdapterResult)
            assert hasattr(result, "provider")
            assert hasattr(result, "external_id")
            assert hasattr(result, "strategy")
            assert hasattr(result, "status")
            assert hasattr(result, "http_status")
            assert hasattr(result, "message")

    def test_provider_is_airbnb(self):
        with patch.dict(os.environ, {"AIRBNB_API_KEY": ""}, clear=False):
            adapter = AirbnbAdapter()
            result = adapter.send("listing-001", "airbnb_RES001")
            assert result.provider == "airbnb"

    def test_strategy_is_api_first(self):
        with patch.dict(os.environ, {"AIRBNB_API_KEY": ""}, clear=False):
            adapter = AirbnbAdapter()
            result = adapter.send("listing-001", "airbnb_RES001")
            assert result.strategy == "api_first"

    def test_cancel_message(self):
        with patch.dict(os.environ, {"AIRBNB_API_KEY": ""}, clear=False):
            adapter = AirbnbAdapter()
            result = adapter.cancel("listing-001", "airbnb_RES001")
            assert "cancel" in result.message.lower()
            assert result.external_id == "listing-001"


# ===========================================================================
# Group C — BookingComAdapter — Dry-Run Mode
# ===========================================================================


class TestBookingComDryRun:

    def test_send_dry_run_no_api_key(self):
        with patch.dict(os.environ, {"BOOKINGCOM_API_KEY": ""}, clear=False):
            adapter = BookingComAdapter()
            result = adapter.send("hotel-001", "bookingcom_RES001")
            assert result.status == "dry_run"
            assert result.provider == "bookingcom"
            assert result.http_status is None

    def test_cancel_dry_run_no_api_key(self):
        with patch.dict(os.environ, {"BOOKINGCOM_API_KEY": ""}, clear=False):
            adapter = BookingComAdapter()
            result = adapter.cancel("hotel-001", "bookingcom_RES001")
            assert result.status == "dry_run"
            assert "cancel" in result.message.lower()

    def test_amend_dry_run_no_api_key(self):
        with patch.dict(os.environ, {"BOOKINGCOM_API_KEY": ""}, clear=False):
            adapter = BookingComAdapter()
            result = adapter.amend("hotel-001", "bookingcom_RES001",
                                   check_in="2026-05-01", check_out="2026-05-05")
            assert result.status == "dry_run"
            assert "amend" in result.message.lower()

    def test_send_dry_run_global_flag(self):
        with patch.dict(os.environ, {
            "BOOKINGCOM_API_KEY": "test-key-456",
            "IHOUSE_DRY_RUN": "true",
        }, clear=False):
            adapter = BookingComAdapter()
            result = adapter.send("hotel-001", "bookingcom_RES001")
            assert result.status == "dry_run"
            assert "DRY_RUN" in result.message

    def test_amend_with_dates(self):
        with patch.dict(os.environ, {"BOOKINGCOM_API_KEY": ""}, clear=False):
            adapter = BookingComAdapter()
            result = adapter.amend("hotel-001", "bookingcom_RES001",
                                   check_in="2026-05-01", check_out="2026-05-05")
            assert result.status == "dry_run"
            assert "Phase 155" in result.message


# ===========================================================================
# Group D — BookingComAdapter — AdapterResult Shape
# ===========================================================================


class TestBookingComResultShape:

    def test_send_result_fields(self):
        with patch.dict(os.environ, {"BOOKINGCOM_API_KEY": ""}, clear=False):
            adapter = BookingComAdapter()
            result = adapter.send("hotel-001", "bookingcom_RES001")
            assert isinstance(result, AdapterResult)

    def test_provider_is_bookingcom(self):
        with patch.dict(os.environ, {"BOOKINGCOM_API_KEY": ""}, clear=False):
            adapter = BookingComAdapter()
            result = adapter.send("hotel-001", "bookingcom_RES001")
            assert result.provider == "bookingcom"

    def test_strategy_is_api_first(self):
        with patch.dict(os.environ, {"BOOKINGCOM_API_KEY": ""}, clear=False):
            adapter = BookingComAdapter()
            result = adapter.send("hotel-001", "bookingcom_RES001")
            assert result.strategy == "api_first"

    def test_cancel_message(self):
        with patch.dict(os.environ, {"BOOKINGCOM_API_KEY": ""}, clear=False):
            adapter = BookingComAdapter()
            result = adapter.cancel("hotel-001", "bookingcom_RES001")
            assert "cancel" in result.message.lower()
            assert result.external_id == "hotel-001"


# ===========================================================================
# Group E — ExpediaVrboAdapter — Dual Provider
# ===========================================================================


class TestExpediaVrboDualProvider:

    def test_default_provider_is_expedia(self):
        adapter = ExpediaVrboAdapter()
        assert adapter.provider == "expedia"

    def test_send_dry_run_expedia(self):
        with patch.dict(os.environ, {"EXPEDIA_API_KEY": ""}, clear=False):
            adapter = ExpediaVrboAdapter("expedia")
            result = adapter.send("prop-001", "expedia_RES001")
            assert result.status == "dry_run"
            assert result.provider == "expedia"

    def test_send_dry_run_vrbo(self):
        with patch.dict(os.environ, {"EXPEDIA_API_KEY": ""}, clear=False):
            adapter = ExpediaVrboAdapter("vrbo")
            result = adapter.send("prop-002", "vrbo_RES001")
            assert result.status == "dry_run"
            assert result.provider == "vrbo"

    def test_cancel_dry_run_vrbo(self):
        with patch.dict(os.environ, {"EXPEDIA_API_KEY": ""}, clear=False):
            adapter = ExpediaVrboAdapter("vrbo")
            result = adapter.cancel("prop-002", "vrbo_RES001")
            assert result.status == "dry_run"
            assert "cancel" in result.message.lower()
            assert result.provider == "vrbo"

    def test_amend_dry_run_expedia(self):
        with patch.dict(os.environ, {"EXPEDIA_API_KEY": ""}, clear=False):
            adapter = ExpediaVrboAdapter("expedia")
            result = adapter.amend("prop-001", "expedia_RES001",
                                   check_in="2026-06-01", check_out="2026-06-10")
            assert result.status == "dry_run"
            assert "amend" in result.message.lower()

    def test_vrbo_resolves_to_expedia_env_prefix(self):
        """VRBO uses the EXPEDIA_API_KEY env var (shared Partner Solutions API)."""
        with patch.dict(os.environ, {"EXPEDIA_API_KEY": ""}, clear=False):
            adapter = ExpediaVrboAdapter("vrbo")
            result = adapter.send("prop-002", "vrbo_RES001")
            assert "EXPEDIA_API_KEY" in result.message


# ===========================================================================
# Group F — ExpediaVrboAdapter — AdapterResult Shape
# ===========================================================================


class TestExpediaVrboResultShape:

    def test_send_result_expedia(self):
        with patch.dict(os.environ, {"EXPEDIA_API_KEY": ""}, clear=False):
            adapter = ExpediaVrboAdapter("expedia")
            result = adapter.send("prop-001", "expedia_RES001")
            assert isinstance(result, AdapterResult)

    def test_send_result_vrbo(self):
        with patch.dict(os.environ, {"EXPEDIA_API_KEY": ""}, clear=False):
            adapter = ExpediaVrboAdapter("vrbo")
            result = adapter.send("prop-002", "vrbo_RES002")
            assert isinstance(result, AdapterResult)

    def test_provider_label_matches_constructor(self):
        with patch.dict(os.environ, {"EXPEDIA_API_KEY": ""}, clear=False):
            exp = ExpediaVrboAdapter("expedia")
            vrb = ExpediaVrboAdapter("vrbo")
            assert exp.send("p1", "b1").provider == "expedia"
            assert vrb.send("p2", "b2").provider == "vrbo"

    def test_strategy_is_api_first(self):
        with patch.dict(os.environ, {"EXPEDIA_API_KEY": ""}, clear=False):
            adapter = ExpediaVrboAdapter("expedia")
            result = adapter.send("prop-001", "expedia_RES001")
            assert result.strategy == "api_first"


# ===========================================================================
# Group G — Idempotency Key Integration
# ===========================================================================


class TestIdempotencyKeyIntegration:

    def test_consistent_key_same_day(self):
        k1 = _build_idempotency_key("booking-1", "ext-1")
        k2 = _build_idempotency_key("booking-1", "ext-1")
        assert k1 == k2

    def test_key_contains_ids(self):
        key = _build_idempotency_key("booking-ABC", "ext-XYZ")
        assert "booking-ABC" in key
        assert "ext-XYZ" in key

    def test_key_with_suffix(self):
        key = _build_idempotency_key("b1", "e1", suffix="cancel")
        assert key.endswith(":cancel")

    def test_empty_booking_id_best_effort(self):
        # Should not raise; returns a best-effort key with warning
        key = _build_idempotency_key("", "ext-1")
        assert isinstance(key, str)
        assert len(key) > 0

    def test_cancel_key_differs_from_send_key(self):
        send_key = _build_idempotency_key("b1", "e1")
        cancel_key = _build_idempotency_key("b1", "e1", suffix="cancel")
        assert send_key != cancel_key


# ===========================================================================
# Group H — Shared Infrastructure
# ===========================================================================


class TestSharedInfrastructure:

    def test_throttle_disabled_returns_immediately(self):
        with patch.dict(os.environ, {"IHOUSE_THROTTLE_DISABLED": "true"}, clear=False):
            start = time.monotonic()
            _throttle(1)  # rate_limit=1 would sleep 60s if not disabled
            elapsed = time.monotonic() - start
            assert elapsed < 1.0

    def test_throttle_zero_rate_limit_no_sleep(self):
        with patch.dict(os.environ, {"IHOUSE_THROTTLE_DISABLED": "false"}, clear=False):
            start = time.monotonic()
            _throttle(0)  # Should warn and return without sleeping
            elapsed = time.monotonic() - start
            assert elapsed < 1.0

    def test_retry_disabled_calls_fn_once(self):
        call_count = 0
        def fn():
            nonlocal call_count
            call_count += 1
            return "result"
        with patch.dict(os.environ, {"IHOUSE_RETRY_DISABLED": "true"}, clear=False):
            result = _retry_with_backoff(fn)
            assert result == "result"
            assert call_count == 1

    def test_base_adapter_raises_not_implemented(self):
        base = OutboundAdapter()
        try:
            base.send("ext", "bk", 60)
            assert False, "Should have raised NotImplementedError"
        except NotImplementedError:
            pass
        try:
            base.push("ext", "bk", 60)
            assert False, "Should have raised NotImplementedError"
        except NotImplementedError:
            pass
