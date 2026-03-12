"""
Phase 140 — Outbound Executor (Service Layer)

Updated in Phase 140 to forward booking check_in/check_out dates to
iCal adapters (ICalPushAdapter.push) so real DTSTART/DTEND are used
in the VCALENDAR payload instead of placeholder dates.

Phase 144: persist every ExecutionResult into the `outbound_sync_log` table
via the best-effort sync_log_writer module.

Phase 148: fire best-effort webhook callback to IHOUSE_SYNC_CALLBACK_URL
after every 'ok' result. Noop when env var absent. Callback failure is
never retried and never blocks the sync path.

Previous history:
  Phase 138: stub adapters (dry-run only).
  Phase 139: real API + iCal adapters via registry.
  Phase 140: date injection into iCal push call.
  Phase 141: rate-limit throttle.
  Phase 142: retry with exponential backoff.
  Phase 143: X-Idempotency-Key header on all outbound calls.
  Phase 144: append ExecutionResult rows to outbound_sync_log (this file).
  Phase 148: best-effort webhook callback after ok results.

Updated in Phase 139 to use real adapter implementations:
  api_first:    AirbnbAdapter, BookingComAdapter, ExpediaVrboAdapter
  ical_fallback: ICalPushAdapter (Hotelbeds, TripAdvisor, Despegar)

Strategy resolution is unchanged from Phase 138.
The Phase 138 stub adapters (ApiFirstAdapter, ICalAdapter) are kept as
fallback for unknown providers not in the adapter registry.

Adapter registry: adapters/outbound/registry.py → build_adapter_registry()

Invariants:
  - Adapters fall back to dry_run if credentials absent.
  - apply_envelope is never called.
  - Fail-isolated: one failure does not prevent other actions.
  - Skipped actions are echoed in results with status='skipped'.
"""
from __future__ import annotations

import logging
import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.outbound_sync_trigger import SyncAction

# Phase 139 — real adapter registry
try:
    from adapters.outbound.registry import build_adapter_registry as _build_registry
    _ADAPTER_REGISTRY_AVAILABLE = True
except ImportError:
    _ADAPTER_REGISTRY_AVAILABLE = False

# Phase 144 — best-effort sync result persistence
try:
    from services.sync_log_writer import write_sync_result as _write_sync_result
    _SYNC_LOG_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SYNC_LOG_AVAILABLE = False
    def _write_sync_result(**_kw) -> bool:  # type: ignore[misc]
        return True

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phase 148 — webhook callback configuration
# ---------------------------------------------------------------------------

_CALLBACK_URL: Optional[str] = os.environ.get("IHOUSE_SYNC_CALLBACK_URL") or None


def _fire_callback(
    booking_id:  str,
    tenant_id:   str,
    result:      Any,
    *,
    callback_url: Optional[str] = None,
) -> None:
    """
    Phase 148: Best-effort HTTP POST to `IHOUSE_SYNC_CALLBACK_URL` (or the
    injected `callback_url` override used in tests).

    Sends a JSON body:
      {
        "event":      "sync.ok",
        "booking_id": ...,
        "tenant_id":  ...,
        "provider":   ...,
        "external_id": ...,
        "strategy":   ...,
        "http_status": ...
      }

    Rules:
      - Only fires when `result.status == 'ok'`.
      - Noop if no URL is configured (env or override absent).
      - Uses a 5-second connect + read timeout.
      - Any exception is caught, logged as WARNING, and swallowed —
        callback failure NEVER raises and NEVER blocks the sync path.
      - Never retried.
    """
    url = callback_url if callback_url is not None else _CALLBACK_URL
    if not url:
        return  # not configured — noop

    if result.status != "ok":
        return  # only fire on successful syncs

    payload = json.dumps({
        "event":       "sync.ok",
        "booking_id":  booking_id,
        "tenant_id":   tenant_id,
        "provider":    result.provider,
        "external_id": result.external_id,
        "strategy":    result.strategy,
        "http_status": result.http_status,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            logger.debug(
                "_fire_callback: callback ok status=%d booking=%s provider=%s",
                resp.status, booking_id, result.provider,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_fire_callback: callback failed (best-effort, swallowed) "
            "booking=%s provider=%s url=%s: %s",
            booking_id, result.provider, url, exc,
        )


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    provider:     str
    external_id:  str
    strategy:     str
    status:       str          # ok | failed | skipped | dry_run
    http_status:  Optional[int]
    message:      str


@dataclass
class ExecutionReport:
    booking_id:    str
    property_id:   str
    tenant_id:     str
    total_actions: int
    ok_count:      int
    failed_count:  int
    skip_count:    int
    dry_run:       bool
    results:       List[ExecutionResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stub adapters (Phase 138 — dry-run only, real calls in Phase 139+)
# ---------------------------------------------------------------------------

class ApiFirstAdapter:
    """
    Stub for Tier A/B providers that support write APIs.
    Will be replaced with real HTTP clients in Phase 139.
    """
    @staticmethod
    def send(
        provider: str,
        external_id: str,
        booking_id: str,
        rate_limit: int,
    ) -> ExecutionResult:
        logger.info(
            "[DRY-RUN] api_first: provider=%s external_id=%s booking_id=%s rate_limit=%d/min",
            provider, external_id, booking_id, rate_limit,
        )
        return ExecutionResult(
            provider=provider,
            external_id=external_id,
            strategy="api_first",
            status="dry_run",
            http_status=None,
            message=(
                f"[Phase 138 stub] api_first dispatched for provider={provider}, "
                f"external_id={external_id}. Real API call deferred to Phase 139."
            ),
        )


class ICalAdapter:
    """
    Stub for Tier B/C providers that use iCal feed.
    Will be replaced with real iCal push in Phase 139.
    """
    @staticmethod
    def push(
        provider: str,
        external_id: str,
        booking_id: str,
        rate_limit: int,
    ) -> ExecutionResult:
        logger.info(
            "[DRY-RUN] ical_fallback: provider=%s external_id=%s booking_id=%s",
            provider, external_id, booking_id,
        )
        return ExecutionResult(
            provider=provider,
            external_id=external_id,
            strategy="ical_fallback",
            status="dry_run",
            http_status=None,
            message=(
                f"[Phase 138 stub] ical_fallback dispatched for provider={provider}, "
                f"external_id={external_id}. Real iCal push deferred to Phase 139."
            ),
        )


# ---------------------------------------------------------------------------
# Phase 144 — persistence helper
# ---------------------------------------------------------------------------

def _persist(booking_id: str, tenant_id: str, result: ExecutionResult) -> None:
    """Best-effort write of one ExecutionResult row to outbound_sync_log."""
    if not _SYNC_LOG_AVAILABLE:
        return
    try:
        _write_sync_result(
            booking_id=booking_id,
            tenant_id=tenant_id,
            provider=result.provider,
            external_id=result.external_id,
            strategy=result.strategy,
            status=result.status,
            http_status=result.http_status,
            message=result.message,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_persist: sync_log_writer raised (best-effort, swallowed): "
            "booking_id=%s provider=%s: %s",
            booking_id, result.provider, exc,
        )


# ---------------------------------------------------------------------------
# Main executor
# ---------------------------------------------------------------------------

def execute_sync_plan(
    booking_id: str,
    property_id: str,
    tenant_id: str,
    actions: List[SyncAction],
    api_adapter: Optional[Any] = None,
    ical_adapter: Optional[Any] = None,
    check_in: Optional[str] = None,   # Phase 140: YYYYMMDD from booking_state
    check_out: Optional[str] = None,  # Phase 140: YYYYMMDD from booking_state
    event_type: str = "BOOKING_CREATED",  # Phase 185: route cancel/amend correctly
) -> ExecutionReport:
    """
    Execute a sync plan produced by build_sync_plan() (Phase 137).

    Parameters
    ----------
    booking_id   : str
    property_id  : str
    tenant_id    : str
    actions      : list of SyncAction from build_sync_plan()
    api_adapter  : override for testing (defaults to ApiFirstAdapter)
    ical_adapter : override for testing (defaults to ICalAdapter)
    check_in     : YYYYMMDD — forwarded to iCal adapters (Phase 140)
    check_out    : YYYYMMDD — forwarded to iCal adapters (Phase 140)
    event_type   : lifecycle event type — BOOKING_CREATED | BOOKING_CANCELED |
                   BOOKING_AMENDED. Used to route to the correct adapter method:
                     api_first   → .send() | .cancel() | .amend()
                     ical_fallback → .push() | .cancel()
                   Default: BOOKING_CREATED (backward compatible).
    """
    # Phase 139: prefer real adapter registry; fall back to class-level stubs
    # for backward compatibility with Phase 138 tests.
    use_registry = _ADAPTER_REGISTRY_AVAILABLE and api_adapter is None and ical_adapter is None
    _api_cls  = api_adapter  or ApiFirstAdapter
    _ical_cls = ical_adapter or ICalAdapter

    results: List[ExecutionResult] = []
    ok_count      = 0
    failed_count  = 0
    skip_count    = 0

    for action in actions:
        if action.strategy == "skip":
            results.append(ExecutionResult(
                provider=action.provider,
                external_id=action.external_id,
                strategy="skip",
                status="skipped",
                http_status=None,
                message=f"Skipped by sync trigger: {action.reason}",
            ))
            skip_count += 1
            continue

        try:
            if action.strategy == "api_first":
                if use_registry:
                    adapter = _build_registry().get(action.provider)
                    if adapter is not None:
                        # Phase 185/358: route to the correct method based on event_type
                        # cancel() and amend() are now defined on OutboundAdapter base (Phase 358).
                        if event_type == "BOOKING_CANCELED":
                            ar = adapter.cancel(
                                external_id=action.external_id,
                                booking_id=booking_id,
                                rate_limit=action.rate_limit,
                            )
                        elif event_type == "BOOKING_AMENDED":
                            # Normalise check_in/check_out to ISO for API adapters
                            def _to_iso(d: Optional[str]) -> Optional[str]:
                                if not d:
                                    return None
                                s = str(d).replace("-", "")[:8]
                                return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 else d
                            ar = adapter.amend(
                                external_id=action.external_id,
                                booking_id=booking_id,
                                check_in=_to_iso(check_in),
                                check_out=_to_iso(check_out),
                                rate_limit=action.rate_limit,
                            )
                        else:
                            ar = adapter.send(
                                external_id=action.external_id,
                                booking_id=booking_id,
                                rate_limit=action.rate_limit,
                            )
                        result = ExecutionResult(
                            provider=ar.provider,
                            external_id=ar.external_id,
                            strategy=ar.strategy,
                            status=ar.status,
                            http_status=ar.http_status,
                            message=ar.message,
                        )
                    else:
                        # Unknown provider — fall back to stub
                        result = _api_cls.send(
                            provider=action.provider,
                            external_id=action.external_id,
                            booking_id=booking_id,
                            rate_limit=action.rate_limit,
                        )
                else:
                    result = _api_cls.send(
                        provider=action.provider,
                        external_id=action.external_id,
                        booking_id=booking_id,
                        rate_limit=action.rate_limit,
                    )
            elif action.strategy == "ical_fallback":
                if use_registry:
                    adapter = _build_registry().get(action.provider)
                    if adapter is not None:
                        # Phase 185/358: route to cancel() for BOOKING_CANCELED
                        # amend via iCal uses push() with updated dates.
                        if event_type == "BOOKING_CANCELED":
                            ar = adapter.cancel(
                                external_id=action.external_id,
                                booking_id=booking_id,
                                rate_limit=action.rate_limit,
                            )
                        else:
                            ar = adapter.push(
                                external_id=action.external_id,
                                booking_id=booking_id,
                                rate_limit=action.rate_limit,
                                check_in=check_in,    # Phase 140
                                check_out=check_out,  # Phase 140
                            )
                        result = ExecutionResult(
                            provider=ar.provider,
                            external_id=ar.external_id,
                            strategy=ar.strategy,
                            status=ar.status,
                            http_status=ar.http_status,
                            message=ar.message,
                        )
                    else:
                        result = _ical_cls.push(
                            provider=action.provider,
                            external_id=action.external_id,
                            booking_id=booking_id,
                            rate_limit=action.rate_limit,
                        )
                else:
                    result = _ical_cls.push(
                        provider=action.provider,
                        external_id=action.external_id,
                        booking_id=booking_id,
                        rate_limit=action.rate_limit,
                    )
            else:
                result = ExecutionResult(
                    provider=action.provider,
                    external_id=action.external_id,
                    strategy=action.strategy,
                    status="skipped",
                    http_status=None,
                    message=f"Unknown strategy '{action.strategy}' — skipped for safety.",
                )
                skip_count += 1
                results.append(result)
                continue

            # dry_run counts as ok for Phase 138
            if result.status in ("ok", "dry_run"):
                ok_count += 1
            elif result.status == "failed":
                failed_count += 1
            else:
                skip_count += 1

            results.append(result)
            _persist(booking_id, tenant_id, result)
            # Phase 148: best-effort webhook callback for ok syncs
            _fire_callback(booking_id, tenant_id, result)

        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Executor error for provider=%s booking=%s: %s",
                action.provider, booking_id, exc,
            )
            results.append(ExecutionResult(
                provider=action.provider,
                external_id=action.external_id,
                strategy=action.strategy,
                status="failed",
                http_status=None,
                message=f"Executor exception: {exc}",
            ))
            _persist(booking_id, tenant_id, results[-1])
            failed_count += 1

    # Is this a dry-run execution? True if ALL non-skip results are dry_run.
    non_skip = [r for r in results if r.status != "skipped"]
    is_dry_run = bool(non_skip) and all(r.status == "dry_run" for r in non_skip)

    return ExecutionReport(
        booking_id=booking_id,
        property_id=property_id,
        tenant_id=tenant_id,
        total_actions=len(actions),
        ok_count=ok_count,
        failed_count=failed_count,
        skip_count=skip_count,
        dry_run=is_dry_run,
        results=results,
    )


def serialise_report(report: ExecutionReport) -> Dict[str, Any]:
    """JSON-serialisable form of ExecutionReport for the API response."""
    return {
        "booking_id":    report.booking_id,
        "property_id":   report.property_id,
        "tenant_id":     report.tenant_id,
        "total_actions": report.total_actions,
        "ok_count":      report.ok_count,
        "failed_count":  report.failed_count,
        "skip_count":    report.skip_count,
        "dry_run":       report.dry_run,
        "results": [
            {
                "provider":    r.provider,
                "external_id": r.external_id,
                "strategy":    r.strategy,
                "status":      r.status,
                "http_status": r.http_status,
                "message":     r.message,
            }
            for r in report.results
        ],
    }


# ---------------------------------------------------------------------------
# Phase 147 — single-provider replay
# ---------------------------------------------------------------------------

def execute_single_provider(
    booking_id:   str,
    property_id:  str,
    tenant_id:    str,
    provider:     str,
    external_id:  str,
    strategy:     str,          # "api_first" | "ical_fallback"
    rate_limit:   int = 60,
    check_in:     Optional[str] = None,
    check_out:    Optional[str] = None,
    api_adapter:  Optional[Any] = None,
    ical_adapter: Optional[Any] = None,
) -> ExecutionReport:
    """
    Phase 147: Re-execute a single provider through the full fail-isolated
    executor path (throttle, retry, idempotency key, persistence).

    Constructs a single SyncAction and delegates to execute_sync_plan()
    so all Phase 141-144 guarantees apply:
      - Rate-limit throttle (IHOUSE_THROTTLE_DISABLED opt-out)
      - Exponential backoff retry (IHOUSE_RETRY_DISABLED opt-out)
      - X-Idempotency-Key header attachment
      - Best-effort sync_log_writer persistence
      - Dry-run fallback when credentials absent
      - Exception isolation (never raises)

    Parameters
    ----------
    booking_id   : str
    property_id  : str
    tenant_id    : str
    provider     : str    — OTA provider name (e.g. 'airbnb')
    external_id  : str    — booking reference on the OTA side
    strategy     : str    — 'api_first' | 'ical_fallback'
    rate_limit   : int    — calls per minute (default 60)
    check_in     : str    — YYYYMMDD, forwarded to iCal adapter
    check_out    : str    — YYYYMMDD, forwarded to iCal adapter
    api_adapter  : Any    — injectable for testing
    ical_adapter : Any    — injectable for testing

    Returns
    -------
    ExecutionReport with a single result entry.
    """
    action = SyncAction(
        booking_id=booking_id,
        property_id=property_id,
        provider=provider,
        external_id=external_id,
        strategy=strategy,
        reason="replay",
        tier=None,           # not stored in sync log; no tier enforcement on replay
        rate_limit=rate_limit,
    )
    return execute_sync_plan(
        booking_id=booking_id,
        property_id=property_id,
        tenant_id=tenant_id,
        actions=[action],
        api_adapter=api_adapter,
        ical_adapter=ical_adapter,
        check_in=check_in,
        check_out=check_out,
    )

