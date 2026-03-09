"""
Phase 139 — iCal Push Adapter

Handles Tier B providers (ical_fallback via push):
  - Hotelbeds
  - TripAdvisor Rentals
  - Despegar

Each provider has its own iCal push URL and optional API key in env.
The adapter PUTs a minimal iCal payload to the provider's endpoint.

Credentials per provider (from environment):
  HOTELBEDS_ICAL_URL          — push endpoint
  HOTELBEDS_API_KEY           — optional auth header
  TRIPADVISOR_ICAL_URL
  TRIPADVISOR_API_KEY
  DESPEGAR_ICAL_URL
  DESPEGAR_API_KEY

iCal payload for a blocked period (simplified VCALENDAR):
    BEGIN:VCALENDAR
    VERSION:2.0
    PRODID:-//iHouse Core//Phase 139//EN
    BEGIN:VEVENT
    UID:<booking_id>@ihouse.core
    DTSTART:YYYYMMDD
    DTEND:YYYYMMDD
    SUMMARY:Blocked by iHouse Core
    END:VEVENT
    END:VCALENDAR

Phase 139: URL is read from env. If absent → dry_run. Dates are placeholders
(Phase 140 will inject real check-in/check-out from booking).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

try:
    import httpx  # type: ignore[import]
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from adapters.outbound import AdapterResult, OutboundAdapter

logger = logging.getLogger(__name__)

_ICAL_TEMPLATE = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//iHouse Core//Phase 139//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:{booking_id}@ihouse.core\r\n"
    "DTSTART:20260101\r\n"
    "DTEND:20260102\r\n"
    "SUMMARY:Blocked by iHouse Core\r\n"
    "DESCRIPTION:booking_id={booking_id} external_id={external_id}\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)

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
            ical_body = _ICAL_TEMPLATE.format(
                booking_id=booking_id,
                external_id=external_id,
            )
            headers: dict[str, str] = {"Content-Type": "text/calendar; charset=utf-8"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            full_url = f"{ical_url}/{external_id}.ics"
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

        except Exception as exc:  # noqa: BLE001
            logger.exception("%s ical_fallback exception: %s", self.provider, exc)
            return AdapterResult(
                provider=self.provider, external_id=external_id,
                strategy="ical_fallback", status="failed",
                http_status=None,
                message=f"{self.provider} iCal adapter exception: {exc}",
            )
