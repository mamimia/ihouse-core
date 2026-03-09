"""
Phase 149 — iCal Push Adapter (RFC 5545 Compliance Audit)

Updated from Phase 143 to include all RFC 5545 REQUIRED fields in the
VCALENDAR and VEVENT components:

  VCALENDAR header:
    CALSCALE:GREGORIAN   (RFC 5545 §3.7.1)
    METHOD:PUBLISH       (RFC 5545 §3.7.2)

  VEVENT:
    DTSTAMP:YYYYMMDDTHHMMSSZ  (UTC, generated at push time) (RFC 5545 §3.8.7.2)
    SEQUENCE:0                (RFC 5545 £3.8.7.4)

See also: Phase 140 (DTSTART/DTEND date injection)
         Phase 143 (X-Idempotency-Key header)

Handles Tier B providers (ical_fallback via push):
  - Hotelbeds
  - TripAdvisor Rentals
  - Despegar

Phase 139: URL is read from env. If absent → dry_run.
Phase 140: DTSTART/DTEND injected from booking_state via fetch_booking_dates().
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

try:
    import httpx  # type: ignore[import]
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from adapters.outbound import AdapterResult, OutboundAdapter, _build_idempotency_key, _retry_with_backoff, _throttle

logger = logging.getLogger(__name__)

_ICAL_TEMPLATE = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//iHouse Core//Phase 149//EN\r\n"
    "CALSCALE:GREGORIAN\r\n"
    "METHOD:PUBLISH\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:{booking_id}@ihouse.core\r\n"
    "DTSTAMP:{dtstamp}\r\n"
    "DTSTART:{dtstart}\r\n"
    "DTEND:{dtend}\r\n"
    "SEQUENCE:0\r\n"
    "SUMMARY:Blocked by iHouse Core\r\n"
    "DESCRIPTION:booking_id={booking_id} external_id={external_id}\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)

# Safe fallback dates used when booking_state lookup returns nothing.
_FALLBACK_DTSTART = "20260101"
_FALLBACK_DTEND   = "20260102"

_PROVIDER_ENV: dict[str, str] = {
    "hotelbeds":   "HOTELBEDS",
    "tripadvisor": "TRIPADVISOR",
    "despegar":    "DESPEGAR",
}


class ICalPushAdapter(OutboundAdapter):
    """
    Outbound adapter for Tier B providers (iCal push).
    Supports: hotelbeds, tripadvisor, despegar.
    """
    def __init__(self, provider: str):
        self.provider = provider   # type: ignore[assignment]

    def push(
        self,
        external_id: str,
        booking_id: str,
        rate_limit: int = 10,
        dry_run: bool = False,
        check_in: Optional[str] = None,   # Phase 140: YYYYMMDD or None
        check_out: Optional[str] = None,  # Phase 140: YYYYMMDD or None
    ) -> AdapterResult:
        env_prefix = _PROVIDER_ENV.get(self.provider, self.provider.upper())
        ical_url   = os.environ.get(f"{env_prefix}_ICAL_URL", "")
        api_key: Optional[str] = os.environ.get(f"{env_prefix}_API_KEY")
        global_dry_run = os.environ.get("IHOUSE_DRY_RUN", "false").lower() == "true"

        if dry_run or global_dry_run or not ical_url:
            reason = (
                "IHOUSE_DRY_RUN=true" if global_dry_run
                else f"{env_prefix}_ICAL_URL not configured — dry-run mode"
                if not ical_url else "dry_run=True requested"
            )
            logger.info(
                "[DRY-RUN] %s ical_fallback: external_id=%s reason=%s",
                self.provider, external_id, reason,
            )
            return AdapterResult(
                provider=self.provider, external_id=external_id,
                strategy="ical_fallback", status="dry_run",
                http_status=None,
                message=f"[Phase 139 dry-run] {self.provider} iCal: {reason}",
            )

        try:
            if httpx is None:  # pragma: no cover
                raise RuntimeError("httpx not available")
            dtstart   = check_in  or _FALLBACK_DTSTART
            dtend     = check_out or _FALLBACK_DTEND
            dtstamp   = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            ical_body = _ICAL_TEMPLATE.format(
                booking_id=booking_id,
                external_id=external_id,
                dtstart=dtstart,
                dtend=dtend,
                dtstamp=dtstamp,
            )
            headers: dict[str, str] = {
                "Content-Type":      "text/calendar; charset=utf-8",
                "X-Idempotency-Key": _build_idempotency_key(booking_id, external_id),
            }
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            full_url = f"{ical_url}/{external_id}.ics"
            _throttle(rate_limit)

            def _do_req() -> AdapterResult:
                resp = httpx.put(full_url, content=ical_body.encode(), headers=headers, timeout=15)
                if resp.status_code in (200, 201, 204):
                    logger.info(
                        "%s ical_fallback OK: external_id=%s status=%d",
                        self.provider, external_id, resp.status_code,
                    )
                    return AdapterResult(
                        provider=self.provider, external_id=external_id,
                        strategy="ical_fallback", status="ok",
                        http_status=resp.status_code,
                        message=f"{self.provider} iCal pushed. HTTP {resp.status_code}.",
                    )
                logger.warning(
                    "%s ical_fallback error: external_id=%s status=%d",
                    self.provider, external_id, resp.status_code,
                )
                return AdapterResult(
                    provider=self.provider, external_id=external_id,
                    strategy="ical_fallback", status="failed",
                    http_status=resp.status_code,
                    message=f"{self.provider} iCal error HTTP {resp.status_code}: {resp.text[:200]}",
                )

            return _retry_with_backoff(_do_req)

        except Exception as exc:  # noqa: BLE001
            logger.exception("%s ical_fallback exception: %s", self.provider, exc)
            return AdapterResult(
                provider=self.provider, external_id=external_id,
                strategy="ical_fallback", status="failed",
                http_status=None,
                message=f"{self.provider} iCal adapter exception: {exc}",
            )
