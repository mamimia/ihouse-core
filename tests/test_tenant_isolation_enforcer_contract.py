"""
Phase 87 — Contract tests for tenant_isolation_enforcer.py.

Tests:
  A — Table registry: TABLE_REGISTRY, TENANT_SCOPED_TABLES, GLOBAL_TABLES
  B — TableIsolationPolicy structure and immutability
  C — get_table_policy: known + unknown tables
  D — check_cross_tenant_leak: no leak, detected leak, edge cases
  E — audit_system_isolation: clean system, policy coverage
  F — CrossTenantLeakResult properties
  G — SystemIsolationReport properties
  H — Integration: isolation checker (Phase 81) + enforcer (Phase 87) agreement
  I — Invariants: immutability, never raises, no writes
"""
from __future__ import annotations

from typing import List, Dict, Any

import pytest

from adapters.ota.tenant_isolation_enforcer import (
    TableScope,
    TABLE_REGISTRY,
    TENANT_SCOPED_TABLES,
    GLOBAL_TABLES,
    TableIsolationPolicy,
    CrossTenantLeakResult,
    SystemIsolationReport,
    get_table_policy,
    get_all_policies,
    check_cross_tenant_leak,
    audit_system_isolation,
)

TENANT_A = "tenant-alpha"
TENANT_B = "tenant-beta"


# ---------------------------------------------------------------------------
# Group A — Table registry
# ---------------------------------------------------------------------------

class TestTableRegistry:

    def test_A1_event_log_is_tenant_scoped(self) -> None:
        assert TABLE_REGISTRY["event_log"] == TableScope.TENANT_SCOPED

    def test_A2_booking_state_is_tenant_scoped(self) -> None:
        assert TABLE_REGISTRY["booking_state"] == TableScope.TENANT_SCOPED

    def test_A3_booking_financial_facts_is_tenant_scoped(self) -> None:
        assert TABLE_REGISTRY["booking_financial_facts"] == TableScope.TENANT_SCOPED

    def test_A4_ota_dead_letter_is_global(self) -> None:
        assert TABLE_REGISTRY["ota_dead_letter"] == TableScope.GLOBAL

    def test_A5_ota_ordering_buffer_is_global(self) -> None:
        assert TABLE_REGISTRY["ota_ordering_buffer"] == TableScope.GLOBAL

    def test_A6_tenant_scoped_set_correct(self) -> None:
        assert "event_log" in TENANT_SCOPED_TABLES
        assert "booking_state" in TENANT_SCOPED_TABLES
        assert "booking_financial_facts" in TENANT_SCOPED_TABLES

    def test_A7_global_set_correct(self) -> None:
        assert "ota_dead_letter" in GLOBAL_TABLES
        assert "ota_ordering_buffer" in GLOBAL_TABLES

    def test_A8_global_not_in_scoped(self) -> None:
        assert "ota_dead_letter" not in TENANT_SCOPED_TABLES
        assert "ota_ordering_buffer" not in TENANT_SCOPED_TABLES

    def test_A9_scoped_not_in_global(self) -> None:
        assert "event_log" not in GLOBAL_TABLES
        assert "booking_state" not in GLOBAL_TABLES

    def test_A10_registry_covers_five_tables(self) -> None:
        assert len(TABLE_REGISTRY) == 5


# ---------------------------------------------------------------------------
# Group B — TableIsolationPolicy
# ---------------------------------------------------------------------------

class TestTableIsolationPolicy:

    def _policy(self) -> TableIsolationPolicy:
        return TableIsolationPolicy(
            table_name="booking_state",
            scope=TableScope.TENANT_SCOPED,
            requires_filter=True,
            rationale="test rationale",
        )

    def test_B1_is_frozen(self) -> None:
        p = self._policy()
        with pytest.raises((AttributeError, TypeError)):
            p.requires_filter = False  # type: ignore

    def test_B2_fields_accessible(self) -> None:
        p = self._policy()
        assert p.table_name == "booking_state"
        assert p.scope == TableScope.TENANT_SCOPED
        assert p.requires_filter is True
        assert "test rationale" in p.rationale

    def test_B3_global_policy_requires_filter_false(self) -> None:
        p = TableIsolationPolicy(
            table_name="ota_dead_letter",
            scope=TableScope.GLOBAL,
            requires_filter=False,
            rationale="global by design",
        )
        assert p.requires_filter is False


# ---------------------------------------------------------------------------
# Group C — get_table_policy
# ---------------------------------------------------------------------------

class TestGetTablePolicy:

    def test_C1_event_log_policy_exists(self) -> None:
        policy = get_table_policy("event_log")
        assert policy is not None
        assert policy.scope == TableScope.TENANT_SCOPED
        assert policy.requires_filter is True

    def test_C2_booking_state_policy_exists(self) -> None:
        policy = get_table_policy("booking_state")
        assert policy is not None
        assert policy.scope == TableScope.TENANT_SCOPED

    def test_C3_booking_financial_facts_policy_exists(self) -> None:
        policy = get_table_policy("booking_financial_facts")
        assert policy is not None
        assert policy.requires_filter is True

    def test_C4_ota_dead_letter_policy_global(self) -> None:
        policy = get_table_policy("ota_dead_letter")
        assert policy is not None
        assert policy.scope == TableScope.GLOBAL
        assert policy.requires_filter is False

    def test_C5_ota_ordering_buffer_policy_global(self) -> None:
        policy = get_table_policy("ota_ordering_buffer")
        assert policy is not None
        assert policy.scope == TableScope.GLOBAL

    def test_C6_unknown_table_returns_none(self) -> None:
        assert get_table_policy("nonexistent_table") is None

    def test_C7_all_policies_returns_list(self) -> None:
        policies = get_all_policies()
        assert isinstance(policies, list)
        assert len(policies) == 5

    def test_C8_all_policies_have_rationale(self) -> None:
        for policy in get_all_policies():
            assert policy.rationale, f"Table {policy.table_name!r} has no rationale"


# ---------------------------------------------------------------------------
# Group D — check_cross_tenant_leak
# ---------------------------------------------------------------------------

class TestCheckCrossTenantLeak:

    def _rows_for(self, tenant_id: str, count: int = 2) -> List[Dict[str, Any]]:
        return [{"booking_id": f"B-{i}", "tenant_id": tenant_id} for i in range(count)]

    def test_D1_no_leak_when_all_rows_belong_to_requester(self) -> None:
        rows = self._rows_for(TENANT_A, 3)
        result = check_cross_tenant_leak(TENANT_A, TENANT_B, rows)
        assert result.leaked is False
        assert result.leaked_row_count == 0

    def test_D2_leak_detected_when_other_tenant_row_present(self) -> None:
        rows = self._rows_for(TENANT_A, 2) + self._rows_for(TENANT_B, 1)
        result = check_cross_tenant_leak(TENANT_A, TENANT_B, rows)
        assert result.leaked is True
        assert result.leaked_row_count == 1

    def test_D3_all_rows_are_leaked(self) -> None:
        rows = self._rows_for(TENANT_B, 5)
        result = check_cross_tenant_leak(TENANT_A, TENANT_B, rows)
        assert result.leaked is True
        assert result.leaked_row_count == 5

    def test_D4_empty_rows_no_leak(self) -> None:
        result = check_cross_tenant_leak(TENANT_A, TENANT_B, [])
        assert result.leaked is False
        assert result.leaked_row_count == 0

    def test_D5_same_tenant_not_applicable(self) -> None:
        rows = self._rows_for(TENANT_A, 3)
        result = check_cross_tenant_leak(TENANT_A, TENANT_A, rows)
        assert result.leaked is False
        assert "not applicable" in result.detail.lower()

    def test_D6_tenant_ids_preserved_in_result(self) -> None:
        rows = self._rows_for(TENANT_A)
        result = check_cross_tenant_leak(TENANT_A, TENANT_B, rows)
        assert result.tenant_requesting == TENANT_A
        assert result.tenant_target == TENANT_B

    def test_D7_custom_tenant_id_field(self) -> None:
        rows = [{"org_id": TENANT_B, "booking_id": "B-001"}]
        result = check_cross_tenant_leak(TENANT_A, TENANT_B, rows, tenant_id_field="org_id")
        assert result.leaked is True

    def test_D8_rows_with_none_tenant_not_counted_as_leak(self) -> None:
        rows = [{"tenant_id": None, "booking_id": "B-001"}]
        result = check_cross_tenant_leak(TENANT_A, TENANT_B, rows)
        assert result.leaked is False

    def test_D9_detail_contains_tenant_names_on_leak(self) -> None:
        rows = self._rows_for(TENANT_B, 2)
        result = check_cross_tenant_leak(TENANT_A, TENANT_B, rows)
        assert TENANT_A in result.detail
        assert TENANT_B in result.detail

    def test_D10_result_is_frozen(self) -> None:
        result = check_cross_tenant_leak(TENANT_A, TENANT_B, [])
        with pytest.raises((AttributeError, TypeError)):
            result.leaked = True  # type: ignore


# ---------------------------------------------------------------------------
# Group E — audit_system_isolation
# ---------------------------------------------------------------------------

class TestAuditSystemIsolation:

    def test_E1_returns_system_isolation_report(self) -> None:
        report = audit_system_isolation()
        assert isinstance(report, SystemIsolationReport)

    def test_E2_system_is_compliant(self) -> None:
        report = audit_system_isolation()
        assert report.all_compliant is True
        assert report.violations == []

    def test_E3_scoped_count_is_three(self) -> None:
        report = audit_system_isolation()
        assert report.scoped_table_count == 3

    def test_E4_global_count_is_two(self) -> None:
        report = audit_system_isolation()
        assert report.global_table_count == 2

    def test_E5_policies_list_has_five_entries(self) -> None:
        report = audit_system_isolation()
        assert len(report.policies) == 5

    def test_E6_no_violations(self) -> None:
        report = audit_system_isolation()
        assert report.has_violations is False

    def test_E7_all_scoped_policies_require_filter(self) -> None:
        report = audit_system_isolation()
        for policy in report.policies:
            if policy.scope == TableScope.TENANT_SCOPED:
                assert policy.requires_filter is True, (
                    f"Table {policy.table_name!r} is TENANT_SCOPED "
                    f"but requires_filter is False"
                )

    def test_E8_all_global_policies_do_not_require_filter(self) -> None:
        report = audit_system_isolation()
        for policy in report.policies:
            if policy.scope == TableScope.GLOBAL:
                assert policy.requires_filter is False


# ---------------------------------------------------------------------------
# Group F — CrossTenantLeakResult properties
# ---------------------------------------------------------------------------

class TestCrossTenantLeakResult:

    def test_F1_is_frozen(self) -> None:
        r = CrossTenantLeakResult(
            tenant_requesting=TENANT_A,
            tenant_target=TENANT_B,
            leaked=False,
            leaked_row_count=0,
            detail="clean",
        )
        with pytest.raises((AttributeError, TypeError)):
            r.leaked = True  # type: ignore

    def test_F2_leaked_false_when_zero_rows(self) -> None:
        r = CrossTenantLeakResult(
            tenant_requesting=TENANT_A,
            tenant_target=TENANT_B,
            leaked=False,
            leaked_row_count=0,
            detail="clean",
        )
        assert r.leaked is False
        assert r.leaked_row_count == 0


# ---------------------------------------------------------------------------
# Group G — SystemIsolationReport properties
# ---------------------------------------------------------------------------

class TestSystemIsolationReport:

    def test_G1_all_compliant_false_when_violations_exist(self) -> None:
        report = SystemIsolationReport(
            all_compliant=False,
            scoped_table_count=3,
            global_table_count=2,
            violations=["mystery_table"],
            policies=[],
        )
        assert report.has_violations is True
        assert report.all_compliant is False

    def test_G2_has_violations_false_when_empty(self) -> None:
        report = SystemIsolationReport(
            all_compliant=True,
            scoped_table_count=3,
            global_table_count=2,
            violations=[],
            policies=[],
        )
        assert report.has_violations is False

    def test_G3_is_frozen(self) -> None:
        report = audit_system_isolation()
        with pytest.raises((AttributeError, TypeError)):
            report.all_compliant = False  # type: ignore


# ---------------------------------------------------------------------------
# Group H — Integration with Phase 81 tenant_isolation_checker
# ---------------------------------------------------------------------------

class TestIntegrationWithPhase81:

    def test_H1_phase81_query_shape_matches_enforcer_tables(self) -> None:
        """
        Phase 81 uses query dicts with 'table' + 'filters'.
        Phase 87 knows which tables require tenant filtering.
        Verify that queries on TENANT_SCOPED tables must include tenant_id.
        """
        from adapters.ota.tenant_isolation_checker import (
            audit_tenant_isolation,
            check_query_has_tenant_filter,
        )

        for table_name in TENANT_SCOPED_TABLES:
            with_filter = {"table": table_name, "filters": {"tenant_id": TENANT_A}}
            without_filter = {"table": table_name, "filters": {}}

            assert check_query_has_tenant_filter(with_filter) is True
            assert check_query_has_tenant_filter(without_filter) is False

    def test_H2_global_tables_dont_require_tenant_filter(self) -> None:
        """Global tables are intentionally query-able without tenant_id."""
        from adapters.ota.tenant_isolation_checker import check_query_has_tenant_filter

        for table_name in GLOBAL_TABLES:
            without_filter = {"table": table_name, "filters": {}}
            policy = get_table_policy(table_name)
            assert policy is not None
            assert policy.requires_filter is False

    def test_H3_full_router_audit_with_correct_scoped_queries(self) -> None:
        from adapters.ota.tenant_isolation_checker import audit_tenant_isolation

        queries = [
            {"table": t, "filters": {"tenant_id": TENANT_A}}
            for t in TENANT_SCOPED_TABLES
        ]
        report = audit_tenant_isolation("test_router", queries)
        assert report.all_isolated is True

    def test_H4_router_audit_with_global_table_query_counted_as_unfiltered(self) -> None:
        from adapters.ota.tenant_isolation_checker import audit_tenant_isolation

        queries = [
            {"table": "ota_dead_letter", "filters": {}},  # global — expected unfiltered
        ]
        report = audit_tenant_isolation("admin_router", queries)
        # Global queries are unfiltered by design — audit correctly shows this
        assert report.unfiltered_queries == 1


# ---------------------------------------------------------------------------
# Group I — Invariants
# ---------------------------------------------------------------------------

class TestInvariants:

    def test_I1_check_cross_tenant_leak_never_raises(self) -> None:
        result = check_cross_tenant_leak(TENANT_A, TENANT_B, None)  # type: ignore
        assert isinstance(result, CrossTenantLeakResult)

    def test_I2_check_cross_tenant_leak_never_raises_on_malformed_rows(self) -> None:
        rows = [None, {}, "garbage", 42]  # type: ignore
        result = check_cross_tenant_leak(TENANT_A, TENANT_B, rows)
        assert isinstance(result, CrossTenantLeakResult)

    def test_I3_audit_system_isolation_never_raises(self) -> None:
        report = audit_system_isolation()
        assert isinstance(report, SystemIsolationReport)

    def test_I4_no_write_methods_on_report(self) -> None:
        report = audit_system_isolation()
        assert not hasattr(report, "write")
        assert not hasattr(report, "execute")
        assert not hasattr(report, "save")

    def test_I5_tenant_scoped_tables_cannot_appear_in_global_set(self) -> None:
        overlap = TENANT_SCOPED_TABLES & GLOBAL_TABLES
        assert overlap == set(), f"Tables appear in both sets: {overlap}"

    def test_I6_all_registry_tables_have_policy(self) -> None:
        from adapters.ota.tenant_isolation_enforcer import _POLICIES
        for table_name in TABLE_REGISTRY:
            assert table_name in _POLICIES, (
                f"Table {table_name!r} in TABLE_REGISTRY has no entry in _POLICIES"
            )
