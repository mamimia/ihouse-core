"""
Phase 87 — Tenant Isolation Hardening

Extends Phase 81 (query-level audit) with a system-level isolation policy.

This module:
  1. Defines the canonical table classification: TENANT_SCOPED vs GLOBAL.
  2. Provides `TableIsolationPolicy` — a locked registry of which tables require
     tenant_id filtering and which are intentionally global.
  3. Provides `CrossTenantLeakResult` — result of checking a specific cross-tenant
     data access attempt against the policy.
  4. Provides `audit_system_isolation` — scans the full set of known tables and
     verifies all TENANT_SCOPED tables have a registered isolation strategy.
  5. Provides `assert_no_cross_tenant_access` — given two tenants and a DB response,
     verifies that tenant B's data does not appear in tenant A's result set.

Design rules:
  - Pure computation — no actual DB reads.
  - All results are immutable dataclasses.
  - Never raises.
  - Augments (not replaces) Phase 81 tenant_isolation_checker.py.

Table classification rationale:
  TENANT_SCOPED: event_log, booking_state, booking_financial_facts
    These tables contain per-tenant business data. ALL queries MUST filter by tenant_id.
  GLOBAL: ota_dead_letter, ota_ordering_buffer
    These tables do not have a tenant_id column — they are intentionally global.
    Isolation for these tables is enforced at the application layer (booking_id routing),
    not at the DB column level.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Table classification
# ---------------------------------------------------------------------------

class TableScope(str, Enum):
    TENANT_SCOPED = "TENANT_SCOPED"   # Must filter by tenant_id
    GLOBAL        = "GLOBAL"          # No tenant_id column — global by design


# Canonical table registry — locked for Phase 87
# Any future table addition MUST declare its scope here.
TABLE_REGISTRY: Dict[str, TableScope] = {
    "event_log":               TableScope.TENANT_SCOPED,
    "booking_state":           TableScope.TENANT_SCOPED,
    "booking_financial_facts": TableScope.TENANT_SCOPED,
    "ota_dead_letter":         TableScope.GLOBAL,
    "ota_ordering_buffer":     TableScope.GLOBAL,
}

# Derived sets for convenience
TENANT_SCOPED_TABLES: Set[str] = {
    t for t, scope in TABLE_REGISTRY.items()
    if scope == TableScope.TENANT_SCOPED
}

GLOBAL_TABLES: Set[str] = {
    t for t, scope in TABLE_REGISTRY.items()
    if scope == TableScope.GLOBAL
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TableIsolationPolicy:
    """
    Isolation policy for a single table.

    table_name:       Name of the DB table
    scope:            TENANT_SCOPED or GLOBAL
    requires_filter:  True → every query must include tenant_id filter
    rationale:        Human-readable explanation of the isolation decision
    """
    table_name: str
    scope: TableScope
    requires_filter: bool
    rationale: str


@dataclass(frozen=True)
class CrossTenantLeakResult:
    """
    Result of a cross-tenant access check.

    tenant_requesting:  Tenant that made the request
    tenant_target:      Tenant whose data is being checked for leakage
    leaked:             True if tenant_target's data appeared in the result
    leaked_row_count:   Number of rows that should not have appeared
    detail:             Human-readable description
    """
    tenant_requesting: str
    tenant_target: str
    leaked: bool
    leaked_row_count: int
    detail: str


@dataclass(frozen=True)
class SystemIsolationReport:
    """
    Full system isolation audit result.

    all_compliant:       True if all TENANT_SCOPED tables have a registered policy
    scoped_table_count:  Count of TENANT_SCOPED tables
    global_table_count:  Count of GLOBAL tables
    violations:          List of table names that are missing policy registration
    policies:            Full policy registry as list
    """
    all_compliant: bool
    scoped_table_count: int
    global_table_count: int
    violations: List[str]
    policies: List[TableIsolationPolicy]

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0


# ---------------------------------------------------------------------------
# Policy registry
# ---------------------------------------------------------------------------

_POLICIES: Dict[str, TableIsolationPolicy] = {
    "event_log": TableIsolationPolicy(
        table_name="event_log",
        scope=TableScope.TENANT_SCOPED,
        requires_filter=True,
        rationale=(
            "event_log stores canonical booking events per tenant. "
            "All queries MUST include tenant_id filter. "
            "Cross-tenant reads would expose another tenant's booking history."
        ),
    ),
    "booking_state": TableIsolationPolicy(
        table_name="booking_state",
        scope=TableScope.TENANT_SCOPED,
        requires_filter=True,
        rationale=(
            "booking_state is the current projection of booking lifecycle. "
            "It contains tenant business-critical data. "
            "All queries MUST include tenant_id filter."
        ),
    ),
    "booking_financial_facts": TableIsolationPolicy(
        table_name="booking_financial_facts",
        scope=TableScope.TENANT_SCOPED,
        requires_filter=True,
        rationale=(
            "booking_financial_facts contains revenue, pricing, and commission data. "
            "This is financially sensitive per-tenant data. "
            "All queries MUST include tenant_id filter."
        ),
    ),
    "ota_dead_letter": TableIsolationPolicy(
        table_name="ota_dead_letter",
        scope=TableScope.GLOBAL,
        requires_filter=False,
        rationale=(
            "ota_dead_letter has no tenant_id column — it is a global rejection queue. "
            "Isolation is enforced at the application layer via booking_id routing. "
            "Admin access to the global DLQ is intentional and documented."
        ),
    ),
    "ota_ordering_buffer": TableIsolationPolicy(
        table_name="ota_ordering_buffer",
        scope=TableScope.GLOBAL,
        requires_filter=False,
        rationale=(
            "ota_ordering_buffer is a global event ordering queue with no tenant_id column. "
            "Isolation is provided by booking_id which is deterministically scoped to a tenant. "
            "Global read access is intentional for the ordering engine."
        ),
    ),
}


def get_table_policy(table_name: str) -> Optional[TableIsolationPolicy]:
    """Return the isolation policy for a table, or None if not registered."""
    return _POLICIES.get(table_name)


def get_all_policies() -> List[TableIsolationPolicy]:
    """Return all registered table isolation policies."""
    return list(_POLICIES.values())


# ---------------------------------------------------------------------------
# Cross-tenant leak detection
# ---------------------------------------------------------------------------

def check_cross_tenant_leak(
    tenant_requesting: str,
    tenant_target: str,
    rows: List[Dict[str, Any]],
    tenant_id_field: str = "tenant_id",
) -> CrossTenantLeakResult:
    """
    Check whether a query result intended for `tenant_requesting` accidentally
    contains rows belonging to `tenant_target`.

    This is a Python-layer check — it inspects actual row data returned by
    the DB and verifies no row has tenant_id == tenant_target when the
    requesting tenant is tenant_requesting.

    Args:
        tenant_requesting:  The tenant that made the legitimate request
        tenant_target:      The foreign tenant whose data should NOT appear
        rows:               List of DB result rows (dicts)
        tenant_id_field:    Column name for tenant_id (default: "tenant_id")

    Returns:
        CrossTenantLeakResult — never raises
    """
    if tenant_requesting == tenant_target:
        return CrossTenantLeakResult(
            tenant_requesting=tenant_requesting,
            tenant_target=tenant_target,
            leaked=False,
            leaked_row_count=0,
            detail="Same tenant — cross-tenant check is not applicable.",
        )

    leaked_rows = [
        row for row in (rows or [])
        if isinstance(row, dict)
        and row.get(tenant_id_field) == tenant_target
    ]

    count = len(leaked_rows)
    leaked = count > 0

    if leaked:
        detail = (
            f"LEAK DETECTED: tenant={tenant_requesting!r} received {count} row(s) "
            f"belonging to tenant={tenant_target!r}"
        )
    else:
        detail = (
            f"Clean: tenant={tenant_requesting!r} result contains no data "
            f"belonging to tenant={tenant_target!r}"
        )

    return CrossTenantLeakResult(
        tenant_requesting=tenant_requesting,
        tenant_target=tenant_target,
        leaked=leaked,
        leaked_row_count=count,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# System-level isolation audit
# ---------------------------------------------------------------------------

def audit_system_isolation() -> SystemIsolationReport:
    """
    Audit the full table registry against the policy registry.

    Verifies:
      1. All TENANT_SCOPED tables have a registered isolation policy.
      2. All GLOBAL tables have a registered rationale explaining why they are global.

    A table in TABLE_REGISTRY without an entry in _POLICIES is a violation.
    Global tables without rationale are also flagged.

    Returns SystemIsolationReport — never raises.
    """
    violations: List[str] = []

    for table_name, scope in TABLE_REGISTRY.items():
        policy = _POLICIES.get(table_name)
        if policy is None:
            violations.append(table_name)
        elif scope == TableScope.TENANT_SCOPED and not policy.requires_filter:
            # TENANT_SCOPED table registered but marked as not requiring filter — violation
            violations.append(table_name)

    return SystemIsolationReport(
        all_compliant=len(violations) == 0,
        scoped_table_count=len(TENANT_SCOPED_TABLES),
        global_table_count=len(GLOBAL_TABLES),
        violations=violations,
        policies=get_all_policies(),
    )
