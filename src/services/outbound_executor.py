"""
Phase 138 — Outbound Executor (Service Layer)

Receives the output of Phase 137's build_sync_plan() and dispatches each
non-skip SyncAction to the appropriate outbound adapter.

Design decisions:
  - Phase 138 is an **executor**, not a scheduler. It runs synchronously within
    the request — each action is attempted in turn.
  - Phase 138 ships with **stubbed adapters** — they log the intent and return
    a deterministic success/dry-run result. Real API calls come in Phase 139+.
  - The execution result for every action is recorded in ExecutionResult,
    regardless of success or failure.
  - If one action fails, the others still run (fail-isolated dispatch).

ExecutionResult schema (per action):
    provider     TEXT
    external_id  TEXT
    strategy     TEXT  (api_first | ical_fallback | skip)
    status       TEXT  (ok | failed | skipped | dry_run)
    http_status  INT?  (from OTA API, if applicable)
    message      TEXT  (human explanation)

ExecutionReport schema (full report):
    booking_id      TEXT
    property_id     TEXT
    tenant_id       TEXT
    total_actions   INT
    ok_count        INT
    failed_count    INT
    skip_count      INT
    dry_run         BOOL
    results         List[ExecutionResult]

Adapter registry (stubbed for Phase 138):
    api_first   → ApiFirstAdapter.send(provider, external_id, booking_id)
    ical_fallback → ICalAdapter.push(provider, external_id, booking_id)

Invariants:
    - Adapters in Phase 138 are stubs that return dry_run=True.
    - apply_envelope is never called.
    - Only processes actions with strategy != 'skip'.
    - Skipped actions are echoed in results with status='skipped'.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.outbound_sync_trigger import SyncAction

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
# Main executor
# ---------------------------------------------------------------------------

def execute_sync_plan(
    booking_id: str,
    property_id: str,
    tenant_id: str,
    actions: List[SyncAction],
    api_adapter: Optional[Any] = None,
    ical_adapter: Optional[Any] = None,
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

    Returns
    -------
    ExecutionReport with per-action results.
    """
    _api  = api_adapter  or ApiFirstAdapter
    _ical = ical_adapter or ICalAdapter

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
                result = _api.send(
                    provider=action.provider,
                    external_id=action.external_id,
                    booking_id=booking_id,
                    rate_limit=action.rate_limit,
                )
            elif action.strategy == "ical_fallback":
                result = _ical.push(
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
