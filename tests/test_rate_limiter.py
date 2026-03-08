"""
Contract tests for Phase 62 — Per-Tenant Rate Limiting (src/api/rate_limiter.py).

Tests the InMemoryRateLimiter directly (unit-level) — no HTTP server needed.

Coverage:
    1. Under limit → no exception
    2. At exactly the limit → no exception
    3. Over limit (N+1) → HTTP 429
    4. Tenant A over limit, Tenant B not affected (isolation)
    5. Window reset: old requests expire, new ones allowed
    6. Dev bypass (limit=0) → never raises
"""
from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from api.rate_limiter import InMemoryRateLimiter


# ---------------------------------------------------------------------------
# Test 1: Under limit → no exception
# ---------------------------------------------------------------------------

def test_under_limit_no_exception():
    limiter = InMemoryRateLimiter(rpm=5, window=60)
    for _ in range(4):
        limiter.check("tenant-a")  # should not raise


# ---------------------------------------------------------------------------
# Test 2: At exactly the limit → no exception
# ---------------------------------------------------------------------------

def test_at_limit_no_exception():
    limiter = InMemoryRateLimiter(rpm=5, window=60)
    for _ in range(5):
        limiter.check("tenant-a")  # exactly 5 — should not raise


# ---------------------------------------------------------------------------
# Test 3: Over limit (N+1) → 429
# ---------------------------------------------------------------------------

def test_over_limit_raises_429():
    limiter = InMemoryRateLimiter(rpm=3, window=60)
    for _ in range(3):
        limiter.check("tenant-a")  # fill the bucket
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("tenant-a")  # 4th → 429
    assert exc_info.value.status_code == 429
    detail = exc_info.value.detail
    assert detail["error"] == "RATE_LIMIT_EXCEEDED"
    assert "retry_after_seconds" in detail


# ---------------------------------------------------------------------------
# Test 4: Tenant isolation — A over limit, B not affected
# ---------------------------------------------------------------------------

def test_tenant_isolation():
    limiter = InMemoryRateLimiter(rpm=2, window=60)
    # Exhaust tenant-a
    limiter.check("tenant-a")
    limiter.check("tenant-a")
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("tenant-a")
    assert exc_info.value.status_code == 429

    # tenant-b must not be affected
    limiter.check("tenant-b")  # should not raise
    limiter.check("tenant-b")  # should not raise


# ---------------------------------------------------------------------------
# Test 5: Window reset — old requests expire, new ones allowed
# ---------------------------------------------------------------------------

def test_window_reset_allows_new_requests():
    """Requests outside the window are evicted, freeing capacity."""
    limiter = InMemoryRateLimiter(rpm=2, window=1)  # 1-second window for speed
    limiter.check("tenant-x")
    limiter.check("tenant-x")

    # Over limit immediately
    with pytest.raises(HTTPException):
        limiter.check("tenant-x")

    # After window expires, requests are allowed again
    time.sleep(1.1)
    limiter.check("tenant-x")  # should not raise


# ---------------------------------------------------------------------------
# Test 6: Dev bypass (limit=0) → never raises
# ---------------------------------------------------------------------------

def test_dev_bypass_limit_zero():
    limiter = InMemoryRateLimiter(rpm=0, window=60)
    for _ in range(1000):
        limiter.check("any-tenant")  # should never raise
