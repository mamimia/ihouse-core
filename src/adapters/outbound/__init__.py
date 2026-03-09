"""
Phase 142 — Outbound Adapter Base Class + Rate-Limit Throttle + Retry

All outbound adapters implement this interface.

An adapter receives a dispatch request and returns an AdapterResult.
It is responsible for:
  1. Reading its own credentials from environment variables.
  2. Honouring the rate_limit (calls/minute) via _throttle() — Phase 141.
  3. Retrying on 5xx / network errors via _retry_with_backoff() — Phase 142.
  4. Making the outbound HTTP call (or iCal push).
  5. Returning a structured AdapterResult.

Adapters must NOT raise exceptions — catch internally and return status='failed'.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

_throttle_logger = logging.getLogger(__name__)


def _throttle(rate_limit: int) -> None:
    """
    Phase 141 — Rate-limit enforcement.

    Sleeps for one rate-limit slot (60s / rate_limit) before the adapter
    makes its outbound HTTP call.

    Disabled when:
    - IHOUSE_THROTTLE_DISABLED=true  (test / staging opt-out)
    - rate_limit <= 0                (best-effort: warn + continue)

    Never raises. Never blocks the dry-run path (adapters call this only on
    the real HTTP path, not inside the dry-run early-return branch).
    """
    if os.environ.get("IHOUSE_THROTTLE_DISABLED", "false").lower() == "true":
        return
    if rate_limit <= 0:
        _throttle_logger.warning(
            "rate_limit=%d is non-positive — throttle skipped (best-effort)",
            rate_limit,
        )
        return
    time.sleep(60.0 / rate_limit)


_T = TypeVar("_T")
_retry_logger = logging.getLogger(__name__ + ".retry")

_MAX_BACKOFF_SECONDS = 30.0


def _retry_with_backoff(fn: Callable[[], _T], max_retries: int = 3) -> _T:
    """
    Phase 142 — Retry with exponential backoff.

    Calls fn() and retries up to max_retries times when:
      - fn() returns an AdapterResult with http_status >= 500
      - fn() raises any exception (network error, timeout, etc.)

    Does NOT retry on:
      - 4xx responses (client error — retrying is pointless)
      - 2xx / 3xx responses (success)
      - dry_run / None http_status (no HTTP call was made)

    Backoff sequence (4 ** attempt, capped at 30s):
      attempt 0 → call (no pre-sleep)
      attempt 1 → sleep 1s, retry
      attempt 2 → sleep 4s, retry
      attempt 3 → sleep 16s, retry → stop

    Disabled when:
      - IHOUSE_RETRY_DISABLED=true  (test / staging opt-out)

    Never raises — the caller's except block catches exhausted retries via
    the last exception re-raise (or the adapter returns the last 5xx result).
    """
    if os.environ.get("IHOUSE_RETRY_DISABLED", "false").lower() == "true":
        return fn()

    last_exc: Optional[Exception] = None
    last_result = None

    for attempt in range(max_retries + 1):
        # Pre-attempt sleep (skip on first attempt)
        if attempt > 0:
            delay = min(4.0 ** (attempt - 1), _MAX_BACKOFF_SECONDS)
            _retry_logger.warning(
                "retry attempt %d/%d — sleeping %.1fs after previous failure",
                attempt, max_retries, delay,
            )
            time.sleep(delay)

        try:
            last_result = fn()
            # Check for 5xx — retry if we have attempts left
            http_st = getattr(last_result, "http_status", None)
            if http_st is not None and http_st >= 500:
                if attempt < max_retries:
                    _retry_logger.warning(
                        "5xx (HTTP %d) on attempt %d — will retry", http_st, attempt,
                    )
                    last_exc = None
                    continue
            # 2xx / 4xx / None → return immediately without retry
            return last_result
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < max_retries:
                _retry_logger.warning(
                    "exception on attempt %d — will retry: %s", attempt, exc,
                )
                continue
            # All retries exhausted — re-raise so caller's except block handles it
            raise

    # All retries exhausted with 5xx (no exception path)
    return last_result  # type: ignore[return-value]


@dataclass
class AdapterResult:
    """The result of a single outbound adapter call."""
    provider:     str
    external_id:  str
    strategy:     str   # api_first | ical_fallback
    status:       str   # ok | failed | dry_run
    http_status:  Optional[int]
    message:      str


class OutboundAdapter:
    """
    Abstract base for outbound OTA adapters.
    Subclasses implement send() for api_first or push() for ical_fallback.
    """
    provider: str = "unknown"

    def send(
        self,
        external_id: str,
        booking_id: str,
        rate_limit: int,
        dry_run: bool = False,
    ) -> AdapterResult:
        """
        Send an availability lock to the OTA's write API.
        Override in api_first (Tier A) adapters.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support api_first.")

    def push(
        self,
        external_id: str,
        booking_id: str,
        rate_limit: int,
        dry_run: bool = False,
    ) -> AdapterResult:
        """
        Push an iCal feed update to the OTA.
        Override in ical_fallback (Tier B/C) adapters.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support ical_fallback.")
