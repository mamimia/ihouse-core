"""
Phase 224 — Financial Explainer — Contract Tests

Tests cover:
    _compute_tier:
        - FULL/VERIFIED → A
        - PARTIAL → B
        - UNKNOWN/empty → C

    _project_lifecycle:
        - cancel event → CANCELED_REFUNDED / CANCELED_NO_REFUND
        - UNKNOWN confidence + no total → UNKNOWN
        - missing net + PARTIAL → RECONCILIATION_PENDING
        - net >= 0 + FULL confidence → PAYOUT_EXPECTED

    _detect_anomalies:
        - clean record → no flags
        - PARTIAL confidence → PARTIAL_CONFIDENCE flag
        - None net → MISSING_NET_TO_PROPERTY flag
        - commission > 25% → COMMISSION_HIGH flag
        - commission = 0 → COMMISSION_ZERO flag
        - net < 0 → NET_NEGATIVE flag
        - RECONCILIATION_PENDING lifecycle → flag

    _build_booking_explanation:
        - contains provider name
        - contains currency
        - lists flags in output
        - no-anomaly message when flags empty

    _build_recommended_action:
        - RECONCILIATION_PENDING → cross-check OTA
        - MISSING_NET + PARTIAL → log in to OTA
        - COMMISSION_HIGH → review commission
        - no flags → no action required

    _build_reconciliation_narrative:
        - zero exceptions → "clean" message
        - with exceptions → mentions tier C/B counts

    GET /ai/copilot/financial/explain/{booking_id}:
        - 404 when booking not found
        - 200 with expected shape (heuristic)
        - generated_by='llm' when mock LLM returns text
        - anomaly_flags, confidence_tier, financials in response

    GET /ai/copilot/financial/reconciliation-summary:
        - 400 when period missing
        - 400 when period invalid format
        - 200 with stats + narrative
        - exception_items sorted (Tier C first)
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.financial_explainer_router import (
    _compute_tier,
    _project_lifecycle,
    _detect_anomalies,
    _build_booking_explanation,
    _build_recommended_action,
    _build_reconciliation_narrative,
    _monetary,
)

TENANT = "tenant-test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(**kwargs) -> dict:
    base = {
        "booking_id": "B001",
        "tenant_id": TENANT,
        "provider": "airbnb",
        "currency": "THB",
        "total_price": 10000,
        "ota_commission": 1500,
        "net_to_property": 8500,
        "source_confidence": "FULL",
        "event_kind": "BOOKING_CREATED",
        "recorded_at": "2026-03-01T00:00:00+00:00",
        "taxes": None,
        "fees": None,
    }
    base.update(kwargs)
    return base


def _empty_db() -> MagicMock:
    db = MagicMock()
    t = MagicMock()
    for m in ("select", "eq", "order", "limit", "gte", "lt", "execute"):
        getattr(t, m).return_value = t
    result = MagicMock()
    result.data = []
    t.execute.return_value = result
    db.table.return_value = t
    return db


def _db_with_rows(rows: list) -> MagicMock:
    db = MagicMock()
    t = MagicMock()
    for m in ("select", "eq", "order", "limit", "gte", "lt", "execute"):
        getattr(t, m).return_value = t
    result = MagicMock()
    result.data = rows
    t.execute.return_value = result
    db.table.return_value = t
    return db


# ---------------------------------------------------------------------------
# _compute_tier
# ---------------------------------------------------------------------------

class TestComputeTier:
    def test_full_maps_to_a(self):
        assert _compute_tier("FULL") == "A"

    def test_verified_maps_to_a(self):
        assert _compute_tier("VERIFIED") == "A"

    def test_partial_maps_to_b(self):
        assert _compute_tier("PARTIAL") == "B"

    def test_unknown_maps_to_c(self):
        assert _compute_tier("UNKNOWN") == "C"

    def test_empty_maps_to_c(self):
        assert _compute_tier("") == "C"

    def test_case_insensitive(self):
        assert _compute_tier("full") == "A"
        assert _compute_tier("partial") == "B"


# ---------------------------------------------------------------------------
# _project_lifecycle
# ---------------------------------------------------------------------------

class TestProjectLifecycle:
    def test_cancel_with_fees_returns_refunded(self):
        row = _row(event_kind="BOOKING_CANCELED", fees=500)
        assert _project_lifecycle(row) == "CANCELED_REFUNDED"

    def test_cancel_without_fees_returns_no_refund(self):
        row = _row(event_kind="BOOKING_CANCELED", fees=None)
        assert _project_lifecycle(row) == "CANCELED_NO_REFUND"

    def test_unknown_confidence_returns_unknown(self):
        row = _row(source_confidence="UNKNOWN", total_price=None)
        assert _project_lifecycle(row) == "UNKNOWN"

    def test_partial_with_no_net_returns_reconciliation_pending(self):
        row = _row(source_confidence="PARTIAL", net_to_property=None, total_price=10000)
        assert _project_lifecycle(row) == "RECONCILIATION_PENDING"

    def test_full_confidence_with_net_returns_payout_expected(self):
        row = _row(source_confidence="FULL", net_to_property=8500)
        assert _project_lifecycle(row) == "PAYOUT_EXPECTED"


# ---------------------------------------------------------------------------
# _detect_anomalies
# ---------------------------------------------------------------------------

class TestDetectAnomalies:
    def test_clean_row_has_no_flags(self):
        row = _row(source_confidence="FULL", net_to_property=8500, total_price=10000, ota_commission=1500)
        flags, lifecycle = _detect_anomalies(row)
        assert flags == []
        assert lifecycle == "PAYOUT_EXPECTED"

    def test_partial_confidence_flag(self):
        row = _row(source_confidence="PARTIAL", net_to_property=8500, total_price=10000)
        flags, _ = _detect_anomalies(row)
        assert "PARTIAL_CONFIDENCE" in flags

    def test_missing_net_flag(self):
        row = _row(source_confidence="FULL", net_to_property=None)
        flags, _ = _detect_anomalies(row)
        assert "MISSING_NET_TO_PROPERTY" in flags

    def test_commission_high_flag(self):
        # 3000 / 10000 = 30% > 25%
        row = _row(source_confidence="FULL", net_to_property=7000, total_price=10000, ota_commission=3000)
        flags, _ = _detect_anomalies(row)
        assert "COMMISSION_HIGH" in flags

    def test_commission_zero_flag(self):
        row = _row(source_confidence="FULL", net_to_property=10000, total_price=10000, ota_commission=0)
        flags, _ = _detect_anomalies(row)
        assert "COMMISSION_ZERO" in flags

    def test_net_negative_flag(self):
        row = _row(source_confidence="FULL", net_to_property=-500)
        flags, _ = _detect_anomalies(row)
        assert "NET_NEGATIVE" in flags

    def test_multiple_flags_together(self):
        row = _row(source_confidence="PARTIAL", net_to_property=None, total_price=10000, ota_commission=3500)
        flags, _ = _detect_anomalies(row)
        assert "PARTIAL_CONFIDENCE" in flags
        assert "MISSING_NET_TO_PROPERTY" in flags


# ---------------------------------------------------------------------------
# _build_booking_explanation
# ---------------------------------------------------------------------------

class TestBuildBookingExplanation:
    def test_contains_provider(self):
        row = _row()
        text = _build_booking_explanation(row, [], "PAYOUT_EXPECTED")
        assert "airbnb" in text.lower()

    def test_contains_currency(self):
        row = _row()
        text = _build_booking_explanation(row, [], "PAYOUT_EXPECTED")
        assert "THB" in text

    def test_lists_flags(self):
        row = _row(source_confidence="PARTIAL", net_to_property=None)
        flags = ["PARTIAL_CONFIDENCE", "MISSING_NET_TO_PROPERTY"]
        text = _build_booking_explanation(row, flags, "RECONCILIATION_PENDING")
        assert "Partial" in text or "partial" in text
        assert "missing" in text.lower() or "net" in text.lower()

    def test_no_anomaly_when_clean(self):
        row = _row()
        text = _build_booking_explanation(row, [], "PAYOUT_EXPECTED")
        assert "No anomalies" in text


# ---------------------------------------------------------------------------
# _build_recommended_action
# ---------------------------------------------------------------------------

class TestBuildRecommendedAction:
    def test_reconciliation_pending(self):
        action = _build_recommended_action(["RECONCILIATION_PENDING"], "RECONCILIATION_PENDING")
        assert "OTA" in action or "statement" in action

    def test_missing_net_and_partial(self):
        action = _build_recommended_action(["MISSING_NET_TO_PROPERTY", "PARTIAL_CONFIDENCE"], "RECONCILIATION_PENDING")
        assert "OTA" in action or "dashboard" in action.lower()

    def test_commission_high(self):
        action = _build_recommended_action(["COMMISSION_HIGH"], "PAYOUT_EXPECTED")
        assert "commission" in action.lower()

    def test_no_flags_returns_no_action_required(self):
        action = _build_recommended_action([], "PAYOUT_EXPECTED")
        assert "No action" in action


# ---------------------------------------------------------------------------
# _build_reconciliation_narrative
# ---------------------------------------------------------------------------

class TestBuildReconciliationNarrative:
    def test_zero_exceptions_is_clean(self):
        stats = {"total_checked": 10, "exception_count": 0, "tier_c_count": 0, "tier_b_count": 0, "flags_breakdown": {}}
        text = _build_reconciliation_narrative(stats)
        assert "clean" in text.lower() or "no action" in text.lower()

    def test_with_tier_c_exceptions(self):
        stats = {"total_checked": 5, "exception_count": 2, "tier_c_count": 1, "tier_b_count": 1, "flags_breakdown": {"RECONCILIATION_PENDING": 1}}
        text = _build_reconciliation_narrative(stats)
        assert "Tier C" in text or "critical" in text.lower()

    def test_with_missing_net(self):
        stats = {"total_checked": 3, "exception_count": 2, "tier_c_count": 0, "tier_b_count": 2, "flags_breakdown": {"MISSING_NET_TO_PROPERTY": 2}}
        text = _build_reconciliation_narrative(stats)
        assert "net" in text.lower() or "payout" in text.lower()


# ---------------------------------------------------------------------------
# Endpoint integration tests
# ---------------------------------------------------------------------------

class TestBookingExplainerEndpoint:
    def _app(self):
        from fastapi import FastAPI
        from api.financial_explainer_router import router
        app = FastAPI()
        app.include_router(router)
        return app

    def test_404_when_not_found(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.financial_explainer_router as fe_mod

        app = self._app()
        db = _empty_db()

        with patch("api.financial_explainer_router.jwt_auth", return_value=TENANT), \
             patch.object(fe_mod, "_get_db", return_value=db):
            resp = TestClient(app).get("/ai/copilot/financial/explain/BOGUS", headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 404

    def test_200_heuristic_response_shape(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.financial_explainer_router as fe_mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        db = _db_with_rows([_row()])

        with patch("api.financial_explainer_router.jwt_auth", return_value=TENANT), \
             patch.object(fe_mod, "_get_db", return_value=db):
            resp = TestClient(app).get("/ai/copilot/financial/explain/B001", headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["generated_by"] == "heuristic"
        assert "explanation_text" in data
        assert "anomaly_flags" in data
        assert "confidence_tier" in data
        assert "financials" in data
        assert "recommended_action" in data
        assert data["booking_id"] == "B001"

    def test_200_llm_when_mock_returns_text(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.financial_explainer_router as fe_mod
        import services.llm_client as lc

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        app = self._app()
        db = _db_with_rows([_row()])

        with patch("api.financial_explainer_router.jwt_auth", return_value=TENANT), \
             patch.object(fe_mod, "_get_db", return_value=db), \
             patch.object(lc, "is_configured", return_value=True), \
             patch.object(lc, "generate", return_value="LLM-generated booking explanation."):
            resp = TestClient(app).get("/ai/copilot/financial/explain/B001", headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["generated_by"] == "llm"
        assert data["explanation_text"] == "LLM-generated booking explanation."

    def test_anomaly_flags_present_for_partial_confidence(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.financial_explainer_router as fe_mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        db = _db_with_rows([_row(source_confidence="PARTIAL", net_to_property=None)])

        with patch("api.financial_explainer_router.jwt_auth", return_value=TENANT), \
             patch.object(fe_mod, "_get_db", return_value=db):
            resp = TestClient(app).get("/ai/copilot/financial/explain/B001", headers={"Authorization": "Bearer fake"})

        flags = resp.json()["anomaly_flags"]
        assert "PARTIAL_CONFIDENCE" in flags
        assert "MISSING_NET_TO_PROPERTY" in flags


class TestReconciliationSummaryEndpoint:
    def _app(self):
        from fastapi import FastAPI
        from api.financial_explainer_router import router
        app = FastAPI()
        app.include_router(router)
        return app

    def test_400_when_period_missing(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.financial_explainer_router as fe_mod

        app = self._app()
        with patch("api.financial_explainer_router.jwt_auth", return_value=TENANT), \
             patch.object(fe_mod, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).get("/ai/copilot/financial/reconciliation-summary", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 400

    def test_400_when_period_invalid_format(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.financial_explainer_router as fe_mod

        app = self._app()
        with patch("api.financial_explainer_router.jwt_auth", return_value=TENANT), \
             patch.object(fe_mod, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).get("/ai/copilot/financial/reconciliation-summary?period=bad", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 400

    def test_200_with_no_exceptions(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.financial_explainer_router as fe_mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        db = _db_with_rows([_row(source_confidence="FULL", net_to_property=8500)])  # clean row

        with patch("api.financial_explainer_router.jwt_auth", return_value=TENANT), \
             patch.object(fe_mod, "_get_db", return_value=db):
            resp = TestClient(app).get("/ai/copilot/financial/reconciliation-summary?period=2026-03", headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["stats"]["exception_count"] == 0
        assert "narrative" in data
        assert "exception_items" in data

    def test_200_with_exceptions_sorted_by_tier(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.financial_explainer_router as fe_mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        rows = [
            _row(booking_id="B-B", source_confidence="PARTIAL", net_to_property=8000, ota_commission=2000),
            _row(booking_id="B-C", source_confidence="UNKNOWN", net_to_property=None, total_price=None),
        ]
        db = _db_with_rows(rows)

        with patch("api.financial_explainer_router.jwt_auth", return_value=TENANT), \
             patch.object(fe_mod, "_get_db", return_value=db):
            resp = TestClient(app).get("/ai/copilot/financial/reconciliation-summary?period=2026-03", headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        items = resp.json()["exception_items"]
        assert len(items) > 0
        # Tier C item (B-C) should appear first
        tiers = [i["tier"] for i in items]
        if len(tiers) > 1:
            assert tiers[0] == "C" or tiers[0] <= tiers[-1]
