"""
Phase 263 — Production Monitoring Hooks
=========================================

Lightweight in-process instrumentation layer.

Tracks:
  - Request counts per route prefix
  - Error counts (4xx, 5xx) per route prefix
  - Uptime (process start time)
  - A named latency histogram (rolling 1000-sample window per route)

No external dependencies — pure Python stdlib.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque

# Process start time
_PROCESS_START = time.monotonic()
_PROCESS_START_UTC = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Counters (thread-safe enough for single-process FastAPI under Uvicorn)
# ---------------------------------------------------------------------------

_request_count: dict[str, int] = defaultdict(int)
_error_4xx_count: dict[str, int] = defaultdict(int)
_error_5xx_count: dict[str, int] = defaultdict(int)

# Latency: {route_prefix: deque of float (seconds), max 1000 samples}
_MAX_SAMPLES = 1000
_latency_samples: dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=_MAX_SAMPLES))


# ---------------------------------------------------------------------------
# Record functions
# ---------------------------------------------------------------------------

def record_request(route: str, status_code: int, latency_s: float) -> None:
    """Called after each request to update all counters."""
    prefix = _route_prefix(route)
    _request_count[prefix] += 1
    if 400 <= status_code < 500:
        _error_4xx_count[prefix] += 1
    elif status_code >= 500:
        _error_5xx_count[prefix] += 1
    _latency_samples[prefix].append(latency_s)


def _route_prefix(route: str) -> str:
    """Collapse /admin/xxx → /admin, /guest/xxx → /guest, etc."""
    parts = route.strip("/").split("/")
    return f"/{parts[0]}" if parts else "/"


# ---------------------------------------------------------------------------
# Read functions
# ---------------------------------------------------------------------------

def get_uptime_seconds() -> float:
    return time.monotonic() - _PROCESS_START


def get_request_counts() -> dict[str, int]:
    return dict(_request_count)


def get_error_counts() -> dict[str, dict[str, int]]:
    # Union of all route prefixes seen
    prefixes = set(_error_4xx_count) | set(_error_5xx_count)
    return {
        p: {
            "4xx": _error_4xx_count.get(p, 0),
            "5xx": _error_5xx_count.get(p, 0),
        }
        for p in sorted(prefixes)
    }


def get_latency_stats(route: str | None = None) -> dict:
    """
    Returns min/max/avg/p95 for the given route prefix (or all combined).
    """
    if route:
        prefix = _route_prefix(route)
        samples = list(_latency_samples.get(prefix, []))
        return {prefix: _compute_stats(samples)}

    result = {}
    for prefix, dq in _latency_samples.items():
        result[prefix] = _compute_stats(list(dq))
    return result


def _compute_stats(samples: list[float]) -> dict:
    if not samples:
        return {"count": 0, "min_ms": None, "max_ms": None, "avg_ms": None, "p95_ms": None}
    sorted_s = sorted(samples)
    count = len(sorted_s)
    to_ms = lambda s: round(s * 1000, 2)
    p95_idx = int(count * 0.95)
    return {
        "count":   count,
        "min_ms":  to_ms(sorted_s[0]),
        "max_ms":  to_ms(sorted_s[-1]),
        "avg_ms":  to_ms(sum(sorted_s) / count),
        "p95_ms":  to_ms(sorted_s[min(p95_idx, count - 1)]),
    }


def get_full_metrics() -> dict:
    return {
        "uptime_seconds":   round(get_uptime_seconds(), 2),
        "process_start_utc": _PROCESS_START_UTC,
        "request_counts":   get_request_counts(),
        "error_counts":     get_error_counts(),
        "latency":          get_latency_stats(),
    }


def reset_metrics() -> None:
    """For testing only — flushes all counters."""
    _request_count.clear()
    _error_4xx_count.clear()
    _error_5xx_count.clear()
    _latency_samples.clear()
