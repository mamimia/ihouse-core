"""
Contract tests for reconciliation_model.py — Phase 89

Groups:
  A — ReconciliationFindingKind enum (7 values, string enum)
  B — ReconciliationSeverity enum (3 values, canonical CRITICAL/WARNING/INFO)
  C — FINDING_SEVERITY mapping (all 7 kinds mapped, correct severities)
  D — CORRECTION_HINTS mapping (all 7 kinds mapped, non-empty strings)
  E — ReconciliationFinding.build() factory (id, severity, hint auto-assigned)
  F — finding_id determinism and collision behaviour
  G — ReconciliationReport.build() (count derivation, partial flag)
  H — ReconciliationReport helper methods (has_critical, has_warnings, is_clean)
  I — ReconciliationSummary.from_report() (top_kind logic, delegation)
"""

import pytest
import hashlib
from adapters.ota.reconciliation_model import (
    ReconciliationFindingKind,
    ReconciliationSeverity,
    FINDING_SEVERITY,
    CORRECTION_HINTS,
    ReconciliationFinding,
    ReconciliationReport,
    ReconciliationSummary,
    _make_finding_id,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TENANT = "tenant-123"
PROVIDER = "bookingcom"
BOOKING_ID = "bookingcom_bk12345"
DETECTED_AT = "2026-03-09T08:00:00Z"


def _finding(
    kind: ReconciliationFindingKind,
    booking_id: str = BOOKING_ID,
) -> ReconciliationFinding:
    return ReconciliationFinding.build(
        kind=kind,
        booking_id=booking_id,
        tenant_id=TENANT,
        provider=PROVIDER,
        description=f"Test finding for {kind.value}",
        detected_at=DETECTED_AT,
    )


def _report(findings, total=10, partial=False) -> ReconciliationReport:
    return ReconciliationReport.build(
        tenant_id=TENANT,
        generated_at=DETECTED_AT,
        findings=findings,
        total_checked=total,
        partial=partial,
    )


# ---------------------------------------------------------------------------
# Group A — ReconciliationFindingKind enum
# ---------------------------------------------------------------------------

class TestGroupAFindingKindEnum:

    def test_a1_all_seven_kinds_exist(self):
        kinds = list(ReconciliationFindingKind)
        assert len(kinds) == 7

    def test_a2_kinds_are_string_enum(self):
        for kind in ReconciliationFindingKind:
            assert isinstance(kind.value, str)

    def test_a3_booking_missing_internally_value(self):
        assert ReconciliationFindingKind.BOOKING_MISSING_INTERNALLY.value == "BOOKING_MISSING_INTERNALLY"

    def test_a4_booking_status_mismatch_value(self):
        assert ReconciliationFindingKind.BOOKING_STATUS_MISMATCH.value == "BOOKING_STATUS_MISMATCH"

    def test_a5_date_mismatch_value(self):
        assert ReconciliationFindingKind.DATE_MISMATCH.value == "DATE_MISMATCH"

    def test_a6_financial_facts_missing_value(self):
        assert ReconciliationFindingKind.FINANCIAL_FACTS_MISSING.value == "FINANCIAL_FACTS_MISSING"

    def test_a7_financial_amount_drift_value(self):
        assert ReconciliationFindingKind.FINANCIAL_AMOUNT_DRIFT.value == "FINANCIAL_AMOUNT_DRIFT"

    def test_a8_provider_drift_value(self):
        assert ReconciliationFindingKind.PROVIDER_DRIFT.value == "PROVIDER_DRIFT"

    def test_a9_stale_booking_value(self):
        assert ReconciliationFindingKind.STALE_BOOKING.value == "STALE_BOOKING"

    def test_a10_kind_usable_as_string_key(self):
        k = ReconciliationFindingKind("DATE_MISMATCH")
        assert k == ReconciliationFindingKind.DATE_MISMATCH


# ---------------------------------------------------------------------------
# Group B — ReconciliationSeverity enum
# ---------------------------------------------------------------------------

class TestGroupBSeverityEnum:

    def test_b1_three_severities_exist(self):
        assert len(list(ReconciliationSeverity)) == 3

    def test_b2_critical_value(self):
        assert ReconciliationSeverity.CRITICAL.value == "CRITICAL"

    def test_b3_warning_value(self):
        assert ReconciliationSeverity.WARNING.value == "WARNING"

    def test_b4_info_value(self):
        assert ReconciliationSeverity.INFO.value == "INFO"

    def test_b5_severity_is_string_enum(self):
        for sev in ReconciliationSeverity:
            assert isinstance(sev.value, str)


# ---------------------------------------------------------------------------
# Group C — FINDING_SEVERITY mapping
# ---------------------------------------------------------------------------

class TestGroupCFindingSeverityMap:

    def test_c1_all_kinds_mapped(self):
        for kind in ReconciliationFindingKind:
            assert kind in FINDING_SEVERITY

    def test_c2_booking_missing_is_critical(self):
        assert FINDING_SEVERITY[ReconciliationFindingKind.BOOKING_MISSING_INTERNALLY] == ReconciliationSeverity.CRITICAL

    def test_c3_status_mismatch_is_critical(self):
        assert FINDING_SEVERITY[ReconciliationFindingKind.BOOKING_STATUS_MISMATCH] == ReconciliationSeverity.CRITICAL

    def test_c4_date_mismatch_is_critical(self):
        assert FINDING_SEVERITY[ReconciliationFindingKind.DATE_MISMATCH] == ReconciliationSeverity.CRITICAL

    def test_c5_financial_missing_is_warning(self):
        assert FINDING_SEVERITY[ReconciliationFindingKind.FINANCIAL_FACTS_MISSING] == ReconciliationSeverity.WARNING

    def test_c6_financial_drift_is_warning(self):
        assert FINDING_SEVERITY[ReconciliationFindingKind.FINANCIAL_AMOUNT_DRIFT] == ReconciliationSeverity.WARNING

    def test_c7_provider_drift_is_warning(self):
        assert FINDING_SEVERITY[ReconciliationFindingKind.PROVIDER_DRIFT] == ReconciliationSeverity.WARNING

    def test_c8_stale_booking_is_info(self):
        assert FINDING_SEVERITY[ReconciliationFindingKind.STALE_BOOKING] == ReconciliationSeverity.INFO

    def test_c9_exactly_seven_mappings(self):
        assert len(FINDING_SEVERITY) == 7


# ---------------------------------------------------------------------------
# Group D — CORRECTION_HINTS mapping
# ---------------------------------------------------------------------------

class TestGroupDCorrectionHints:

    def test_d1_all_kinds_have_hint(self):
        for kind in ReconciliationFindingKind:
            assert kind in CORRECTION_HINTS

    def test_d2_all_hints_are_non_empty_strings(self):
        for kind, hint in CORRECTION_HINTS.items():
            assert isinstance(hint, str)
            assert len(hint) > 10, f"Hint for {kind} is suspiciously short"

    def test_d3_missing_internally_hint_mentions_webhooks(self):
        hint = CORRECTION_HINTS[ReconciliationFindingKind.BOOKING_MISSING_INTERNALLY]
        assert "webhooks" in hint.lower() or "/webhooks" in hint

    def test_d4_status_mismatch_hint_mentions_apply_envelope(self):
        hint = CORRECTION_HINTS[ReconciliationFindingKind.BOOKING_STATUS_MISMATCH]
        assert "apply_envelope" in hint

    def test_d5_date_mismatch_hint_mentions_amended(self):
        hint = CORRECTION_HINTS[ReconciliationFindingKind.DATE_MISMATCH]
        assert "AMENDED" in hint or "amended" in hint.lower()

    def test_d6_stale_booking_hint_mentions_terminal(self):
        hint = CORRECTION_HINTS[ReconciliationFindingKind.STALE_BOOKING]
        assert "terminal" in hint.lower() or "canceled" in hint.lower()

    def test_d7_exactly_seven_hints(self):
        assert len(CORRECTION_HINTS) == 7


# ---------------------------------------------------------------------------
# Group E — ReconciliationFinding.build() factory
# ---------------------------------------------------------------------------

class TestGroupEFindingBuild:

    def test_e1_build_returns_finding_instance(self):
        f = _finding(ReconciliationFindingKind.DATE_MISMATCH)
        assert isinstance(f, ReconciliationFinding)

    def test_e2_finding_is_frozen(self):
        f = _finding(ReconciliationFindingKind.DATE_MISMATCH)
        with pytest.raises((AttributeError, TypeError)):
            f.kind = ReconciliationFindingKind.STALE_BOOKING  # type: ignore

    def test_e3_kind_assigned_correctly(self):
        f = _finding(ReconciliationFindingKind.DATE_MISMATCH)
        assert f.kind == ReconciliationFindingKind.DATE_MISMATCH

    def test_e4_severity_auto_assigned(self):
        f = _finding(ReconciliationFindingKind.DATE_MISMATCH)
        assert f.severity == ReconciliationSeverity.CRITICAL

    def test_e5_correction_hint_auto_assigned(self):
        f = _finding(ReconciliationFindingKind.DATE_MISMATCH)
        assert "AMENDED" in f.correction_hint or "amended" in f.correction_hint.lower()

    def test_e6_finding_id_is_12_hex_chars(self):
        f = _finding(ReconciliationFindingKind.DATE_MISMATCH)
        assert len(f.finding_id) == 12
        int(f.finding_id, 16)  # raises if not valid hex

    def test_e7_booking_id_stored(self):
        f = _finding(ReconciliationFindingKind.DATE_MISMATCH)
        assert f.booking_id == BOOKING_ID

    def test_e8_tenant_id_stored(self):
        f = _finding(ReconciliationFindingKind.DATE_MISMATCH)
        assert f.tenant_id == TENANT

    def test_e9_provider_stored(self):
        f = _finding(ReconciliationFindingKind.DATE_MISMATCH)
        assert f.provider == PROVIDER

    def test_e10_internal_value_defaults_none(self):
        f = _finding(ReconciliationFindingKind.DATE_MISMATCH)
        assert f.internal_value is None

    def test_e11_external_value_defaults_none(self):
        f = _finding(ReconciliationFindingKind.DATE_MISMATCH)
        assert f.external_value is None

    def test_e12_internal_and_external_values_can_be_set(self):
        f = ReconciliationFinding.build(
            kind=ReconciliationFindingKind.DATE_MISMATCH,
            booking_id=BOOKING_ID,
            tenant_id=TENANT,
            provider=PROVIDER,
            description="date mismatch",
            detected_at=DETECTED_AT,
            internal_value="2026-04-01",
            external_value="2026-04-03",
        )
        assert f.internal_value == "2026-04-01"
        assert f.external_value == "2026-04-03"

    @pytest.mark.parametrize("kind", list(ReconciliationFindingKind))
    def test_e13_all_kinds_build_successfully(self, kind):
        f = _finding(kind)
        assert f.kind == kind
        assert f.severity == FINDING_SEVERITY[kind]
        assert f.correction_hint == CORRECTION_HINTS[kind]


# ---------------------------------------------------------------------------
# Group F — finding_id determinism
# ---------------------------------------------------------------------------

class TestGroupFFindingIdDeterminism:

    def test_f1_same_kind_same_booking_produces_same_id(self):
        id1 = _make_finding_id(ReconciliationFindingKind.DATE_MISMATCH, BOOKING_ID)
        id2 = _make_finding_id(ReconciliationFindingKind.DATE_MISMATCH, BOOKING_ID)
        assert id1 == id2

    def test_f2_different_kind_same_booking_produces_different_id(self):
        id1 = _make_finding_id(ReconciliationFindingKind.DATE_MISMATCH, BOOKING_ID)
        id2 = _make_finding_id(ReconciliationFindingKind.STALE_BOOKING, BOOKING_ID)
        assert id1 != id2

    def test_f3_same_kind_different_booking_produces_different_id(self):
        id1 = _make_finding_id(ReconciliationFindingKind.DATE_MISMATCH, "bookingcom_aaa")
        id2 = _make_finding_id(ReconciliationFindingKind.DATE_MISMATCH, "bookingcom_bbb")
        assert id1 != id2

    def test_f4_finding_id_matches_sha256_formula(self):
        kind = ReconciliationFindingKind.DATE_MISMATCH
        booking_id = BOOKING_ID
        expected = hashlib.sha256(f"{kind.value}:{booking_id}".encode()).hexdigest()[:12]
        assert _make_finding_id(kind, booking_id) == expected

    def test_f5_finding_id_is_lowercase_hex(self):
        result = _make_finding_id(ReconciliationFindingKind.PROVIDER_DRIFT, BOOKING_ID)
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)

    def test_f6_build_factory_uses_make_finding_id(self):
        kind = ReconciliationFindingKind.DATE_MISMATCH
        f = _finding(kind)
        expected = _make_finding_id(kind, BOOKING_ID)
        assert f.finding_id == expected


# ---------------------------------------------------------------------------
# Group G — ReconciliationReport.build()
# ---------------------------------------------------------------------------

class TestGroupGReportBuild:

    def test_g1_empty_findings_all_counts_zero(self):
        r = _report([])
        assert r.critical_count == 0
        assert r.warning_count == 0
        assert r.info_count == 0

    def test_g2_critical_count_derived(self):
        findings = [
            _finding(ReconciliationFindingKind.DATE_MISMATCH),
            _finding(ReconciliationFindingKind.BOOKING_STATUS_MISMATCH),
        ]
        r = _report(findings)
        assert r.critical_count == 2

    def test_g3_warning_count_derived(self):
        findings = [
            _finding(ReconciliationFindingKind.FINANCIAL_FACTS_MISSING),
            _finding(ReconciliationFindingKind.PROVIDER_DRIFT),
        ]
        r = _report(findings)
        assert r.warning_count == 2

    def test_g4_info_count_derived(self):
        findings = [_finding(ReconciliationFindingKind.STALE_BOOKING)]
        r = _report(findings)
        assert r.info_count == 1

    def test_g5_mixed_findings_counts_correct(self):
        findings = [
            _finding(ReconciliationFindingKind.DATE_MISMATCH),          # CRITICAL
            _finding(ReconciliationFindingKind.FINANCIAL_FACTS_MISSING), # WARNING
            _finding(ReconciliationFindingKind.STALE_BOOKING),           # INFO
        ]
        r = _report(findings)
        assert r.critical_count == 1
        assert r.warning_count == 1
        assert r.info_count == 1

    def test_g6_tenant_id_stored(self):
        r = _report([])
        assert r.tenant_id == TENANT

    def test_g7_generated_at_stored(self):
        r = _report([])
        assert r.generated_at == DETECTED_AT

    def test_g8_total_checked_stored(self):
        r = _report([], total=42)
        assert r.total_checked == 42

    def test_g9_partial_defaults_false(self):
        r = _report([])
        assert r.partial is False

    def test_g10_partial_can_be_set_true(self):
        r = _report([], partial=True)
        assert r.partial is True

    def test_g11_findings_list_stored(self):
        findings = [_finding(ReconciliationFindingKind.STALE_BOOKING)]
        r = _report(findings)
        assert len(r.findings) == 1


# ---------------------------------------------------------------------------
# Group H — ReconciliationReport helper methods
# ---------------------------------------------------------------------------

class TestGroupHReportHelpers:

    def test_h1_is_clean_true_when_no_findings(self):
        r = _report([])
        assert r.is_clean() is True

    def test_h2_is_clean_false_when_findings_exist(self):
        r = _report([_finding(ReconciliationFindingKind.STALE_BOOKING)])
        assert r.is_clean() is False

    def test_h3_has_critical_true_when_critical_finding(self):
        r = _report([_finding(ReconciliationFindingKind.DATE_MISMATCH)])
        assert r.has_critical() is True

    def test_h4_has_critical_false_when_only_warnings(self):
        r = _report([_finding(ReconciliationFindingKind.FINANCIAL_FACTS_MISSING)])
        assert r.has_critical() is False

    def test_h5_has_warnings_true_when_warning_finding(self):
        r = _report([_finding(ReconciliationFindingKind.PROVIDER_DRIFT)])
        assert r.has_warnings() is True

    def test_h6_has_warnings_false_when_only_info(self):
        r = _report([_finding(ReconciliationFindingKind.STALE_BOOKING)])
        assert r.has_warnings() is False

    def test_h7_has_critical_false_on_empty(self):
        r = _report([])
        assert r.has_critical() is False

    def test_h8_has_warnings_false_on_empty(self):
        r = _report([])
        assert r.has_warnings() is False


# ---------------------------------------------------------------------------
# Group I — ReconciliationSummary.from_report()
# ---------------------------------------------------------------------------

class TestGroupISummaryFromReport:

    def test_i1_summary_is_frozen(self):
        r = _report([])
        s = ReconciliationSummary.from_report(r)
        with pytest.raises((AttributeError, TypeError)):
            s.finding_count = 99  # type: ignore

    def test_i2_empty_report_all_false_zero(self):
        r = _report([])
        s = ReconciliationSummary.from_report(r)
        assert s.has_critical is False
        assert s.has_warnings is False
        assert s.finding_count == 0
        assert s.top_kind is None

    def test_i3_finding_count_correct(self):
        findings = [
            _finding(ReconciliationFindingKind.STALE_BOOKING),
            _finding(ReconciliationFindingKind.DATE_MISMATCH),
        ]
        r = _report(findings)
        s = ReconciliationSummary.from_report(r)
        assert s.finding_count == 2

    def test_i4_has_critical_propagated(self):
        r = _report([_finding(ReconciliationFindingKind.DATE_MISMATCH)])
        s = ReconciliationSummary.from_report(r)
        assert s.has_critical is True

    def test_i5_has_warnings_propagated(self):
        r = _report([_finding(ReconciliationFindingKind.FINANCIAL_FACTS_MISSING)])
        s = ReconciliationSummary.from_report(r)
        assert s.has_warnings is True

    def test_i6_top_kind_single_finding(self):
        r = _report([_finding(ReconciliationFindingKind.DATE_MISMATCH)])
        s = ReconciliationSummary.from_report(r)
        assert s.top_kind == "DATE_MISMATCH"

    def test_i7_top_kind_most_frequent(self):
        findings = [
            _finding(ReconciliationFindingKind.STALE_BOOKING),
            _finding(ReconciliationFindingKind.STALE_BOOKING),
            _finding(ReconciliationFindingKind.DATE_MISMATCH),
        ]
        r = _report(findings)
        s = ReconciliationSummary.from_report(r)
        assert s.top_kind == "STALE_BOOKING"

    def test_i8_top_kind_tie_broken_by_critical_first(self):
        """When two kinds are equally frequent, CRITICAL wins over INFO."""
        findings = [
            _finding(ReconciliationFindingKind.DATE_MISMATCH),      # CRITICAL
            _finding(ReconciliationFindingKind.STALE_BOOKING),       # INFO
        ]
        r = _report(findings)
        s = ReconciliationSummary.from_report(r)
        assert s.top_kind == "DATE_MISMATCH"

    def test_i9_counts_delegated_from_report(self):
        findings = [
            _finding(ReconciliationFindingKind.DATE_MISMATCH),
            _finding(ReconciliationFindingKind.FINANCIAL_FACTS_MISSING),
            _finding(ReconciliationFindingKind.STALE_BOOKING),
        ]
        r = _report(findings)
        s = ReconciliationSummary.from_report(r)
        assert s.critical_count == 1
        assert s.warning_count == 1
        assert s.info_count == 1

    def test_i10_partial_flag_propagated(self):
        r = _report([], partial=True)
        s = ReconciliationSummary.from_report(r)
        assert s.partial is True

    def test_i11_tenant_id_propagated(self):
        r = _report([])
        s = ReconciliationSummary.from_report(r)
        assert s.tenant_id == TENANT

    def test_i12_generated_at_propagated(self):
        r = _report([])
        s = ReconciliationSummary.from_report(r)
        assert s.generated_at == DETECTED_AT
