"""
Phase 81 — Tenant Isolation Checker

Audit tool that verifies query configurations filter by tenant_id.

Rules:
- Pure inspection — never reads from or writes to any database.
- Never raises — all exceptions are swallowed and counted.
- TenantIsolationReport is frozen and immutable after construction.

Usage:
    from adapters.ota.tenant_isolation_checker import (
        TenantIsolationReport,
        audit_tenant_isolation,
        check_query_has_tenant_filter,
    )

    queries = [
        {"table": "booking_state", "filters": {"tenant_id": "t1", "booking_id": "b1"}},
        {"table": "ota_dead_letter", "filters": {}},  # global — no tenant_id
    ]
    report = audit_tenant_isolation("bookings_router", queries)
    report.all_isolated  # False — ota_dead_letter is unfiltered
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TenantIsolationReport:
    """
    Immutable result of a tenant isolation audit for one router.

    Attributes:
        router_name         — name of the router or module being audited
        total_queries       — total number of queries examined
        isolated_queries    — queries that include a tenant_id filter
        unfiltered_queries  — queries without a tenant_id filter
        all_isolated        — True only when total > 0 and all queries are filtered
    """
    router_name: str
    total_queries: int
    isolated_queries: int
    unfiltered_queries: int
    all_isolated: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def check_query_has_tenant_filter(query: dict[str, Any]) -> bool:
    """
    Return True if the query dict contains a non-None tenant_id in its filters.

    Accepts two interface shapes:
        {"filters": {"tenant_id": "..."}}   — nested filters key
        {"tenant_id": "..."}                — flat dict (convenience form)

    A query with tenant_id=None or tenant_id="" is treated as unfiltered.
    """
    if not isinstance(query, dict):
        return False

    # Try nested 'filters' key first
    filters = query.get("filters")
    if isinstance(filters, dict):
        val = filters.get("tenant_id")
        return bool(val)

    # Flat dict fallback
    val = query.get("tenant_id")
    return bool(val)


# ---------------------------------------------------------------------------
# Audit function
# ---------------------------------------------------------------------------

def audit_tenant_isolation(
    router_name: str,
    queries: list[dict[str, Any]],
) -> TenantIsolationReport:
    """
    Audit a list of query configurations for tenant_id isolation.

    Args:
        router_name — label for the router being audited (used in report only)
        queries     — list of query dicts, each representing one DB query

    Returns:
        TenantIsolationReport — immutable audit result

    Never raises. Any per-query error is counted as unfiltered (conservative).
    """
    if not queries:
        return TenantIsolationReport(
            router_name=router_name,
            total_queries=0,
            isolated_queries=0,
            unfiltered_queries=0,
            all_isolated=False,
        )

    isolated = 0
    unfiltered = 0

    for query in queries:
        try:
            if check_query_has_tenant_filter(query):
                isolated += 1
            else:
                unfiltered += 1
        except Exception:  # noqa: BLE001
            # Any unexpected error is conservative: count as unfiltered
            unfiltered += 1

    total = isolated + unfiltered
    all_isolated = (total > 0) and (unfiltered == 0)

    return TenantIsolationReport(
        router_name=router_name,
        total_queries=total,
        isolated_queries=isolated,
        unfiltered_queries=unfiltered,
        all_isolated=all_isolated,
    )
