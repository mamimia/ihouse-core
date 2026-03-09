"""
Phase 81 — Tenant Isolation Checker contract tests.

Groups:
  A — TenantIsolationReport dataclass (frozen, fields, all_isolated)
  B — check_query_has_tenant_filter (nested/flat, missing, None, empty)
  C — audit_tenant_isolation (all isolated, partial, empty list, zero)
  D — Invariants (never raises, conservative on error, all_isolated=False when empty)
"""
from __future__ import annotations

import pytest

from adapters.ota.tenant_isolation_checker import (
    TenantIsolationReport,
    audit_tenant_isolation,
    check_query_has_tenant_filter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _q(tenant_id: str | None = "t1", use_nested: bool = True) -> dict:
    """Build a query dict with or without a tenant_id filter."""
    if use_nested:
        filters: dict = {}
        if tenant_id is not None:
            filters["tenant_id"] = tenant_id
        return {"table": "booking_state", "filters": filters}
    # Flat form
    result: dict = {"table": "booking_state"}
    if tenant_id is not None:
        result["tenant_id"] = tenant_id
    return result


# ---------------------------------------------------------------------------
# Group A — TenantIsolationReport dataclass
# ---------------------------------------------------------------------------

class TestTenantIsolationReport:

    def test_A1_is_frozen(self) -> None:
        """TenantIsolationReport must be immutable."""
        report = TenantIsolationReport(
            router_name="test",
            total_queries=1,
            isolated_queries=1,
            unfiltered_queries=0,
            all_isolated=True,
        )
        with pytest.raises((AttributeError, TypeError)):
            report.router_name = "hacked"  # type: ignore[misc]

    def test_A2_all_fields_accessible(self) -> None:
        report = TenantIsolationReport(
            router_name="bookings_router",
            total_queries=3,
            isolated_queries=2,
            unfiltered_queries=1,
            all_isolated=False,
        )
        assert report.router_name == "bookings_router"
        assert report.total_queries == 3
        assert report.isolated_queries == 2
        assert report.unfiltered_queries == 1
        assert report.all_isolated is False

    def test_A3_all_isolated_true_when_all_filtered(self) -> None:
        report = TenantIsolationReport(
            router_name="r",
            total_queries=2,
            isolated_queries=2,
            unfiltered_queries=0,
            all_isolated=True,
        )
        assert report.all_isolated is True

    def test_A4_all_isolated_false_when_some_unfiltered(self) -> None:
        report = TenantIsolationReport(
            router_name="r",
            total_queries=2,
            isolated_queries=1,
            unfiltered_queries=1,
            all_isolated=False,
        )
        assert report.all_isolated is False


# ---------------------------------------------------------------------------
# Group B — check_query_has_tenant_filter
# ---------------------------------------------------------------------------

class TestCheckQueryHasTenantFilter:

    def test_B1_nested_filters_with_tenant_id(self) -> None:
        q = {"table": "booking_state", "filters": {"tenant_id": "t1", "booking_id": "b1"}}
        assert check_query_has_tenant_filter(q) is True

    def test_B2_nested_filters_without_tenant_id(self) -> None:
        q = {"table": "booking_state", "filters": {"booking_id": "b1"}}
        assert check_query_has_tenant_filter(q) is False

    def test_B3_flat_dict_with_tenant_id(self) -> None:
        q = {"table": "ota_dead_letter", "tenant_id": "t1"}
        assert check_query_has_tenant_filter(q) is True

    def test_B4_flat_dict_without_tenant_id(self) -> None:
        q = {"table": "ota_dead_letter"}
        assert check_query_has_tenant_filter(q) is False

    def test_B5_nested_tenant_id_none_is_unfiltered(self) -> None:
        q = {"filters": {"tenant_id": None}}
        assert check_query_has_tenant_filter(q) is False

    def test_B6_nested_tenant_id_empty_string_is_unfiltered(self) -> None:
        q = {"filters": {"tenant_id": ""}}
        assert check_query_has_tenant_filter(q) is False

    def test_B7_empty_dict_is_unfiltered(self) -> None:
        assert check_query_has_tenant_filter({}) is False

    def test_B8_non_dict_input_returns_false(self) -> None:
        assert check_query_has_tenant_filter(None) is False  # type: ignore[arg-type]
        assert check_query_has_tenant_filter("string") is False  # type: ignore[arg-type]

    def test_B9_empty_filters_dict_is_unfiltered(self) -> None:
        q = {"table": "x", "filters": {}}
        assert check_query_has_tenant_filter(q) is False


# ---------------------------------------------------------------------------
# Group C — audit_tenant_isolation
# ---------------------------------------------------------------------------

class TestAuditTenantIsolation:

    def test_C1_all_isolated(self) -> None:
        queries = [_q("t1"), _q("t1"), _q("t1")]
        report = audit_tenant_isolation("bookings_router", queries)
        assert report.total_queries == 3
        assert report.isolated_queries == 3
        assert report.unfiltered_queries == 0
        assert report.all_isolated is True

    def test_C2_partial_isolation(self) -> None:
        # 2 filtered + 1 unfiltered (DLQ global)
        queries = [_q("t1"), _q("t1"), {"table": "ota_dead_letter", "filters": {}}]
        report = audit_tenant_isolation("admin_router", queries)
        assert report.total_queries == 3
        assert report.isolated_queries == 2
        assert report.unfiltered_queries == 1
        assert report.all_isolated is False

    def test_C3_all_unfiltered(self) -> None:
        queries = [{"table": "ota_dead_letter"}, {"table": "global_metrics"}]
        report = audit_tenant_isolation("global_router", queries)
        assert report.isolated_queries == 0
        assert report.unfiltered_queries == 2
        assert report.all_isolated is False

    def test_C4_empty_list_returns_zero_counts(self) -> None:
        report = audit_tenant_isolation("empty", [])
        assert report.total_queries == 0
        assert report.isolated_queries == 0
        assert report.unfiltered_queries == 0

    def test_C5_router_name_preserved_in_report(self) -> None:
        report = audit_tenant_isolation("my_custom_router", [_q("t1")])
        assert report.router_name == "my_custom_router"

    def test_C6_single_isolated_query(self) -> None:
        report = audit_tenant_isolation("r", [_q("t1")])
        assert report.all_isolated is True
        assert report.total_queries == 1

    def test_C7_flat_tenant_id_form_also_counts(self) -> None:
        q = _q("t1", use_nested=False)
        report = audit_tenant_isolation("r", [q])
        assert report.isolated_queries == 1
        assert report.all_isolated is True


# ---------------------------------------------------------------------------
# Group D — Invariants
# ---------------------------------------------------------------------------

class TestInvariants:

    def test_D1_never_raises_on_bad_query_entries(self) -> None:
        """audit_tenant_isolation must never raise — bad entries counted as unfiltered."""
        queries: list = [None, 123, "bad", {"filters": None}]  # type: ignore[list-item]
        report = audit_tenant_isolation("r", queries)
        # Should complete without exception
        assert report.total_queries == len(queries)
        assert report.all_isolated is False

    def test_D2_empty_list_all_isolated_is_false(self) -> None:
        """Vacuously 'all isolated' is False when there are no queries."""
        report = audit_tenant_isolation("r", [])
        assert report.all_isolated is False

    def test_D3_report_is_frozen_after_construction(self) -> None:
        """audit_tenant_isolation result is immutable."""
        report = audit_tenant_isolation("r", [_q("t1")])
        with pytest.raises((AttributeError, TypeError)):
            report.all_isolated = False  # type: ignore[misc]

    def test_D4_isolated_plus_unfiltered_equals_total(self) -> None:
        queries = [_q("t1"), {"table": "x"}, _q("t2"), {"table": "y"}]
        report = audit_tenant_isolation("r", queries)
        assert report.isolated_queries + report.unfiltered_queries == report.total_queries
