"""
Phase 110 — OTA Reconciliation contract tests.

Two modules to test:
  1. reconciliation_detector.py — run_reconciliation(), detection logic
  2. admin_router.py GET /admin/reconciliation — API surface

Groups:
  A — Detector: clean tenant (no findings)
  B — Detector: FINANCIAL_FACTS_MISSING detection
  C — Detector: STALE_BOOKING detection
  D — Detector: combined findings, total_checked count
  E — Detector: edge cases (empty db, unparseable updated_at, canceled bookings not stale)
  F — API: summary response fields present (include_findings=false)
  G — API: include_findings=true inlines findings list
  H — API: auth guard, 403 on missing JWT
  I — API: Supabase failure → 500 INTERNAL_ERROR
  J — API: tenant isolation (tenant_id scoped)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Detector helpers
# ---------------------------------------------------------------------------

def _db_stub(bookings=None, financial_ids=None, fail_bookings=False, fail_financial=False):
    """
    Build a Supabase mock that returns the given data.
    fail_* causes the corresponding query to raise RuntimeError.
    """
    mock_db = MagicMock()

    booking_chain = MagicMock()
    if fail_bookings:
        booking_chain.execute.side_effect = RuntimeError("bookings DB fail")
    else:
        booking_chain.execute.return_value = MagicMock(data=bookings or [])
    booking_chain.select.return_value = booking_chain
    booking_chain.eq.return_value = booking_chain

    financial_chain = MagicMock()
    if fail_financial:
        financial_chain.execute.side_effect = RuntimeError("financial DB fail")
    else:
        fin_data = [{"booking_id": bid} for bid in (financial_ids or [])]
        financial_chain.execute.return_value = MagicMock(data=fin_data)
    financial_chain.select.return_value = financial_chain
    financial_chain.eq.return_value = financial_chain

    def _table(name):
        if name == "booking_state":
            return booking_chain
        if name == "booking_financial_facts":
            return financial_chain
        m = MagicMock()
        m.select.return_value = m
        m.eq.return_value = m
        m.execute.return_value = MagicMock(data=[])
        return m

    mock_db.table.side_effect = _table
    return mock_db


def _booking_row(
    booking_id="bookingcom_R001",
    tenant_id="tenant_test",
    source="bookingcom",
    status="active",
    updated_at=None,
):
    if updated_at is None:
        # Fresh booking updated 1 day ago
        updated_at = (datetime.now(tz=timezone.utc) - timedelta(days=1)).isoformat()
    return {
        "booking_id": booking_id,
        "tenant_id": tenant_id,
        "source": source,
        "status": status,
        "updated_at": updated_at,
    }


def _stale_updated_at(days=40):
    """Return an ISO 8601 timestamp for a date `days` days ago."""
    return (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Group A — Detector: clean tenant
# ---------------------------------------------------------------------------

class TestDetectorClean:

    def test_no_findings_when_all_bookings_have_financial_facts(self):
        from adapters.ota.reconciliation_detector import run_reconciliation

        rows = [_booking_row("bookingcom_R001"), _booking_row("bookingcom_R002")]
        db = _db_stub(
            bookings=rows,
            financial_ids={"bookingcom_R001", "bookingcom_R002"},
        )
        report = run_reconciliation("tenant_test", db)

        assert len(report.findings) == 0
        assert report.is_clean()
        assert report.total_checked == 2
        assert report.partial is False

    def test_no_findings_when_no_bookings(self):
        from adapters.ota.reconciliation_detector import run_reconciliation

        db = _db_stub(bookings=[], financial_ids=set())
        report = run_reconciliation("tenant_test", db)

        assert len(report.findings) == 0
        assert report.total_checked == 0

    def test_generated_at_is_iso8601_utc(self):
        from adapters.ota.reconciliation_detector import run_reconciliation

        db = _db_stub(bookings=[], financial_ids=set())
        report = run_reconciliation("tenant_test", db)

        # Should be parseable as ISO 8601
        dt = datetime.fromisoformat(report.generated_at.replace("Z", "+00:00"))
        assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# Group B — Detector: FINANCIAL_FACTS_MISSING
# ---------------------------------------------------------------------------

class TestDetectorFinancialFactsMissing:

    def test_single_booking_missing_facts(self):
        from adapters.ota.reconciliation_detector import run_reconciliation
        from adapters.ota.reconciliation_model import ReconciliationFindingKind, ReconciliationSeverity

        rows = [_booking_row("bookingcom_R001")]
        db = _db_stub(bookings=rows, financial_ids=set())  # no financial facts
        report = run_reconciliation("tenant_test", db)

        assert len(report.findings) == 1
        f = report.findings[0]
        assert f.kind == ReconciliationFindingKind.FINANCIAL_FACTS_MISSING
        assert f.severity == ReconciliationSeverity.WARNING
        assert f.booking_id == "bookingcom_R001"
        assert f.tenant_id == "tenant_test"
        assert f.provider == "bookingcom"
        assert f.finding_id  # non-empty
        assert "bookingcom_R001" in f.description
        assert f.correction_hint  # non-empty

    def test_multiple_bookings_some_missing_facts(self):
        from adapters.ota.reconciliation_detector import run_reconciliation

        rows = [
            _booking_row("bookingcom_R001"),
            _booking_row("bookingcom_R002"),
            _booking_row("airbnb_A003"),
        ]
        db = _db_stub(
            bookings=rows,
            financial_ids={"bookingcom_R001"},  # R002 and A003 missing
        )
        report = run_reconciliation("tenant_test", db)

        missing_ids = {f.booking_id for f in report.findings
                       if f.kind.value == "FINANCIAL_FACTS_MISSING"}
        assert missing_ids == {"bookingcom_R002", "airbnb_A003"}

    def test_finding_id_is_deterministic(self):
        from adapters.ota.reconciliation_detector import run_reconciliation

        rows = [_booking_row("bookingcom_R001")]
        db1 = _db_stub(bookings=rows, financial_ids=set())
        db2 = _db_stub(bookings=rows, financial_ids=set())

        r1 = run_reconciliation("tenant_test", db1)
        r2 = run_reconciliation("tenant_test", db2)

        assert r1.findings[0].finding_id == r2.findings[0].finding_id

    def test_canceled_booking_also_flagged_if_missing_facts(self):
        """FINANCIAL_FACTS_MISSING applies to all statuses, including canceled."""
        from adapters.ota.reconciliation_detector import run_reconciliation
        from adapters.ota.reconciliation_model import ReconciliationFindingKind

        rows = [_booking_row("bookingcom_R001", status="canceled")]
        db = _db_stub(bookings=rows, financial_ids=set())
        report = run_reconciliation("tenant_test", db)

        assert any(f.kind == ReconciliationFindingKind.FINANCIAL_FACTS_MISSING for f in report.findings)


# ---------------------------------------------------------------------------
# Group C — Detector: STALE_BOOKING
# ---------------------------------------------------------------------------

class TestDetectorStaleBooking:

    def test_active_booking_updated_40_days_ago_is_stale(self):
        from adapters.ota.reconciliation_detector import run_reconciliation
        from adapters.ota.reconciliation_model import ReconciliationFindingKind, ReconciliationSeverity

        rows = [_booking_row("bookingcom_R001", status="active", updated_at=_stale_updated_at(40))]
        db = _db_stub(bookings=rows, financial_ids={"bookingcom_R001"})
        report = run_reconciliation("tenant_test", db)

        stale = [f for f in report.findings if f.kind == ReconciliationFindingKind.STALE_BOOKING]
        assert len(stale) == 1
        assert stale[0].severity == ReconciliationSeverity.INFO
        assert stale[0].booking_id == "bookingcom_R001"
        assert "40" in stale[0].description or "days" in stale[0].description.lower()

    def test_canceled_booking_never_flagged_as_stale(self):
        """Canceled bookings are terminal — no stale check."""
        from adapters.ota.reconciliation_detector import run_reconciliation
        from adapters.ota.reconciliation_model import ReconciliationFindingKind

        rows = [_booking_row("bookingcom_R001", status="canceled", updated_at=_stale_updated_at(100))]
        db = _db_stub(bookings=rows, financial_ids={"bookingcom_R001"})
        report = run_reconciliation("tenant_test", db)

        stale = [f for f in report.findings if f.kind == ReconciliationFindingKind.STALE_BOOKING]
        assert len(stale) == 0

    def test_active_booking_updated_yesterday_is_not_stale(self):
        from adapters.ota.reconciliation_detector import run_reconciliation
        from adapters.ota.reconciliation_model import ReconciliationFindingKind

        rows = [_booking_row("bookingcom_R001", status="active",
                              updated_at=_stale_updated_at(1))]
        db = _db_stub(bookings=rows, financial_ids={"bookingcom_R001"})
        report = run_reconciliation("tenant_test", db)

        stale = [f for f in report.findings if f.kind == ReconciliationFindingKind.STALE_BOOKING]
        assert len(stale) == 0

    def test_custom_stale_days_respected(self):
        """stale_days=5 means a booking updated 10 days ago is stale."""
        from adapters.ota.reconciliation_detector import run_reconciliation
        from adapters.ota.reconciliation_model import ReconciliationFindingKind

        rows = [_booking_row("bookingcom_R001", status="active", updated_at=_stale_updated_at(10))]
        db = _db_stub(bookings=rows, financial_ids={"bookingcom_R001"})
        report = run_reconciliation("tenant_test", db, stale_days=5)

        stale = [f for f in report.findings if f.kind == ReconciliationFindingKind.STALE_BOOKING]
        assert len(stale) == 1


# ---------------------------------------------------------------------------
# Group D — Detector: combined, counts
# ---------------------------------------------------------------------------

class TestDetectorCombined:

    def test_combined_financial_and_stale_findings(self):
        from adapters.ota.reconciliation_detector import run_reconciliation
        from adapters.ota.reconciliation_model import ReconciliationFindingKind

        rows = [
            _booking_row("bookingcom_R001", status="active", updated_at=_stale_updated_at(40)),
            _booking_row("bookingcom_R002", status="active"),
        ]
        # R001 has financial facts but is stale; R002 has no financial facts
        db = _db_stub(bookings=rows, financial_ids={"bookingcom_R001"})
        report = run_reconciliation("tenant_test", db)

        kinds = {f.kind for f in report.findings}
        assert ReconciliationFindingKind.STALE_BOOKING in kinds
        assert ReconciliationFindingKind.FINANCIAL_FACTS_MISSING in kinds

    def test_report_counts_are_accurate(self):
        from adapters.ota.reconciliation_detector import run_reconciliation

        rows = [
            # FINANCIAL_FACTS_MISSING (WARNING) for R001 and R002
            _booking_row("bookingcom_R001", status="active"),
            _booking_row("bookingcom_R002", status="active"),
            # STALE_BOOKING (INFO) for R003
            _booking_row("bookingcom_R003", status="active", updated_at=_stale_updated_at(40)),
        ]
        db = _db_stub(bookings=rows, financial_ids={"bookingcom_R003"})
        report = run_reconciliation("tenant_test", db)

        assert report.total_checked == 3
        assert report.warning_count == 2   # two FINANCIAL_FACTS_MISSING
        assert report.info_count == 1      # one STALE_BOOKING
        assert report.critical_count == 0  # none — offline detector has no CRITICAL

    def test_has_critical_is_false_offline(self):
        """Offline detector can only produce WARNING + INFO — never CRITICAL."""
        from adapters.ota.reconciliation_detector import run_reconciliation

        rows = [_booking_row("bookingcom_R001", status="active", updated_at=_stale_updated_at(40))]
        db = _db_stub(bookings=rows, financial_ids=set())
        report = run_reconciliation("tenant_test", db)

        assert report.has_critical() is False


# ---------------------------------------------------------------------------
# Group E — Detector: edge cases
# ---------------------------------------------------------------------------

class TestDetectorEdgeCases:

    def test_booking_with_no_updated_at_not_flagged_stale(self):
        """If updated_at is None/missing, skip stale check — don't crash."""
        from adapters.ota.reconciliation_detector import run_reconciliation
        from adapters.ota.reconciliation_model import ReconciliationFindingKind

        rows = [{"booking_id": "bookingcom_R001", "tenant_id": "tenant_test",
                 "source": "bookingcom", "status": "active", "updated_at": None}]
        db = _db_stub(bookings=rows, financial_ids={"bookingcom_R001"})
        report = run_reconciliation("tenant_test", db)

        stale = [f for f in report.findings if f.kind == ReconciliationFindingKind.STALE_BOOKING]
        assert len(stale) == 0

    def test_unparseable_updated_at_not_flagged_stale(self):
        """Malformed updated_at is skipped, no crash."""
        from adapters.ota.reconciliation_detector import run_reconciliation
        from adapters.ota.reconciliation_model import ReconciliationFindingKind

        rows = [{"booking_id": "bookingcom_R001", "tenant_id": "tenant_test",
                 "source": "bookingcom", "status": "active", "updated_at": "not-a-date"}]
        db = _db_stub(bookings=rows, financial_ids={"bookingcom_R001"})
        report = run_reconciliation("tenant_test", db)

        stale = [f for f in report.findings if f.kind == ReconciliationFindingKind.STALE_BOOKING]
        assert len(stale) == 0

    def test_db_failure_returns_empty_report_not_exception(self):
        """If booking_state query fails, run_reconciliation returns empty report."""
        from adapters.ota.reconciliation_detector import run_reconciliation

        db = _db_stub(fail_bookings=True, fail_financial=True)
        report = run_reconciliation("tenant_test", db)

        assert len(report.findings) == 0
        assert report.total_checked == 0

    def test_z_suffix_in_updated_at_handled(self):
        """RFC 3339 'Z' suffix should be parsed correctly."""
        from adapters.ota.reconciliation_detector import run_reconciliation
        from adapters.ota.reconciliation_model import ReconciliationFindingKind

        # 40 days ago with Z suffix
        stale_ts = (datetime.now(tz=timezone.utc) - timedelta(days=40)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        rows = [_booking_row("bookingcom_R001", status="active", updated_at=stale_ts)]
        db = _db_stub(bookings=rows, financial_ids={"bookingcom_R001"})
        report = run_reconciliation("tenant_test", db)

        stale = [f for f in report.findings if f.kind == ReconciliationFindingKind.STALE_BOOKING]
        assert len(stale) == 1


# ---------------------------------------------------------------------------
# API test helpers
# ---------------------------------------------------------------------------

def _make_admin_app(mock_tenant_id="tenant_test"):
    from fastapi import FastAPI
    from api.admin_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth():
        return mock_tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Group F — API: summary response (no findings)
# ---------------------------------------------------------------------------

class TestReconciliationApiSummary:

    def _stub_reconciliation(self, findings=None, total_checked=0):
        from adapters.ota.reconciliation_model import ReconciliationReport
        report = ReconciliationReport.build(
            tenant_id="tenant_test",
            generated_at="2026-03-09T10:00:00+00:00",
            findings=findings or [],
            total_checked=total_checked,
        )
        return report

    def test_returns_200_with_summary_fields(self):
        client = _make_admin_app()
        report = self._stub_reconciliation()
        _mock_db = MagicMock()

        with patch("api.admin_router._get_supabase_client", return_value=_mock_db), \
             patch("adapters.ota.reconciliation_detector.run_reconciliation", return_value=report):
            resp = client.get("/admin/reconciliation")

        assert resp.status_code == 200
        body = resp.json()
        required = {
            "tenant_id", "generated_at", "total_checked",
            "finding_count", "critical_count", "warning_count", "info_count",
            "has_critical", "has_warnings", "top_kind", "partial",
        }
        assert required.issubset(set(body.keys()))

    def test_findings_not_in_response_by_default(self):
        client = _make_admin_app()
        report = self._stub_reconciliation()
        _mock_db = MagicMock()

        with patch("api.admin_router._get_supabase_client", return_value=_mock_db), \
             patch("adapters.ota.reconciliation_detector.run_reconciliation", return_value=report):
            resp = client.get("/admin/reconciliation")

        assert "findings" not in resp.json()

    def test_clean_report_counts_are_zero(self):
        client = _make_admin_app()
        report = self._stub_reconciliation()
        _mock_db = MagicMock()

        with patch("api.admin_router._get_supabase_client", return_value=_mock_db), \
             patch("adapters.ota.reconciliation_detector.run_reconciliation", return_value=report):
            resp = client.get("/admin/reconciliation")

        body = resp.json()
        assert body["finding_count"] == 0
        assert body["critical_count"] == 0
        assert body["warning_count"] == 0
        assert body["info_count"] == 0
        assert body["has_critical"] is False
        assert body["has_warnings"] is False
        assert body["top_kind"] is None


# ---------------------------------------------------------------------------
# Group G — API: include_findings=true
# ---------------------------------------------------------------------------

class TestReconciliationApiFindings:

    def _make_finding(self, booking_id="bookingcom_R001"):
        from adapters.ota.reconciliation_model import ReconciliationFinding, ReconciliationFindingKind
        return ReconciliationFinding.build(
            kind=ReconciliationFindingKind.FINANCIAL_FACTS_MISSING,
            booking_id=booking_id,
            tenant_id="tenant_test",
            provider="bookingcom",
            description="Test finding",
            detected_at="2026-03-09T10:00:00+00:00",
        )

    def test_include_findings_true_returns_findings_list(self):
        from adapters.ota.reconciliation_model import ReconciliationReport
        client = _make_admin_app()
        finding = self._make_finding()
        report = ReconciliationReport.build(
            tenant_id="tenant_test",
            generated_at="2026-03-09T10:00:00+00:00",
            findings=[finding],
            total_checked=1,
        )

        _mock_db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=_mock_db), \
             patch("adapters.ota.reconciliation_detector.run_reconciliation", return_value=report):
            resp = client.get("/admin/reconciliation?include_findings=true")

        body = resp.json()
        assert resp.status_code == 200
        assert "findings" in body
        assert len(body["findings"]) == 1

    def test_findings_record_schema(self):
        from adapters.ota.reconciliation_model import ReconciliationReport
        client = _make_admin_app()
        finding = self._make_finding()
        report = ReconciliationReport.build(
            tenant_id="tenant_test",
            generated_at="2026-03-09T10:00:00+00:00",
            findings=[finding],
            total_checked=1,
        )

        _mock_db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=_mock_db), \
             patch("adapters.ota.reconciliation_detector.run_reconciliation", return_value=report):
            resp = client.get("/admin/reconciliation?include_findings=true")

        rec = resp.json()["findings"][0]
        required = {
            "finding_id", "kind", "severity", "booking_id", "provider",
            "description", "detected_at", "internal_value", "external_value",
            "correction_hint",
        }
        assert required.issubset(set(rec.keys()))
        assert rec["kind"] == "FINANCIAL_FACTS_MISSING"
        assert rec["severity"] == "WARNING"

    def test_include_findings_false_no_findings_key(self):
        from adapters.ota.reconciliation_model import ReconciliationReport
        client = _make_admin_app()
        finding = self._make_finding()
        report = ReconciliationReport.build(
            tenant_id="tenant_test",
            generated_at="2026-03-09T10:00:00+00:00",
            findings=[finding],
            total_checked=1,
        )

        _mock_db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=_mock_db), \
             patch("adapters.ota.reconciliation_detector.run_reconciliation", return_value=report):
            resp = client.get("/admin/reconciliation?include_findings=false")

        assert "findings" not in resp.json()


# ---------------------------------------------------------------------------
# Group H — API: auth guard
# ---------------------------------------------------------------------------

class TestReconciliationApiAuth:

    def test_missing_auth_returns_403(self):
        from fastapi import FastAPI, HTTPException
        from api.admin_router import router
        from api.auth import jwt_auth

        app = FastAPI()

        async def _reject():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject
        app.include_router(router)
        client = TestClient(app)

        resp = client.get("/admin/reconciliation")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Group I — API: error handling
# ---------------------------------------------------------------------------

class TestReconciliationApiErrors:

    def test_detector_exception_returns_500(self):
        client = _make_admin_app()
        _mock_db = MagicMock()

        with patch("api.admin_router._get_supabase_client", return_value=_mock_db), \
             patch("adapters.ota.reconciliation_detector.run_reconciliation", side_effect=RuntimeError("boom")):
            resp = client.get("/admin/reconciliation")

        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == "INTERNAL_ERROR"
        assert "boom" not in str(body)


# ---------------------------------------------------------------------------
# Group J — API: tenant isolation
# ---------------------------------------------------------------------------

class TestReconciliationApiTenantIsolation:

    def test_tenant_id_in_response_matches_auth(self):
        from adapters.ota.reconciliation_model import ReconciliationReport
        client = _make_admin_app(mock_tenant_id="specific_tenant")
        report = ReconciliationReport.build(
            tenant_id="specific_tenant",
            generated_at="2026-03-09T10:00:00+00:00",
            findings=[],
            total_checked=0,
        )

        _mock_db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=_mock_db), \
             patch("adapters.ota.reconciliation_detector.run_reconciliation", return_value=report):
            resp = client.get("/admin/reconciliation")

        assert resp.json()["tenant_id"] == "specific_tenant"
