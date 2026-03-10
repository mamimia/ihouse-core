"""
Phase 150 — iCal Push Adapter (VTIMEZONE Support)

Extends Phase 149 RFC 5545 compliance with timezone-aware output.

When `timezone` is provided (e.g. "Asia/Bangkok", "America/New_York"):
  - VTIMEZONE component emitted before VEVENT (RFC 5545 §3.6.5)
  - DTSTART and DTEND use TZID-qualified format:
      DTSTART;TZID=Asia/Bangkok:20260115T000000
      DTEND;TZID=Asia/Bangkok:20260116T000000
  - Note: TZID value is the IANA tz identifier (Region/City)

When `timezone` is absent or None:
  - Existing UTC behaviour unchanged (safe, backward-compatible)
  - DTSTART/DTEND remain in YYYYMMDD format

VTIMEZONE block uses floating-time DTSTART (no Z suffix) per RFC 5545 §3.6.5.
STANDARD sub-component only — DST omitted for simplicity (TZOFFSETTO=+0000 placeholder).
The TZID in VTIMEZONE MUST match the TZID in DTSTART/DTEND.

See also:
  Phase 140 — DTSTART/DTEND date injection
  Phase 143 — X-Idempotency-Key header
  Phase 149 — CALSCALE, METHOD, DTSTAMP, SEQUENCE:0

Handles Tier B providers (ical_fallback via push):
  - Hotelbeds
  - TripAdvisor Rentals
  - Despegar
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from datetime import timezone as _tz_module
from typing import Optional

UTC = _tz_module.utc

try:
    import httpx  # type: ignore[import]
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

from adapters.outbound import AdapterResult, OutboundAdapter, _build_idempotency_key, _retry_with_backoff, _throttle

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# iCal templates
# ---------------------------------------------------------------------------

# UTC template (Phase 149 baseline). DTSTART/DTEND as bare dates (YYYYMMDD).
_ICAL_TEMPLATE_UTC = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//iHouse Core//Phase 150//EN\r\n"
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

# VTIMEZONE template (Phase 150). Emitted when timezone is known.
# TZID placeholder must appear identically in DTSTART;TZID=... lines.
_VTIMEZONE_BLOCK = (
    "BEGIN:VTIMEZONE\r\n"
    "TZID:{tzid}\r\n"
    "BEGIN:STANDARD\r\n"
    "DTSTART:19700101T000000\r\n"
    "TZOFFSETFROM:+0000\r\n"
    "TZOFFSETTO:+0000\r\n"
    "END:STANDARD\r\n"
    "END:VTIMEZONE\r\n"
)

# TZID-qualified template (Phase 150). DTSTART/DTEND carry ;TZID= parameter.
_ICAL_TEMPLATE_TZID = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//iHouse Core//Phase 150//EN\r\n"
    "CALSCALE:GREGORIAN\r\n"
    "METHOD:PUBLISH\r\n"
    "{vtimezone}"
    "BEGIN:VEVENT\r\n"
    "UID:{booking_id}@ihouse.core\r\n"
    "DTSTAMP:{dtstamp}\r\n"
    "DTSTART;TZID={tzid}:{dtstart}T000000\r\n"
    "DTEND;TZID={tzid}:{dtend}T000000\r\n"
    "SEQUENCE:0\r\n"
    "SUMMARY:Blocked by iHouse Core\r\n"
    "DESCRIPTION:booking_id={booking_id} external_id={external_id}\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)

# Backward-compat alias: Phase 149 tests import _ICAL_TEMPLATE by name.
# Always points to the UTC template (timezone-unaware path).
_ICAL_TEMPLATE = _ICAL_TEMPLATE_UTC

# Safe fallback dates used when booking_state lookup returns nothing.
_FALLBACK_DTSTART = "20260101"
_FALLBACK_DTEND   = "20260102"

_PROVIDER_ENV: dict[str, str] = {
    "hotelbeds":   "HOTELBEDS",
    "tripadvisor": "TRIPADVISOR",
    "despegar":    "DESPEGAR",
}


def _build_ical_body(
    *,
    booking_id: str,
    external_id: str,
    dtstart: str,
    dtend: str,
    dtstamp: str,
    timezone_id: Optional[str],
) -> str:
    """
    Build the iCal body string.

    When timezone_id is provided: uses VTIMEZONE block + TZID-qualified dates.
    When timezone_id is None/empty: uses plain UTC format (backward-compatible).
    """
    if timezone_id:
        vtimezone_block = _VTIMEZONE_BLOCK.format(tzid=timezone_id)
        return _ICAL_TEMPLATE_TZID.format(
            booking_id=booking_id,
            external_id=external_id,
            dtstart=dtstart,
            dtend=dtend,
            dtstamp=dtstamp,
            tzid=timezone_id,
            vtimezone=vtimezone_block,
        )
    return _ICAL_TEMPLATE_UTC.format(
        booking_id=booking_id,
        external_id=external_id,
        dtstart=dtstart,
        dtend=dtend,
        dtstamp=dtstamp,
    )


class ICalPushAdapter(OutboundAdapter):
    """
    Outbound adapter for Tier B providers (iCal push).
    Supports: hotelbeds, tripadvisor, despegar.

    Phase 150: accepts optional `timezone` parameter.
    When provided, VTIMEZONE block + TZID-qualified DTSTART/DTEND are emitted.
    When absent, UTC behaviour is unchanged.
    """
    def __init__(self, provider: str):
        self.provider = provider   # type: ignore[assignment]

    def push(
        self,
        external_id: str,
        booking_id: str,
        rate_limit: int = 10,
        dry_run: bool = False,
        check_in: Optional[str] = None,    # Phase 140: YYYYMMDD or None
        check_out: Optional[str] = None,   # Phase 140: YYYYMMDD or None
        timezone: Optional[str] = None,    # Phase 150: IANA tz id or None
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

            dtstart  = check_in  or _FALLBACK_DTSTART
            dtend    = check_out or _FALLBACK_DTEND
            dtstamp  = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
            ical_body = _build_ical_body(
                booking_id=booking_id,
                external_id=external_id,
                dtstart=dtstart,
                dtend=dtend,
                dtstamp=dtstamp,
                timezone_id=timezone,
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

    def cancel(
        self,
        external_id: str,
        booking_id: str,
        rate_limit: int = 10,
        dry_run: bool = False,
    ) -> AdapterResult:
        """
        Phase 151 — iCal Cancellation Push.

        Sends a VCALENDAR payload with STATUS:CANCELLED for the given booking.
        Per RFC 5545 §3.8.1.11 — VEVENT STATUS:CANCELLED signals the booking
        has been cancelled and providers should remove the blocked period.

        Shares rate-limit (Phase 141), retry (Phase 142), and idempotency-key
        (Phase 143) infrastructure with push(). Method is best-effort: errors are
        logged but never re-raised to the caller.

        Dry-run behaviour:
          - dry_run=True → log + return dry_run immediately, no HTTP call.
          - IHOUSE_DRY_RUN=true env var → same.
          - Missing ICAL_URL env → treated as dry_run.
        """
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
                "[DRY-RUN] %s ical_cancel: external_id=%s reason=%s",
                self.provider, external_id, reason,
            )
            return AdapterResult(
                provider=self.provider, external_id=external_id,
                strategy="ical_fallback", status="dry_run",
                http_status=None,
                message=f"[Phase 151 dry-run] {self.provider} iCal cancel: {reason}",
            )

        try:
            if httpx is None:  # pragma: no cover
                raise RuntimeError("httpx not available")

            dtstamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
            cancel_body = (
                "BEGIN:VCALENDAR\r\n"
                "VERSION:2.0\r\n"
                "PRODID:-//iHouse Core//Phase 151//EN\r\n"
                "CALSCALE:GREGORIAN\r\n"
                "METHOD:CANCEL\r\n"
                "BEGIN:VEVENT\r\n"
                f"UID:{booking_id}@ihouse.core\r\n"
                f"DTSTAMP:{dtstamp}\r\n"
                "SEQUENCE:1\r\n"
                "STATUS:CANCELLED\r\n"
                f"SUMMARY:CANCELLED by iHouse Core\r\n"
                f"DESCRIPTION:booking_id={booking_id} external_id={external_id}\r\n"
                "END:VEVENT\r\n"
                "END:VCALENDAR\r\n"
            )

            headers: dict[str, str] = {
                "Content-Type":      "text/calendar; charset=utf-8",
                "X-Idempotency-Key": _build_idempotency_key(booking_id, external_id),
            }
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            full_url = f"{ical_url}/{external_id}.ics"
            _throttle(rate_limit)

            def _do_cancel() -> AdapterResult:
                resp = httpx.put(full_url, content=cancel_body.encode(), headers=headers, timeout=15)
                if resp.status_code in (200, 201, 204):
                    logger.info(
                        "%s ical_cancel OK: external_id=%s status=%d",
                        self.provider, external_id, resp.status_code,
                    )
                    return AdapterResult(
                        provider=self.provider, external_id=external_id,
                        strategy="ical_fallback", status="ok",
                        http_status=resp.status_code,
                        message=f"{self.provider} iCal cancel pushed. HTTP {resp.status_code}.",
                    )
                logger.warning(
                    "%s ical_cancel error: external_id=%s status=%d",
                    self.provider, external_id, resp.status_code,
                )
                return AdapterResult(
                    provider=self.provider, external_id=external_id,
                    strategy="ical_fallback", status="failed",
                    http_status=resp.status_code,
                    message=f"{self.provider} iCal cancel error HTTP {resp.status_code}: {resp.text[:200]}",
                )

            return _retry_with_backoff(_do_cancel)

        except Exception as exc:  # noqa: BLE001
            logger.exception("%s ical_cancel exception: %s", self.provider, exc)
            return AdapterResult(
                provider=self.provider, external_id=external_id,
                strategy="ical_fallback", status="failed",
                http_status=None,
                message=f"{self.provider} iCal cancel exception: {exc}",
            )

