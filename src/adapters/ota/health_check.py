from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment,misc]

from adapters.ota.dlq_inspector import get_pending_count
from adapters.ota.dlq_alerting import check_dlq_threshold_default


_DEFAULT_THRESHOLD = 10
_ENV_VAR = "DLQ_ALERT_THRESHOLD"


@dataclass(frozen=True)
class ComponentStatus:
    """Status of a single system component."""
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class HealthReport:
    """
    Consolidated system health report.

    ok = True only when ALL components are healthy AND the DLQ
    threshold has not been exceeded.

    Intended use:
    - Ops runbook: call system_health_check() before any deploy
    - CI smoke test: assert report.ok
    - SRE triage: inspect report.components for the failing component
    """
    ok: bool
    components: List[ComponentStatus]
    dlq_pending: int
    ordering_buffer_pending: int
    timestamp: str


def _get_client() -> Any:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    if create_client is None:  # pragma: no cover
        raise EnvironmentError("supabase-py is not installed")
    return create_client(url, key)


def _check_table(client: Any, table: str, select_field: str = "id") -> ComponentStatus:
    """Try a minimal SELECT on `table`. Returns ComponentStatus."""
    try:
        client.table(table).select(select_field).limit(1).execute()
        return ComponentStatus(name=table, ok=True, detail="accessible")
    except Exception as exc:
        return ComponentStatus(name=table, ok=False, detail=str(exc))


def system_health_check(client: Any = None) -> HealthReport:
    """
    Run a full system health check and return a HealthReport.

    Checks:
    1. supabase_connectivity — SELECT on booking_state
    2. dlq_table            — SELECT on ota_dead_letter
    3. ordering_buffer      — SELECT on ota_ordering_buffer
    4. dlq_threshold        — pending DLQ count vs DLQ_ALERT_THRESHOLD
    5. ordering_buffer_waiting — how many events are buffered (informational)

    The overall report.ok is False if ANY component is not ok OR the
    DLQ threshold is exceeded.

    Never raises. All exceptions are caught per component.
    """
    if client is None:
        client = _get_client()

    ts = datetime.now(timezone.utc).isoformat()
    components: List[ComponentStatus] = []

    # 1. Supabase connectivity
    conn = _check_table(client, "booking_state", select_field="booking_id")
    components.append(ComponentStatus(
        name="supabase_connectivity",
        ok=conn.ok,
        detail=conn.detail,
    ))

    # 2. DLQ table
    components.append(_check_table(client, "ota_dead_letter"))

    # 3. Ordering buffer table
    components.append(_check_table(client, "ota_ordering_buffer"))

    # 4. DLQ threshold
    dlq_pending = 0
    try:
        dlq_pending = get_pending_count(client)
        alert = check_dlq_threshold_default(client)
        if alert.exceeded:
            components.append(ComponentStatus(
                name="dlq_threshold",
                ok=False,
                detail=f"pending={dlq_pending} >= threshold={alert.threshold}",
            ))
        else:
            components.append(ComponentStatus(
                name="dlq_threshold",
                ok=True,
                detail=f"pending={dlq_pending} < threshold={alert.threshold}",
            ))
    except Exception as exc:
        components.append(ComponentStatus(
            name="dlq_threshold",
            ok=False,
            detail=str(exc),
        ))

    # 5. Ordering buffer waiting (informational — does not affect overall ok)
    ordering_pending = 0
    try:
        result = (
            client.table("ota_ordering_buffer")
            .select("id")
            .eq("status", "waiting")
            .execute()
        )
        ordering_pending = len(result.data or [])
        components.append(ComponentStatus(
            name="ordering_buffer_waiting",
            ok=True,
            detail=f"waiting={ordering_pending}",
        ))
    except Exception as exc:
        components.append(ComponentStatus(
            name="ordering_buffer_waiting",
            ok=False,
            detail=str(exc),
        ))

    overall_ok = all(c.ok for c in components)

    return HealthReport(
        ok=overall_ok,
        components=components,
        dlq_pending=dlq_pending,
        ordering_buffer_pending=ordering_pending,
        timestamp=ts,
    )
