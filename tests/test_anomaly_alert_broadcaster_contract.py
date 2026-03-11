"""
Phase 226 — Anomaly Alert Broadcaster — Contract Tests

Tests cover:
    _detect_financial_flags:
        - clean record → no flags
        - PARTIAL confidence → PARTIAL_CONFIDENCE
        - None net → MISSING_NET_TO_PROPERTY
        - commission > 25% → COMMISSION_HIGH (HIGH severity)
        - net < 0 → NET_NEGATIVE (HIGH severity)
        - UNKNOWN confidence + no total → UNKNOWN_LIFECYCLE

    _compute_health_score:
        - no alerts → 100
        - 1 CRITICAL → 80
        - 3 CRITICAL → 40 (capped at -60)
        - mix of severities → reduces correctly

    _build_heuristic_summary:
        - no alerts → "All clear" / health score
        - critical alerts → mentions count
        - top alert title present

    POST /ai/copilot/anomaly-alerts:
        - 200 with empty body → all domains, all alerts
        - 400 for invalid domain
        - 400 for invalid severity_filter
        - severity_filter CRITICAL returns only CRITICAL
        - alerts sorted: CRITICAL before HIGH before MEDIUM
        - health_score present and in 0-100
        - generated_by = 'heuristic' without LLM key
        - generated_by = 'llm' with mock LLM
        - empty tasks/financial/bookings → 200 empty alerts, health=100
        - response shape: all required top-level fields
        - individual alert shape: required fields
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.anomaly_alert_broadcaster import (
    _detect_financial_flags,
    _compute_health_score,
    _build_heuristic_summary,
)

TENANT = "tenant-test"
NOW = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fin_row(**kwargs) -> dict:
    base = {
        "booking_id": "B001",
        "provider": "airbnb",
        "currency": "THB",
        "total_price": 10000,
        "ota_commission": 1500,
        "net_to_property": 8500,
        "source_confidence": "FULL",
        "recorded_at": NOW.isoformat(),
    }
    base.update(kwargs)
    return base


def _task_row(**kwargs) -> dict:
    base = {
        "task_id": "t001",
        "kind": "CLEANING",
        "title": "Clean villa",
        "priority": "HIGH",
        "status": "PENDING",
        "ack_sla_minutes": 15,
        "worker_role": "CLEANER",
        "property_id": "prop-1",
        "booking_id": "B001",
        "created_at": (NOW - timedelta(minutes=30)).isoformat(),
    }
    base.update(kwargs)
    return base


def _booking_row(**kwargs) -> dict:
    base = {
        "booking_id": "B002",
        "provider": "booking.com",
        "source_confidence": "PARTIAL",
        "lifecycle_status": "ACTIVE",
        "check_in": "2026-03-20",
        "check_out": "2026-03-25",
        "updated_at": (NOW - timedelta(hours=30)).isoformat(),
    }
    base.update(kwargs)
    return base


def _empty_db() -> MagicMock:
    db = MagicMock()
    t = MagicMock()
    for m in ("select", "eq", "in_", "lt", "order", "limit", "execute"):
        getattr(t, m).return_value = t
    result = MagicMock()
    result.data = []
    t.execute.return_value = result
    db.table.return_value = t
    return db


def _db_with(tasks=None, financials=None, bookings=None) -> MagicMock:
    """Returns a mock DB. Different tables return different data."""
    db = MagicMock()

    def table_fn(name):
        t = MagicMock()
        for m in ("select", "eq", "in_", "lt", "order", "limit", "execute"):
            getattr(t, m).return_value = t
        result = MagicMock()
        if name == "tasks":
            result.data = tasks or []
        elif name == "booking_financial_facts":
            result.data = financials or []
        elif name == "booking_state":
            result.data = bookings or []
        else:
            result.data = []
        t.execute.return_value = result
        return t

    db.table.side_effect = table_fn
    return db


# ---------------------------------------------------------------------------
# _detect_financial_flags
# ---------------------------------------------------------------------------

class TestDetectFinancialFlags:
    def test_clean_record_no_flags(self):
        flags = _detect_financial_flags(_fin_row())
        assert flags == []

    def test_partial_confidence_flag(self):
        row = _fin_row(source_confidence="PARTIAL")
        flags = _detect_financial_flags(row)
        names = [f[0] for f in flags]
        assert "PARTIAL_CONFIDENCE" in names

    def test_missing_net_flag(self):
        row = _fin_row(net_to_property=None)
        flags = _detect_financial_flags(row)
        names = [f[0] for f in flags]
        assert "MISSING_NET_TO_PROPERTY" in names

    def test_commission_high_flag_severity_high(self):
        row = _fin_row(total_price=10000, ota_commission=3000, net_to_property=7000)
        flags = _detect_financial_flags(row)
        flag_map = {f[0]: f[1] for f in flags}
        assert "COMMISSION_HIGH" in flag_map
        assert flag_map["COMMISSION_HIGH"] == "HIGH"

    def test_net_negative_flag_severity_high(self):
        row = _fin_row(net_to_property=-500)
        flags = _detect_financial_flags(row)
        flag_map = {f[0]: f[1] for f in flags}
        assert "NET_NEGATIVE" in flag_map
        assert flag_map["NET_NEGATIVE"] == "HIGH"

    def test_unknown_lifecycle_flag(self):
        row = _fin_row(source_confidence="UNKNOWN", total_price=None)
        flags = _detect_financial_flags(row)
        names = [f[0] for f in flags]
        assert "UNKNOWN_LIFECYCLE" in names


# ---------------------------------------------------------------------------
# _compute_health_score
# ---------------------------------------------------------------------------

class TestComputeHealthScore:
    def _alert(self, severity: str) -> dict:
        return {"severity": severity, "_priority_order": 0}

    def test_no_alerts_returns_100(self):
        assert _compute_health_score([]) == 100

    def test_one_critical_returns_80(self):
        score = _compute_health_score([self._alert("CRITICAL")])
        assert score == 80

    def test_three_critical_caps_deduction(self):
        alerts = [self._alert("CRITICAL")] * 3
        score = _compute_health_score(alerts)
        assert score == 40  # -60 cap, 100 - 60 = 40

    def test_mixed_severities(self):
        alerts = [
            self._alert("CRITICAL"),
            self._alert("HIGH"),
            self._alert("MEDIUM"),
        ]
        score = _compute_health_score(alerts)
        # 100 - 20 (CRITICAL) - 10 (HIGH) - 3 (MEDIUM) = 67
        assert score == 67

    def test_score_capped_by_per_severity_cap(self):
        """10 CRITICALs: cap is -60, so score = 40 (not 0).
        Health score is always non-negative."""
        alerts = [self._alert("CRITICAL")] * 10
        score = _compute_health_score(alerts)
        assert score == 40  # 100 - 60 (cap for CRITICAL)
        assert score >= 0

    def test_no_alerts_returns_all_clear(self):
        text = _build_heuristic_summary([], 100, {"tasks", "financial", "bookings"})
        assert "100" in text
        assert "clear" in text.lower()

    def test_critical_count_mentioned(self):
        alerts = [
            {"severity": "CRITICAL", "title": "SLA Breach: Clean Villa"},
            {"severity": "HIGH", "title": "Financial Anomaly"},
        ]
        text = _build_heuristic_summary(alerts, 70, {"tasks", "financial"})
        assert "1 CRITICAL" in text or "CRITICAL" in text

    def test_top_alert_title_present(self):
        alerts = [
            {"severity": "CRITICAL", "title": "SLA Breach: Clean Villa"},
        ]
        text = _build_heuristic_summary(alerts, 80, {"tasks"})
        assert "SLA Breach: Clean Villa" in text


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

class TestAnomalyAlertsEndpoint:
    def _app(self):
        from fastapi import FastAPI
        from api.anomaly_alert_broadcaster import router
        app = FastAPI()
        app.include_router(router)
        return app

    def test_200_with_empty_body(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.anomaly_alert_broadcaster as ab

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        with patch("api.anomaly_alert_broadcaster.jwt_auth", return_value=TENANT), \
             patch.object(ab, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).post("/ai/copilot/anomaly-alerts", json={}, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200

    def test_400_invalid_domain(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.anomaly_alert_broadcaster as ab

        app = self._app()
        with patch("api.anomaly_alert_broadcaster.jwt_auth", return_value=TENANT), \
             patch.object(ab, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).post(
                "/ai/copilot/anomaly-alerts",
                json={"domains": ["invalid_domain"]},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 400

    def test_400_invalid_severity_filter(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.anomaly_alert_broadcaster as ab

        app = self._app()
        with patch("api.anomaly_alert_broadcaster.jwt_auth", return_value=TENANT), \
             patch.object(ab, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).post(
                "/ai/copilot/anomaly-alerts",
                json={"severity_filter": "URGENT"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 400

    def test_severity_filter_critical_only(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.anomaly_alert_broadcaster as ab

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        critical_task = _task_row(priority="CRITICAL", ack_sla_minutes=5,
                                   created_at=(NOW - timedelta(minutes=20)).isoformat())
        medium_booking = _booking_row()
        db = _db_with(tasks=[critical_task], financials=[], bookings=[medium_booking])

        with patch("api.anomaly_alert_broadcaster.jwt_auth", return_value=TENANT), \
             patch.object(ab, "_get_db", return_value=db):
            resp = TestClient(app).post(
                "/ai/copilot/anomaly-alerts",
                json={"severity_filter": "CRITICAL"},
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 200
        data = resp.json()
        for alert in data["alerts"]:
            assert alert["severity"] == "CRITICAL"

    def test_alerts_sorted_critical_first(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.anomaly_alert_broadcaster as ab

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        critical_task = _task_row(task_id="t-crit", priority="CRITICAL", ack_sla_minutes=5,
                                   created_at=(NOW - timedelta(minutes=20)).isoformat())
        high_financial = _fin_row(booking_id="B-HIGH", net_to_property=-100)

        db = _db_with(tasks=[critical_task], financials=[high_financial], bookings=[])

        with patch("api.anomaly_alert_broadcaster.jwt_auth", return_value=TENANT), \
             patch.object(ab, "_get_db", return_value=db):
            resp = TestClient(app).post("/ai/copilot/anomaly-alerts", json={}, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        alerts = resp.json()["alerts"]
        if len(alerts) >= 2:
            first_sev = alerts[0]["severity"]
            assert first_sev == "CRITICAL"

    def test_no_anomalies_health_score_100(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.anomaly_alert_broadcaster as ab

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        with patch("api.anomaly_alert_broadcaster.jwt_auth", return_value=TENANT), \
             patch.object(ab, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).post("/ai/copilot/anomaly-alerts", json={}, headers={"Authorization": "Bearer fake"})

        data = resp.json()
        assert data["health_score"] == 100
        assert data["total_alerts"] == 0
        assert "clear" in data["summary"].lower()

    def test_health_score_in_valid_range(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.anomaly_alert_broadcaster as ab

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        with patch("api.anomaly_alert_broadcaster.jwt_auth", return_value=TENANT), \
             patch.object(ab, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).post("/ai/copilot/anomaly-alerts", json={}, headers={"Authorization": "Bearer fake"})

        score = resp.json()["health_score"]
        assert 0 <= score <= 100

    def test_generated_by_heuristic_without_llm(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.anomaly_alert_broadcaster as ab

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        with patch("api.anomaly_alert_broadcaster.jwt_auth", return_value=TENANT), \
             patch.object(ab, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).post("/ai/copilot/anomaly-alerts", json={}, headers={"Authorization": "Bearer fake"})

        assert resp.json()["generated_by"] == "heuristic"

    def test_generated_by_llm_when_mock_returns_text(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.anomaly_alert_broadcaster as ab
        import services.llm_client as lc

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        app = self._app()
        critical_task = _task_row(priority="CRITICAL", ack_sla_minutes=5,
                                   created_at=(NOW - timedelta(minutes=20)).isoformat())
        db = _db_with(tasks=[critical_task], financials=[], bookings=[])

        with patch("api.anomaly_alert_broadcaster.jwt_auth", return_value=TENANT), \
             patch.object(ab, "_get_db", return_value=db), \
             patch.object(lc, "is_configured", return_value=True), \
             patch.object(lc, "generate", return_value="1 CRITICAL task SLA breached. Review task list."):
            resp = TestClient(app).post("/ai/copilot/anomaly-alerts", json={"domains": ["tasks"]},
                                        headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        assert resp.json()["generated_by"] == "llm"
        assert resp.json()["summary"] == "1 CRITICAL task SLA breached. Review task list."

    def test_response_has_all_required_fields(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.anomaly_alert_broadcaster as ab

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        with patch("api.anomaly_alert_broadcaster.jwt_auth", return_value=TENANT), \
             patch.object(ab, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).post("/ai/copilot/anomaly-alerts", json={}, headers={"Authorization": "Bearer fake"})

        data = resp.json()
        for field in ("tenant_id", "generated_by", "generated_at", "domains_scanned",
                      "total_alerts", "critical_count", "high_count", "medium_count",
                      "low_count", "health_score", "alerts", "summary"):
            assert field in data, f"Missing: {field}"

    def test_domain_filter_tasks_only(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.anomaly_alert_broadcaster as ab

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        with patch("api.anomaly_alert_broadcaster.jwt_auth", return_value=TENANT), \
             patch.object(ab, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).post(
                "/ai/copilot/anomaly-alerts",
                json={"domains": ["tasks"]},
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data["domains_scanned"]
        assert "financial" not in data["domains_scanned"]
        for alert in data["alerts"]:
            assert alert["domain"] == "tasks"

    def test_individual_alert_shape(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.anomaly_alert_broadcaster as ab

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        high_task = _task_row(
            priority="HIGH",
            ack_sla_minutes=15,
            created_at=(NOW - timedelta(minutes=30)).isoformat(),
        )
        db = _db_with(tasks=[high_task], financials=[], bookings=[])

        with patch("api.anomaly_alert_broadcaster.jwt_auth", return_value=TENANT), \
             patch.object(ab, "_get_db", return_value=db):
            resp = TestClient(app).post("/ai/copilot/anomaly-alerts", json={"domains": ["tasks"]},
                                        headers={"Authorization": "Bearer fake"})

        alerts = resp.json()["alerts"]
        assert len(alerts) >= 1
        alert = alerts[0]
        for field in ("alert_id", "severity", "domain", "title", "message",
                      "recommended_action", "reference_id", "detected_at"):
            assert field in alert, f"Missing alert field: {field}"
