"""
Phase 351 — Performance Baseline + Rate Limiting Validation
=============================================================

New tests extending existing rate-limiter coverage with:
  - Concurrent throughput under multi-threaded load
  - Thread-safety: multiple tenants, no cross-contamination
  - Retry-After header correctness
  - Rate-limit bypass (limit=0) under concurrent calls
  - Outbound probe timing baselines
  - Health check response-time baseline
  - Throttle disabled fast-path

Groups:
  A — Concurrent Rate Limiting (6 tests)
  B — Rate Limiter Edge Cases (5 tests)
  C — Health Check Timing Baseline (4 tests)
  D — Outbound Sync Probe Baselines (4 tests)
  E — Throttle + Retry Performance (4 tests)
"""
from __future__ import annotations

import os
import sys
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from unittest.mock import MagicMock

os.environ.setdefault("IHOUSE_ENV", "test")
os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("IHOUSE_THROTTLE_DISABLED", "true")
os.environ.setdefault("IHOUSE_RETRY_DISABLED", "true")

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.rate_limiter import InMemoryRateLimiter  # noqa: E402
from api.health import (  # noqa: E402
    run_health_checks,
    probe_outbound_sync,
    OutboundSyncProbeResult,
)
from adapters.outbound import _throttle, _retry_with_backoff, AdapterResult  # noqa: E402


# ---------------------------------------------------------------------------
# Group A — Concurrent Rate Limiting
# ---------------------------------------------------------------------------

class TestGroupAConcurrent:
    """Thread-safety and multi-tenant isolation under concurrent load."""

    def test_a1_concurrent_same_tenant_hits_limit(self):
        """
        10 threads sending 1 request each to same tenant (limit=5).
        Exactly 5 should succeed, rest should get 429.
        """
        limiter = InMemoryRateLimiter(rpm=5, window=60)
        successes = []
        errors = []
        lock = threading.Lock()

        def make_request():
            try:
                limiter.check("tenant-concurrent")
                with lock:
                    successes.append(1)
            except HTTPException as e:
                with lock:
                    errors.append(e.status_code)

        threads = [threading.Thread(target=make_request) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(successes) == 5
        assert len(errors) == 5
        assert all(c == 429 for c in errors)

    def test_a2_multi_tenant_isolation_under_concurrent_load(self):
        """
        5 tenants × 3 requests (limit=3) simultaneously.
        All 15 should succeed (each tenant has its own bucket).
        """
        limiter = InMemoryRateLimiter(rpm=3, window=60)
        successes = []
        errors = []
        lock = threading.Lock()

        def make_request(tid: str):
            try:
                limiter.check(tid)
                with lock:
                    successes.append(tid)
            except HTTPException:
                with lock:
                    errors.append(tid)

        threads = []
        for tenant_n in range(5):
            for _ in range(3):
                threads.append(
                    threading.Thread(target=make_request, args=(f"tenant-{tenant_n}",))
                )

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(successes) == 15
        assert len(errors) == 0

    def test_a3_tenant_isolation_no_bleed(self):
        """
        Tenant A hits limit, Tenant B is unaffected.
        """
        limiter = InMemoryRateLimiter(rpm=3, window=60)
        for _ in range(3):
            limiter.check("tenant-A")

        # A is at limit
        with pytest.raises(HTTPException) as einfo:
            limiter.check("tenant-A")
        assert einfo.value.status_code == 429

        # B is unaffected
        for _ in range(3):
            limiter.check("tenant-B")  # should not raise

    def test_a4_concurrent_burst_throughput(self):
        """
        100 sequential requests (limit=100) all succeed under 500ms.
        """
        limiter = InMemoryRateLimiter(rpm=100, window=60)
        start = time.monotonic()
        for _ in range(100):
            limiter.check("perf-tenant")
        elapsed = time.monotonic() - start
        # 100 in-memory checks should complete in << 500ms
        assert elapsed < 0.5

    def test_a5_dev_bypass_under_concurrent_load(self):
        """
        With rpm=0 (dev bypass), unlimited concurrent requests all succeed.
        """
        limiter = InMemoryRateLimiter(rpm=0, window=60)
        results = []
        lock = threading.Lock()

        def make_request():
            try:
                limiter.check("any-tenant")
                with lock:
                    results.append("ok")
            except HTTPException:
                with lock:
                    results.append("err")

        threads = [threading.Thread(target=make_request) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count("ok") == 50
        assert results.count("err") == 0

    def test_a6_new_tenant_gets_fresh_bucket(self):
        """
        New tenant IDs always start with a clean bucket.
        """
        limiter = InMemoryRateLimiter(rpm=2, window=60)
        # Fill tenant-X and prove tenant-NEW is clean
        for _ in range(2):
            limiter.check("tenant-X")
        # New tenant should not be affected
        limiter.check("tenant-new-1")
        limiter.check("tenant-new-2")  # both succeed


# ---------------------------------------------------------------------------
# Group B — Rate Limiter Edge Cases
# ---------------------------------------------------------------------------

class TestGroupBEdgeCases:
    """Edge case validation for InMemoryRateLimiter."""

    def test_b1_retry_after_header_present(self):
        """429 response includes retry_after_seconds > 0 in detail."""
        limiter = InMemoryRateLimiter(rpm=1, window=60)
        limiter.check("tenant-b1")
        with pytest.raises(HTTPException) as einfo:
            limiter.check("tenant-b1")
        detail = einfo.value.detail
        assert "retry_after_seconds" in detail
        assert detail["retry_after_seconds"] >= 1

    def test_b2_error_code_is_rate_limit_exceeded(self):
        """429 error code is RATE_LIMIT_EXCEEDED."""
        limiter = InMemoryRateLimiter(rpm=1, window=60)
        limiter.check("tenant-b2")
        with pytest.raises(HTTPException) as einfo:
            limiter.check("tenant-b2")
        assert einfo.value.detail["error"] == "RATE_LIMIT_EXCEEDED"

    def test_b3_window_expiry_allows_new_requests(self):
        """After window expires, requests are allowed again."""
        limiter = InMemoryRateLimiter(rpm=2, window=1)  # 1-second window
        limiter.check("tenant-b3")
        limiter.check("tenant-b3")
        # Window expires
        time.sleep(1.1)
        # Should succeed again
        limiter.check("tenant-b3")
        limiter.check("tenant-b3")

    def test_b4_rpm_1_allows_exactly_one(self):
        """rpm=1 allows the first request, blocks the second."""
        limiter = InMemoryRateLimiter(rpm=1, window=60)
        limiter.check("tenant-b4")
        with pytest.raises(HTTPException):
            limiter.check("tenant-b4")

    def test_b5_bucket_eviction_on_check(self):
        """Old timestamps are evicted from bucket during check()."""
        limiter = InMemoryRateLimiter(rpm=2, window=1)
        limiter.check("tenant-b5")
        time.sleep(1.1)
        # Old entry expires; bucket is refilled on next check
        limiter.check("tenant-b5")
        bucket = limiter._buckets.get("tenant-b5")
        assert bucket is not None
        assert len(bucket) == 1  # Only the new entry remains


# ---------------------------------------------------------------------------
# Group C — Health Check Timing Baseline
# ---------------------------------------------------------------------------

class TestGroupCHealthTiming:
    """Health check completes quickly without live DB connections."""

    def test_c1_health_check_returns_in_under_1s_without_supabase_url(self):
        """run_health_checks without SUPABASE_URL completes instantly."""
        orig = os.environ.pop("SUPABASE_URL", None)
        try:
            start = time.monotonic()
            result = run_health_checks(version="test", env="test")
            elapsed = time.monotonic() - start
        finally:
            if orig:
                os.environ["SUPABASE_URL"] = orig

        assert elapsed < 1.0
        assert result.status in ("ok", "degraded", "unhealthy")

    def test_c2_health_result_has_version(self):
        """HealthResult version field matches input."""
        orig = os.environ.pop("SUPABASE_URL", None)
        try:
            result = run_health_checks(version="1.2.3", env="staging")
        finally:
            if orig:
                os.environ["SUPABASE_URL"] = orig
        assert result.version == "1.2.3"
        assert result.env == "staging"

    def test_c3_health_result_has_checks_dict(self):
        """HealthResult.checks is a dict."""
        orig = os.environ.pop("SUPABASE_URL", None)
        try:
            result = run_health_checks(version="v", env="e")
        finally:
            if orig:
                os.environ["SUPABASE_URL"] = orig
        assert isinstance(result.checks, dict)

    def test_c4_health_status_is_valid_string(self):
        """HealthResult.status is one of the valid strings."""
        orig = os.environ.pop("SUPABASE_URL", None)
        try:
            result = run_health_checks(version="v", env="e")
        finally:
            if orig:
                os.environ["SUPABASE_URL"] = orig
        assert result.status in ("ok", "degraded", "unhealthy")


# ---------------------------------------------------------------------------
# Group D — Outbound Sync Probe Baselines
# ---------------------------------------------------------------------------

class TestGroupDOutboundProbes:
    """probe_outbound_sync returns correct structure, completes quickly."""

    def _mock_db(self, rows_last=None, rows_7d=None):
        db = MagicMock()
        q = MagicMock()
        for m in ("select", "eq", "gte", "order", "limit"):
            setattr(q, m, MagicMock(return_value=q))
        # Alternate between last-sync and 7d queries
        q.execute.side_effect = [
            MagicMock(data=rows_last or []),
            MagicMock(data=rows_7d or []),
        ] * 20  # plenty for all providers
        db.table.return_value = q
        return db

    def test_d1_idle_provider_returns_idle_status(self):
        """Provider with no log entries → status=idle."""
        db = self._mock_db(rows_last=[], rows_7d=[])
        results = probe_outbound_sync(db, providers=["airbnb"], now=datetime.now(timezone.utc))
        assert len(results) == 1
        assert results[0].status == "idle"
        assert results[0].provider == "airbnb"

    def test_d2_healthy_provider_returns_ok(self):
        """Provider with recent sync, low failure rate → status=ok."""
        now = datetime.now(timezone.utc)
        db = self._mock_db(
            rows_last=[{"synced_at": now.isoformat(), "status": "ok"}],
            rows_7d=[{"status": "ok"}, {"status": "ok"}, {"status": "ok"}],
        )
        results = probe_outbound_sync(db, providers=["bookingcom"], now=now)
        assert results[0].status == "ok"
        assert results[0].failure_rate_7d == 0.0

    def test_d3_high_failure_rate_returns_degraded(self):
        """Provider with >20% failure rate → status=degraded."""
        now = datetime.now(timezone.utc)
        db = self._mock_db(
            rows_last=[{"synced_at": now.isoformat(), "status": "failed"}],
            rows_7d=[{"status": "failed"}, {"status": "failed"}, {"status": "ok"}],
        )
        results = probe_outbound_sync(db, providers=["expedia"], now=now)
        assert results[0].status == "degraded"

    def test_d4_db_error_returns_error_status(self):
        """DB exception → status=error, never raises."""
        db = MagicMock()
        db.table.side_effect = RuntimeError("DB down")
        results = probe_outbound_sync(db, providers=["airbnb"])
        assert len(results) == 1
        assert results[0].status == "error"
        assert results[0].failure_rate_7d is None


# ---------------------------------------------------------------------------
# Group E — Throttle + Retry Fast-Path Performance
# ---------------------------------------------------------------------------

class TestGroupEThrottleRetry:
    """Throttle disabled and retry disabled paths are fast."""

    def test_e1_throttle_disabled_is_instant(self):
        """_throttle does nothing when IHOUSE_THROTTLE_DISABLED=true."""
        start = time.monotonic()
        _throttle(60)       # would sleep 1s at rate=60
        _throttle(1)        # would sleep 60s at rate=1
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    def test_e2_retry_disabled_calls_fn_once(self):
        """_retry_with_backoff with IHOUSE_RETRY_DISABLED=true calls fn exactly once."""
        call_count = [0]

        def fn():
            call_count[0] += 1
            r = MagicMock()
            r.http_status = 500
            return r

        _retry_with_backoff(fn)
        assert call_count[0] == 1  # disabled → called once, no retries

    def test_e3_retry_returns_fn_result(self):
        """_retry_with_backoff returns the function's result directly."""
        r = AdapterResult(
            provider="test", external_id="x", strategy="api_first",
            status="ok", http_status=200, message="ok"
        )

        result = _retry_with_backoff(lambda: r)
        assert result is r

    def test_e4_rate_limiter_1000_requests_under_1s(self):
        """
        1000 in-memory rate limit checks (limit=1000, window=60) < 1s.
        Validates the data structure is not a performance bottleneck.
        """
        limiter = InMemoryRateLimiter(rpm=1000, window=60)
        start = time.monotonic()
        for i in range(1000):
            limiter.check(f"tenant-perf-{i % 20}")  # 20 unique tenants
        elapsed = time.monotonic() - start
        assert elapsed < 1.0
