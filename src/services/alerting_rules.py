"""
Phase 475 — Alerting Rules Configuration

Defines alerting thresholds and rules for production monitoring.
Used by the system status dashboard to flag warnings/critical states.

Rules:
- All thresholds are configurable via environment variables.
- Alert evaluation is pure — no side effects.
- Returns a list of fired alerts with severity and remediation hints.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Alert severities
# ---------------------------------------------------------------------------

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Alert result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Alert:
    rule: str
    severity: str
    message: str
    value: Any = None
    threshold: Any = None
    remediation: str = ""


# ---------------------------------------------------------------------------
# Threshold defaults (override via env)
# ---------------------------------------------------------------------------

def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Alert evaluation
# ---------------------------------------------------------------------------

def evaluate_alerts(health_checks: Dict[str, Any]) -> List[Alert]:
    """
    Evaluate alerting rules against the health check output.

    Args:
        health_checks: The 'checks' dict from HealthResult.

    Returns:
        List of fired Alert objects (may be empty).
    """
    alerts: List[Alert] = []

    # Rule 1: DLQ unprocessed count
    dlq = health_checks.get("dlq", {})
    dlq_count = dlq.get("unprocessed_count", 0)
    dlq_warn = _env_int("ALERT_DLQ_WARN", 5)
    dlq_crit = _env_int("ALERT_DLQ_CRIT", 20)

    if isinstance(dlq_count, (int, float)):
        if dlq_count >= dlq_crit:
            alerts.append(Alert(
                rule="dlq_overflow",
                severity=SEVERITY_CRITICAL,
                message=f"DLQ has {dlq_count} unprocessed events (threshold: {dlq_crit})",
                value=dlq_count,
                threshold=dlq_crit,
                remediation="Review /dlq-inspector, replay or purge stale events.",
            ))
        elif dlq_count >= dlq_warn:
            alerts.append(Alert(
                rule="dlq_backlog",
                severity=SEVERITY_WARNING,
                message=f"DLQ has {dlq_count} unprocessed events (threshold: {dlq_warn})",
                value=dlq_count,
                threshold=dlq_warn,
                remediation="Investigate recent webhook failures. Check OTA payload format changes.",
            ))

    # Rule 2: Supabase unreachable
    supabase = health_checks.get("supabase", {})
    if supabase.get("status") == "unreachable":
        alerts.append(Alert(
            rule="supabase_down",
            severity=SEVERITY_CRITICAL,
            message="Supabase is unreachable",
            value=supabase.get("error", "unknown"),
            remediation="Check SUPABASE_URL, network connectivity, Supabase dashboard for outages.",
        ))

    # Rule 3: Supabase latency
    supabase_lat = supabase.get("latency_ms")
    lat_warn = _env_int("ALERT_SUPABASE_LATENCY_WARN_MS", 500)
    lat_crit = _env_int("ALERT_SUPABASE_LATENCY_CRIT_MS", 2000)
    if isinstance(supabase_lat, (int, float)):
        if supabase_lat >= lat_crit:
            alerts.append(Alert(
                rule="supabase_latency_critical",
                severity=SEVERITY_CRITICAL,
                message=f"Supabase latency {supabase_lat}ms exceeds {lat_crit}ms",
                value=supabase_lat,
                threshold=lat_crit,
                remediation="Check Supabase region, connection pooling, or consider upgrading plan.",
            ))
        elif supabase_lat >= lat_warn:
            alerts.append(Alert(
                rule="supabase_latency_high",
                severity=SEVERITY_WARNING,
                message=f"Supabase latency {supabase_lat}ms exceeds {lat_warn}ms",
                value=supabase_lat,
                threshold=lat_warn,
                remediation="Monitor trend. May indicate Supabase load or network issues.",
            ))

    # Rule 4: Outbound sync failures
    outbound = health_checks.get("outbound", {})
    if isinstance(outbound.get("providers"), list):
        fail_rate_warn = _env_float("ALERT_OUTBOUND_FAIL_RATE_WARN", 0.1)
        for prov in outbound["providers"]:
            rate = prov.get("failure_rate_7d")
            if isinstance(rate, (int, float)) and rate > fail_rate_warn:
                sev = SEVERITY_CRITICAL if rate > 0.3 else SEVERITY_WARNING
                alerts.append(Alert(
                    rule=f"outbound_failure_rate_{prov['provider']}",
                    severity=sev,
                    message=f"Outbound sync failure rate for {prov['provider']}: {rate:.0%}",
                    value=rate,
                    threshold=fail_rate_warn,
                    remediation=f"Check outbound_sync_log for {prov['provider']}. Verify API credentials and rate limits.",
                ))

            lag = prov.get("log_lag_seconds")
            lag_warn = _env_int("ALERT_OUTBOUND_LAG_WARN_SEC", 3600)
            if isinstance(lag, (int, float)) and lag > lag_warn:
                alerts.append(Alert(
                    rule=f"outbound_stale_{prov['provider']}",
                    severity=SEVERITY_WARNING,
                    message=f"Outbound sync for {prov['provider']} stale: {lag:.0f}s since last sync",
                    value=lag,
                    threshold=lag_warn,
                    remediation=f"Check if {prov['provider']} sync trigger is active.",
                ))

    return alerts
