"""
Phase 140 — Outbound Executor (Service Layer)

Updated in Phase 140 to forward booking check_in/check_out dates to
iCal adapters (ICalPushAdapter.push) so real DTSTART/DTEND are used
in the VCALENDAR payload instead of placeholder dates.

Phase 144: persist every ExecutionResult into the `outbound_sync_log` table
via the best-effort sync_log_writer module.

Previous history:
  Phase 138: stub adapters (dry-run only).
  Phase 139: real API + iCal adapters via registry.
  Phase 140: date injection into iCal push call.
  Phase 141: rate-limit throttle.
  Phase 142: retry with exponential backoff.
  Phase 143: X-Idempotency-Key header on all outbound calls.
  Phase 144: append ExecutionResult rows to outbound_sync_log (this file).

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

    Phase 140: check_in / check_out (YYYYMMDD strings) are forwarded to
    iCal adapters so real DTSTART/DTEND appear in the VCALENDAR payload.
    If None, adapters use safe placeholder dates.
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
