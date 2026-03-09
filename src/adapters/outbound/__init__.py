"""
Phase 141 — Outbound Adapter Base Class + Rate-Limit Throttle

All outbound adapters implement this interface.

An adapter receives a dispatch request and returns an AdapterResult.
It is responsible for:
  1. Reading its own credentials from environment variables.
  2. Honouring the rate_limit (calls/minute) via _throttle() — Phase 141.
  3. Making the outbound HTTP call (or iCal push).
  4. Returning a structured AdapterResult.

Adapters must NOT raise exceptions — catch internally and return status='failed'.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

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
