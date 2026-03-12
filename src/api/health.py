"""
Enhanced Health Check — Phase 64
Outbound Sync Probes  — Phase 172
==================================

Provides health_check() — used by GET /health in src/main.py.

Checks:
1. Supabase connectivity — SELECT 1 query against SUPABASE_URL/rest/v1/
2. DLQ row count — number of unprocessed ota_dead_letter rows
3. Outbound sync probes (Phase 172) — per provider:
   - last_sync_at        — most recent outbound_sync_log entry
   - failure_rate_7d     — fraction of syncs that failed in last 7 days
   - log_lag_seconds     — seconds since last outbound sync event

Response semantics (SaaS standard):
    200  status=ok         — all checks passed
    200  status=degraded   — at least one check slow / partial (still serving)
    503  status=unhealthy  — Supabase unreachable

DLQ count is informational — a non-zero count sets status=degraded, not 503.
Outbound probe errors set status=degraded, never 503.

Environment variables:
    SUPABASE_URL        — Supabase project URL
    SUPABASE_KEY        — Supabase anon key (read-only, safe for health check)
    HEALTH_DB_TIMEOUT   — seconds for DB ping (default 3.0)
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 3.0
_DLQ_TABLE = "ota_dead_letter"
_BOOT_TIME = time.monotonic()


@dataclass
class HealthResult:
    status: str          # "ok" | "degraded" | "unhealthy"
    version: str
    env: str
    checks: Dict[str, Any] = field(default_factory=dict)
    http_status: int = 200


def _supabase_headers() -> dict[str, str]:
    key = os.environ.get("SUPABASE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _supabase_url() -> str:
    return os.environ.get("SUPABASE_URL", "").rstrip("/")


def run_health_checks(version: str, env: str) -> HealthResult:
    """
    Runs all health checks and returns a HealthResult.
    Non-raising — all errors are caught and surfaced as check failures.
    """
    t_start = time.monotonic()
    checks: Dict[str, Any] = {}
    overall = "ok"
    http_status = 200

    base_url = _supabase_url()

    # ------------------------------------------------------------------ #
    # Check 1: Supabase connectivity ping                                 #
    # ------------------------------------------------------------------ #
    if not base_url:
        checks["supabase"] = {"status": "skipped", "reason": "SUPABASE_URL not set"}
    else:
        try:
            import urllib.request
            import urllib.error

            ping_url = f"{base_url}/rest/v1/?apikey={os.environ.get('SUPABASE_KEY', '')}"
            timeout = float(os.environ.get("HEALTH_DB_TIMEOUT", _DEFAULT_TIMEOUT))
            t0 = time.monotonic()
            req = urllib.request.Request(ping_url, headers=_supabase_headers())
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                latency_ms = int((time.monotonic() - t0) * 1000)
                checks["supabase"] = {
                    "status": "ok",
                    "latency_ms": latency_ms,
                    "http": resp.status,
                }
        except Exception as exc:
            logger.warning("Health check: Supabase ping failed: %s", exc)
            checks["supabase"] = {"status": "unreachable", "error": str(exc)[:120]}
            overall = "unhealthy"
            http_status = 503

    # ------------------------------------------------------------------ #
    # Check 2: DLQ count                                                  #
    # ------------------------------------------------------------------ #
    if not base_url:
        checks["dlq"] = {"status": "skipped", "reason": "SUPABASE_URL not set"}
    elif overall == "unhealthy":
        checks["dlq"] = {"status": "skipped", "reason": "supabase unreachable"}
    else:
        try:
            import urllib.request
            import urllib.error
            import json

            dlq_url = (
                f"{base_url}/rest/v1/{_DLQ_TABLE}"
                f"?select=id&replayed_at=is.null&limit=1000"
            )
            timeout = float(os.environ.get("HEALTH_DB_TIMEOUT", _DEFAULT_TIMEOUT))
            req = urllib.request.Request(dlq_url, headers={
                **_supabase_headers(),
                "Prefer": "count=exact",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                count_header = resp.headers.get("Content-Range", "")
                # Content-Range: 0-999/42  →  total = 42
                total = 0
                if "/" in count_header:
                    try:
                        total = int(count_header.split("/")[-1])
                    except ValueError:
                        pass
                checks["dlq"] = {"status": "ok", "unprocessed_count": total}
                if total > 0 and overall == "ok":
                    overall = "degraded"
        except Exception as exc:
            logger.warning("Health check: DLQ count failed: %s", exc)
            checks["dlq"] = {"status": "error", "error": str(exc)[:120]}
            if overall == "ok":
                overall = "degraded"

    # ------------------------------------------------------------------ #
    # Phase 368: Rate limiter stats + uptime                              #
    # ------------------------------------------------------------------ #
    try:
        from api.rate_limiter import _limiter  # noqa: PLC0415
        stats = _limiter.stats()
        checks["rate_limiter"] = {
            "status": "ok",
            "limit_rpm": stats["limit_rpm"],
            "active_tenants": stats["active_tenants"],
        }
    except Exception:
        checks["rate_limiter"] = {"status": "skipped", "reason": "not available"}

    uptime_seconds = int(time.monotonic() - _BOOT_TIME)
    checks["uptime_seconds"] = uptime_seconds
    checks["response_time_ms"] = int((time.monotonic() - t_start) * 1000)

    return HealthResult(
        status=overall,
        version=version,
        env=env,
        checks=checks,
        http_status=http_status,
    )


# ---------------------------------------------------------------------------
# Phase 172 — Outbound Sync Probes
# ---------------------------------------------------------------------------

# Failure rate threshold that triggers degraded status
_DEGRADED_FAILURE_RATE = 0.2   # 20%
# Log lag threshold (seconds) that triggers degraded status
_DEGRADED_LAG_SECONDS = 3600   # 1 hour


@dataclass
class OutboundSyncProbeResult:
    """
    Result of an outbound sync health probe for a single provider.

    Args:
        provider:         Provider name.
        last_sync_at:     ISO timestamp of the most recent sync log entry, or None.
        failure_rate_7d:  Fraction of syncs that failed in the last 7 days (0.0–1.0),
                          or None if insufficient data.
        log_lag_seconds:  Seconds since the last sync log entry, or None if no data.
        status:           'ok' | 'degraded' | 'idle' | 'error'
    """
    provider: str
    last_sync_at: Optional[str]
    failure_rate_7d: Optional[float]
    log_lag_seconds: Optional[float]
    status: str   # 'ok' | 'degraded' | 'idle' | 'error'


def probe_outbound_sync(
    client: Any,
    providers: Optional[List[str]] = None,
    now: Optional[datetime] = None,
) -> List[OutboundSyncProbeResult]:
    """
    Run outbound sync health probes for each provider.

    Reads from `outbound_sync_log` table (Phase 145+).
    Best-effort: returns provider status='error' on any DB failure.

    Status derivation per provider:
        idle     — no log entries at all
        degraded — failure_rate_7d > 20% OR log_lag_seconds > 3600
        ok       — otherwise
        error    — DB read failed

    Args:
        client:    Supabase client.
        providers: List of provider names to probe. Defaults to _DEFAULT_PROVIDERS.
        now:       Override current time (for testing).

    Returns:
        List of OutboundSyncProbeResult, one per provider.
    """
    effective_providers = providers or _DEFAULT_PROVIDERS
    effective_now = now or datetime.now(tz=timezone.utc)
    cutoff_7d = (effective_now - timedelta(days=7)).isoformat()

    results: List[OutboundSyncProbeResult] = []

    for provider in effective_providers:
        try:
            # Last sync entry (any status)
            last_res = (
                client.table("outbound_sync_log")
                .select("synced_at, status")
                .eq("provider", provider)
                .order("synced_at", desc=True)
                .limit(1)
                .execute()
            )
            last_rows = last_res.data or []

            if not last_rows:
                results.append(OutboundSyncProbeResult(
                    provider=provider,
                    last_sync_at=None,
                    failure_rate_7d=None,
                    log_lag_seconds=None,
                    status="idle",
                ))
                continue

            last_sync_at_str: str = last_rows[0]["synced_at"]

            # Compute lag
            try:
                last_dt = datetime.fromisoformat(last_sync_at_str.replace("Z", "+00:00"))
                lag_seconds: Optional[float] = (
                    effective_now - last_dt
                ).total_seconds()
            except Exception:
                lag_seconds = None

            # 7d failure rate
            week_res = (
                client.table("outbound_sync_log")
                .select("status")
                .eq("provider", provider)
                .gte("synced_at", cutoff_7d)
                .execute()
            )
            week_rows = week_res.data or []

            if week_rows:
                total_week = len(week_rows)
                failed_week = sum(
                    1 for r in week_rows
                    if str(r.get("status", "")).lower() in ("failed", "error", "fail")
                )
                failure_rate: Optional[float] = failed_week / total_week
            else:
                failure_rate = None

            # Derive status
            prov_status = "ok"
            if (
                (failure_rate is not None and failure_rate > _DEGRADED_FAILURE_RATE)
                or (lag_seconds is not None and lag_seconds > _DEGRADED_LAG_SECONDS)
            ):
                prov_status = "degraded"

            results.append(OutboundSyncProbeResult(
                provider=provider,
                last_sync_at=last_sync_at_str,
                failure_rate_7d=failure_rate,
                log_lag_seconds=lag_seconds,
                status=prov_status,
            ))

        except Exception as exc:  # noqa: BLE001
            logger.warning("outbound probe failed for provider=%s: %s", provider, exc)
            results.append(OutboundSyncProbeResult(
                provider=provider,
                last_sync_at=None,
                failure_rate_7d=None,
                log_lag_seconds=None,
                status="error",
            ))

    return results


_DEFAULT_PROVIDERS = ["airbnb", "bookingcom", "expedia", "agoda", "tripcom"]


def run_health_checks_enriched(
    version: str,
    env: str,
    outbound_client: Optional[Any] = None,
    outbound_providers: Optional[List[str]] = None,
    now: Optional[datetime] = None,
) -> HealthResult:
    """
    Extended health check: all Phase 64 checks + Phase 172 outbound probes.

    Outbound probes read from outbound_sync_log. Each provider gets a
    last_sync_at, failure_rate_7d, and log_lag_seconds.

    A degraded outbound probe sets overall status=degraded (never 503).
    An error probe (DB failure) also sets degraded.

    Args:
        version:            App version string.
        env:                Environment name.
        outbound_client:    Optional Supabase client for outbound probes.
                            If None, outbound probes are skipped.
        outbound_providers: Override provider list for probes.
        now:                Override current time (for testing).

    Returns:
        HealthResult with checks['outbound'] populated.
    """
    result = run_health_checks(version=version, env=env)

    if outbound_client is None:
        result.checks["outbound"] = {"status": "skipped", "reason": "no client provided"}
        return result

    probes = probe_outbound_sync(
        client=outbound_client,
        providers=outbound_providers,
        now=now,
    )

    probe_summaries = [
        {
            "provider":         p.provider,
            "last_sync_at":     p.last_sync_at,
            "failure_rate_7d":  p.failure_rate_7d,
            "log_lag_seconds":  p.log_lag_seconds,
            "status":           p.status,
        }
        for p in probes
    ]

    any_degraded = any(p.status in ("degraded", "error") for p in probes)
    outbound_status = "degraded" if any_degraded else "ok"
    if probes and all(p.status == "idle" for p in probes):
        outbound_status = "idle"

    result.checks["outbound"] = {
        "status":    outbound_status,
        "providers": probe_summaries,
    }

    if any_degraded and result.status == "ok":
        result.status = "degraded"

    return result
