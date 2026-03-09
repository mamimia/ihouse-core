"""
Phase 143 — Airbnb Outbound Adapter (Idempotency Key)

Implements availability locking via the Airbnb Partner API (api_first).

Credentials (from environment):
    AIRBNB_API_KEY     — Partner API key
    AIRBNB_API_BASE    — Base URL (default: https://api.airbnb.com/v2)

Airbnb availability block endpoint (simplified):
    POST /v2/calendar_operations
    Body: {
        "listing_id": "<external_id>",
        "blocked_dates": ["<check_in>", "<check_out>"],
        "notes": "Blocked by iHouse Core (booking_id=<booking_id>)"
    }

Phase 139 sends a well-formed request. If AIRBNB_API_KEY is absent or
IHOUSE_DRY_RUN=true, the adapter returns dry_run status without hitting the API.

Rate limits: 120 requests/min (from provider_capability_registry).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

try:
    import httpx  # type: ignore[import]
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from adapters.outbound import AdapterResult, OutboundAdapter, _build_idempotency_key, _retry_with_backoff, _throttle

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "https://api.airbnb.com/v2"
_PROVIDER     = "airbnb"


class AirbnbAdapter(OutboundAdapter):
    """
    Outbound adapter for Airbnb Partner API (Tier A — api_first).

    Sends a calendar block for the given listing (external_id).
    Returns dry_run if AIRBNB_API_KEY is not configured.
    """
    provider = _PROVIDER

    def send(
        self,
        external_id: str,
        booking_id: str,
        rate_limit: int = 120,
        dry_run: bool = False,
    ) -> AdapterResult:
        api_key  = os.environ.get("AIRBNB_API_KEY", "")
        base_url = os.environ.get("AIRBNB_API_BASE", _DEFAULT_BASE)
        global_dry_run = os.environ.get("IHOUSE_DRY_RUN", "false").lower() == "true"

        if dry_run or global_dry_run or not api_key:
            reason = (
                "IHOUSE_DRY_RUN=true" if global_dry_run
                else "AIRBNB_API_KEY not configured — dry-run mode"
                if not api_key else "dry_run=True requested"
            )
            logger.info(
                "[DRY-RUN] airbnb api_first: external_id=%s booking_id=%s reason=%s",
                external_id, booking_id, reason,
            )
            return AdapterResult(
                provider=_PROVIDER, external_id=external_id,
                strategy="api_first", status="dry_run",
                http_status=None,
                message=f"[Phase 139 dry-run] airbnb: {reason}",
            )

        # Real call
        try:
            if httpx is None:  # pragma: no cover
                raise RuntimeError("httpx not available")
            url = f"{base_url}/calendar_operations"
            payload = {
                "listing_id":    external_id,
                "blocked_dates": ["tbd"],   # Phase 140: inject actual dates from booking
                "notes":         f"Blocked by iHouse Core (booking_id={booking_id})",
            }
            headers = {
                "X-Airbnb-API-Key":    api_key,
                "Content-Type":        "application/json",
                "X-Idempotency-Key":   _build_idempotency_key(booking_id, external_id),
            }
            _throttle(rate_limit)

            def _do_req() -> AdapterResult:
                resp = httpx.post(url, json=payload, headers=headers, timeout=10)
                if resp.status_code in (200, 201, 204):
                    logger.info(
                        "airbnb api_first OK: external_id=%s status=%d",
                        external_id, resp.status_code,
                    )
                    return AdapterResult(
                        provider=_PROVIDER, external_id=external_id,
                        strategy="api_first", status="ok",
                        http_status=resp.status_code,
                        message=f"Airbnb calendar block sent. HTTP {resp.status_code}.",
                    )
                logger.warning(
                    "airbnb api_first error: external_id=%s status=%d body=%s",
                    external_id, resp.status_code, resp.text[:200],
                )
                return AdapterResult(
                    provider=_PROVIDER, external_id=external_id,
                    strategy="api_first", status="failed",
                    http_status=resp.status_code,
                    message=f"Airbnb API error HTTP {resp.status_code}: {resp.text[:200]}",
                )

            return _retry_with_backoff(_do_req)
        except Exception as exc:  # noqa: BLE001
            logger.exception("airbnb api_first exception: external_id=%s: %s", external_id, exc)
            return AdapterResult(
                provider=_PROVIDER, external_id=external_id,
                strategy="api_first", status="failed",
                http_status=None,
                message=f"Airbnb adapter exception: {exc}",
            )
