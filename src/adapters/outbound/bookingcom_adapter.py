"""
Phase 143 — Booking.com Outbound Adapter (Idempotency Key)

Implements availability locking via the Booking.com Connectivity Partner API (api_first).

Credentials (from environment):
    BOOKINGCOM_API_KEY   — Connectivity Partner API key
    BOOKINGCOM_API_BASE  — Base URL (default: https://supply-xml.booking.com/v1)

Booking.com availability block endpoint (simplified):
    POST /hotels/availability-blocks
    Body: {
        "hotel_id":   "<external_id>",
        "block_type": "closed",
        "notes":      "Blocked by iHouse Core (booking_id=<booking_id>)"
    }

Phase 139: well-formed request. Falls back to dry_run if credentials absent.
Rate limits: 60 requests/min.
"""
from __future__ import annotations

import logging
import os

try:
    import httpx  # type: ignore[import]
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from adapters.outbound import AdapterResult, OutboundAdapter, _build_idempotency_key, _retry_with_backoff, _throttle

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://supply-xml.booking.com/v1"
_PROVIDER     = "bookingcom"


class BookingComAdapter(OutboundAdapter):
    """
    Outbound adapter for Booking.com Connectivity Partner API (Tier A — api_first).
    """
    provider = _PROVIDER

    def send(
        self,
        external_id: str,
        booking_id: str,
        rate_limit: int = 60,
        dry_run: bool = False,
    ) -> AdapterResult:
        api_key  = os.environ.get("BOOKINGCOM_API_KEY", "")
        base_url = os.environ.get("BOOKINGCOM_API_BASE", _DEFAULT_BASE)
        global_dry_run = os.environ.get("IHOUSE_DRY_RUN", "false").lower() == "true"

        if dry_run or global_dry_run or not api_key:
            reason = (
                "IHOUSE_DRY_RUN=true" if global_dry_run
                else "BOOKINGCOM_API_KEY not configured — dry-run mode"
                if not api_key else "dry_run=True requested"
            )
            logger.info(
                "[DRY-RUN] bookingcom api_first: external_id=%s reason=%s",
                external_id, reason,
            )
            return AdapterResult(
                provider=_PROVIDER, external_id=external_id,
                strategy="api_first", status="dry_run",
                http_status=None,
                message=f"[Phase 139 dry-run] bookingcom: {reason}",
            )

        try:
            if httpx is None:  # pragma: no cover
                raise RuntimeError("httpx not available")
            url = f"{base_url}/hotels/availability-blocks"
            payload = {
                "hotel_id":   external_id,
                "block_type": "closed",
                "notes":      f"Blocked by iHouse Core (booking_id={booking_id})",
            }
            headers = {
                "Authorization":    f"Bearer {api_key}",
                "Content-Type":     "application/json",
                "X-Idempotency-Key": _build_idempotency_key(booking_id, external_id),
            }
            _throttle(rate_limit)

            def _do_req() -> AdapterResult:
                resp = httpx.post(url, json=payload, headers=headers, timeout=10)
                if resp.status_code in (200, 201, 204):
                    return AdapterResult(
                        provider=_PROVIDER, external_id=external_id,
                        strategy="api_first", status="ok",
                        http_status=resp.status_code,
                        message=f"Booking.com block sent. HTTP {resp.status_code}.",
                    )
                return AdapterResult(
                    provider=_PROVIDER, external_id=external_id,
                    strategy="api_first", status="failed",
                    http_status=resp.status_code,
                    message=f"Booking.com API error HTTP {resp.status_code}: {resp.text[:200]}",
                )

            return _retry_with_backoff(_do_req)
        except Exception as exc:  # noqa: BLE001
            logger.exception("bookingcom adapter exception: %s", exc)
            return AdapterResult(
                provider=_PROVIDER, external_id=external_id,
                strategy="api_first", status="failed",
                http_status=None,
                message=f"Booking.com adapter exception: {exc}",
            )
