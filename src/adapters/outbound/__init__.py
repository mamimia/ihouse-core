"""
Phase 143 — Outbound Adapter Base Class + Rate-Limit Throttle + Retry + Idempotency Key

All outbound adapters implement this interface.

An adapter receives a dispatch request and returns an AdapterResult.
It is responsible for:
  1. Reading its own credentials from environment variables.
  2. Honouring the rate_limit (calls/minute) via _throttle() — Phase 141.
  3. Retrying on 5xx / network errors via _retry_with_backoff() — Phase 142.
  4. Attaching X-Idempotency-Key header via _build_idempotency_key() — Phase 143.
  5. Making the outbound HTTP call (or iCal push).
  6. Returning a structured AdapterResult.

Adapters must NOT raise exceptions — catch internally and return status='failed'.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar
from datetime import date as _date

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


_idem_logger = logging.getLogger(__name__ + ".idempotency")


def _build_idempotency_key(booking_id: str, external_id: str, suffix: str = "") -> str:
    """
    Phase 143 — Build a stable idempotency key for an outbound request.
    Phase 154 — Added optional suffix to distinguish cancel from send.

    Format: ``{booking_id}:{external_id}:{YYYYMMDD}`` or
            ``{booking_id}:{external_id}:{YYYYMMDD}:{suffix}`` when suffix given.

    The key is stable within the same calendar day (UTC).  Adapters that
    support idempotency headers should attach it as ``X-Idempotency-Key``.

    Rules:
    - booking_id and external_id must not be empty (logs a warning and
      returns a best-effort key if either is missing).
    - The date component rolls over at UTC midnight, ensuring a fresh key
      per day even if the same booking is synced multiple times.
    - suffix (e.g. "cancel") disambiguates different operation types.
    """
    if not booking_id or not external_id:
        _idem_logger.warning(
            "_build_idempotency_key called with empty booking_id=%r or external_id=%r",
            booking_id, external_id,
        )
    day = _date.today().strftime("%Y%m%d")
    base = f"{booking_id}:{external_id}:{day}"
    return f"{base}:{suffix}" if suffix else base


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

    Tier A (api_first) adapters implement: send(), cancel(), amend()
    Tier B/C (ical_fallback) adapters implement: push(), cancel()

    Contract (all methods):
      - MUST NOT raise — catch internally and return status='failed'.
      - MUST return an AdapterResult.
      - MUST honour dry-run when IHOUSE_DRY_RUN=true or credentials absent.
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
        Send an availability lock to the OTA's write API (BOOKING_CREATED).
        Override in api_first (Tier A) adapters.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support send().")

    def push(
        self,
        external_id: str,
        booking_id: str,
        rate_limit: int,
        dry_run: bool = False,
        check_in: Optional[str] = None,
        check_out: Optional[str] = None,
    ) -> AdapterResult:
        """
        Push an iCal feed update to the OTA (BOOKING_CREATED / BOOKING_AMENDED).
        Override in ical_fallback (Tier B/C) adapters.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support push().")

    def cancel(
        self,
        external_id: str,
        booking_id: str,
        rate_limit: int = 60,
    ) -> AdapterResult:
        """
        Push a cancellation to the OTA (BOOKING_CANCELED).
        Phase 154: Override in Tier A adapters (API cancel).
        Phase 151: Override in Tier B adapters (iCal cancel).
        Default: return dry_run (unsupported by this adapter).
        """
        return AdapterResult(
            provider=self.provider,
            external_id=external_id,
            strategy="api_first",
            status="dry_run",
            http_status=None,
            message=f"{self.__class__.__name__} does not support cancel() — dry_run.",
        )

    def amend(
        self,
        external_id: str,
        booking_id: str,
        check_in: Optional[str] = None,
        check_out: Optional[str] = None,
        rate_limit: int = 60,
    ) -> AdapterResult:
        """
        Push a booking amendment to the OTA (BOOKING_AMENDED).
        Phase 155: Override in Tier A adapters (API amend).
        Default: return dry_run (unsupported by this adapter).
        """
        return AdapterResult(
            provider=self.provider,
            external_id=external_id,
            strategy="api_first",
            status="dry_run",
            http_status=None,
            message=f"{self.__class__.__name__} does not support amend() — dry_run.",
        )

