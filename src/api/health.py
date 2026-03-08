"""
Enhanced Health Check — Phase 64
==================================

Provides health_check() — used by GET /health in src/main.py.

Checks:
1. Supabase connectivity — SELECT 1 query against SUPABASE_URL/rest/v1/
2. DLQ row count — number of unprocessed ota_dead_letter rows

Response semantics (SaaS standard):
    200  status=ok         — all checks passed
    200  status=degraded   — at least one check slow / partial (still serving)
    503  status=unhealthy  — Supabase unreachable

DLQ count is informational — a non-zero count sets status=degraded, not 503.
The caller should monitor DLQ count separately via alerting (future phase).

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
from typing import Any, Dict

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 3.0
_DLQ_TABLE = "ota_dead_letter"


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

    return HealthResult(
        status=overall,
        version=version,
        env=env,
        checks=checks,
        http_status=http_status,
    )
