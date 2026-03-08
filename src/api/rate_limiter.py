"""
Per-Tenant Rate Limiter — FastAPI Dependency
=============================================

Implements a sliding-window in-memory rate limiter keyed by tenant_id.

Configuration:
    IHOUSE_RATE_LIMIT_RPM   — requests per minute per tenant (default 60)
                              Set to 0 to disable (dev bypass).

HTTP response on exceeded limit:
    429 Too Many Requests
    Retry-After: <N>
    {"error": "RATE_LIMIT_EXCEEDED", "retry_after_seconds": <N>}

Design:
    - Sliding window using a deque of timestamps (no external dependencies)
    - Thread-safe via threading.Lock per tenant
    - Interface is purposely abstract — backend can be swapped to Redis
      in a future phase without changing callers

Usage:
    from api.rate_limiter import rate_limit
    from fastapi import Depends

    @router.post("/webhooks/{provider}")
    async def receive_webhook(
        ...,
        tenant_id: str = Depends(jwt_auth),
        _rate: None = Depends(rate_limit),
    ): ...
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque

from fastapi import HTTPException

logger = logging.getLogger(__name__)

_ENV_VAR = "IHOUSE_RATE_LIMIT_RPM"
_DEFAULT_RPM = 60
_WINDOW_SECONDS = 60


class InMemoryRateLimiter:
    """
    Per-tenant sliding-window rate limiter backed by in-process memory.

    Not suitable for multi-process deployments without an external store.
    Swap the backend for Redis in a future phase if horizontal scaling is needed.
    """

    def __init__(self, rpm: int = _DEFAULT_RPM, window: int = _WINDOW_SECONDS) -> None:
        self._limit = rpm
        self._window = window
        self._buckets: dict[str, deque[float]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._meta_lock = threading.Lock()

    def _get_bucket(self, tenant_id: str) -> tuple[deque[float], threading.Lock]:
        with self._meta_lock:
            if tenant_id not in self._buckets:
                self._buckets[tenant_id] = deque()
                self._locks[tenant_id] = threading.Lock()
            return self._buckets[tenant_id], self._locks[tenant_id]

    def check(self, tenant_id: str) -> None:
        """
        Record a request for tenant_id. Raises HTTP 429 if limit exceeded.

        Args:
            tenant_id: Tenant identifier (from verified JWT sub claim).

        Raises:
            HTTPException(429): limit exceeded, includes Retry-After header.
        """
        if self._limit == 0:
            return  # dev bypass

        bucket, lock = self._get_bucket(tenant_id)
        now = time.monotonic()
        cutoff = now - self._window

        with lock:
            # Evict timestamps outside the window
            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= self._limit:
                # Oldest request in window → retry after it expires
                oldest = bucket[0]
                retry_after = max(1, int(self._window - (now - oldest)) + 1)
                logger.warning(
                    "Rate limit exceeded for tenant=%s requests=%d limit=%d retry_after=%ds",
                    tenant_id,
                    len(bucket),
                    self._limit,
                    retry_after,
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "RATE_LIMIT_EXCEEDED",
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            bucket.append(now)


# ---------------------------------------------------------------------------
# Module-level singleton (shared across requests in the same process)
# ---------------------------------------------------------------------------

def _build_limiter() -> InMemoryRateLimiter:
    try:
        rpm = int(os.environ.get(_ENV_VAR, _DEFAULT_RPM))
    except (ValueError, TypeError):
        logger.warning(
            "Invalid %s value — falling back to default %d rpm",
            _ENV_VAR,
            _DEFAULT_RPM,
        )
        rpm = _DEFAULT_RPM

    if rpm == 0:
        logger.warning(
            "Rate limiting DISABLED — %s=0. Expected in local/test environments only.",
            _ENV_VAR,
        )
    else:
        logger.info("Rate limiter configured: %d rpm per tenant", rpm)

    return InMemoryRateLimiter(rpm=rpm)


# Singleton instance — initialised at import time
_limiter = _build_limiter()


def _make_rate_limit_dependency():
    """
    Returns a FastAPI Depends-compatible callable.
    Depends on jwt_auth so tenant_id is available.
    """
    from fastapi import Depends
    from api.auth import jwt_auth

    async def _dep(tenant_id: str = Depends(jwt_auth)) -> None:
        _limiter.check(tenant_id)

    return _dep


# The canonical Depends-injectable for route use
rate_limit = _make_rate_limit_dependency()
