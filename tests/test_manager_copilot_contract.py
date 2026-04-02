"""
Phase 223 — Manager Copilot v1: Morning Briefing — Contract Tests

Tests cover:
    llm_client:
        - generate() returns None when OPENAI_API_KEY not set
        - generate() returns None for unsupported provider
        - generate() calls openai and returns text on success (mock)
        - generate() returns None on openai exception
        - is_configured() returns False when key absent
        - is_configured() returns True when key present

    _build_heuristic_briefing:
        - empty context produces valid output
        - critical SLA breach appears in briefing + action_items
        - DLQ signal NOT surfaced in OM briefing (Phase 1043)
        - sync degraded appears in briefing + action_items
        - high arrival day appears in briefing
        - top_action prioritizes critical SLA over others

    post_morning_briefing endpoint:
        - 200 response with correct shape (no LLM key)
        - generated_by='heuristic' when no key
        - generated_by='llm' when mock LLM returns text
        - language defaults to 'en'
        - unsupported language falls back to 'en'
        - action_items is a list
        - context_signals contains expected keys (no dlq key — Phase 1043)
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import services.llm_client as llm_mod
from api.manager_copilot_router import _build_heuristic_briefing


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TENANT = "tenant-test"

def _empty_context() -> dict:
    """Phase 1043: DLQ removed from OM briefing context."""
    return {
        "operations": {"date": "2026-03-11", "arrivals_count": 0, "departures_count": 0, "cleanings_due": 0, "active_bookings": 0},
        "tasks": {
            "total_open": 0, "actionable_now": 0,
            "overdue": 0, "due_today": 0, "due_soon": 0, "future": 0,
            "by_priority_actionable": {}, "by_kind": {}, "critical_past_ack_sla": 0,
        },
        "outbound_sync": {"event_count_24h": 0, "failure_rate_24h": None},
        "ai_hints": {"critical_tasks_over_sla": 0, "sync_degraded": False, "high_arrival_day": False, "high_departure_day": False},
    }

def _context_with(**overrides) -> dict:
    ctx = _empty_context()
    hints = ctx["ai_hints"]
    hints.update({k: v for k, v in overrides.items() if k in hints})
    ops = ctx["operations"]
    ops.update({k: v for k, v in overrides.items() if k in ops})
    tasks = ctx["tasks"]
    tasks.update({k: v for k, v in overrides.items() if k in tasks})
    sync = ctx["outbound_sync"]
    sync.update({k: v for k, v in overrides.items() if k in sync})
    return ctx


# ---------------------------------------------------------------------------
# llm_client
# ---------------------------------------------------------------------------

class TestLlmClientGenerate:
    def test_returns_none_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = llm_mod.generate("sys", "usr")
        assert result is None

    def test_returns_none_for_unsupported_provider(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("IHOUSE_LLM_PROVIDER", "anthropic")
        result = llm_mod.generate("sys", "usr")
        assert result is None
        monkeypatch.delenv("IHOUSE_LLM_PROVIDER", raising=False)

    def test_returns_text_on_openai_success(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("IHOUSE_LLM_PROVIDER", "openai")

        mock_choice = MagicMock()
        mock_choice.message.content = "  Good morning. Four arrivals today.  "
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(total_tokens=120)

        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_response

        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = mock_client_instance

        with patch.dict("sys.modules", {"openai": mock_openai}):
            result = llm_mod.generate("sys", "usr")

        assert result == "Good morning. Four arrivals today."

    def test_returns_none_on_openai_exception(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("IHOUSE_LLM_PROVIDER", "openai")

        mock_openai = MagicMock()
        mock_openai.OpenAI.side_effect = Exception("Connection refused")

        with patch.dict("sys.modules", {"openai": mock_openai}):
            result = llm_mod.generate("sys", "usr")

        assert result is None


class TestLlmClientIsConfigured:
    def test_false_when_no_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert llm_mod.is_configured() is False

    def test_true_when_key_set(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        assert llm_mod.is_configured() is True

    def test_false_when_key_is_whitespace(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "   ")
        assert llm_mod.is_configured() is False


# ---------------------------------------------------------------------------
# _build_heuristic_briefing
# ---------------------------------------------------------------------------

class TestBuildHeuristicBriefing:
    def test_empty_context_returns_valid_output(self):
        ctx = _empty_context()
        text, items = _build_heuristic_briefing(ctx)
        assert isinstance(text, str)
        assert len(text) > 0
        assert isinstance(items, list)

    def test_critical_sla_breach_in_text_and_actions(self):
        ctx = _context_with(critical_tasks_over_sla=2)
        ctx["ai_hints"]["critical_tasks_over_sla"] = 2
        ctx["tasks"]["critical_past_ack_sla"] = 2
        text, items = _build_heuristic_briefing(ctx)
        assert "ACK SLA" in text or "critical" in text.lower()
        action_types = [a["action"] for a in items]
        assert "ACKNOWLEDGE_TASKS" in action_types

    def test_critical_sla_top_action_priority(self):
        ctx = _context_with(critical_tasks_over_sla=1, sync_degraded=True)
        ctx["ai_hints"]["critical_tasks_over_sla"] = 1
        ctx["tasks"]["critical_past_ack_sla"] = 1
        ctx["ai_hints"]["sync_degraded"] = True
        text, items = _build_heuristic_briefing(ctx)
        # critical takes priority in Top Action
        assert "Acknowledge" in text or "acknowledge" in text.lower() or "critical" in text.lower()
        action_priorities = [a["priority"] for a in items]
        assert "CRITICAL" in action_priorities

    def test_dlq_not_surfaced_in_om_briefing(self):
        """Phase 1043: DLQ must never appear in OM Morning Briefing text or action items."""
        ctx = _empty_context()
        text, items = _build_heuristic_briefing(ctx)
        assert "DLQ" not in text
        assert "Dead Letter" not in text
        assert "replay" not in text.lower()
        assert not any(i["action"] == "REVIEW_DLQ" for i in items)

    def test_sync_degraded_in_text_and_actions(self):
        ctx = _context_with(sync_degraded=True)
        ctx["ai_hints"]["sync_degraded"] = True
        ctx["outbound_sync"]["failure_rate_24h"] = 0.5
        text, items = _build_heuristic_briefing(ctx)
        assert "sync" in text.lower() or "outbound" in text.lower()
        action_types = [a["action"] for a in items]
        assert "CHECK_SYNC" in action_types

    def test_high_arrival_day_mentioned(self):
        ctx = _empty_context()
        ctx["ai_hints"]["high_arrival_day"] = True
        ctx["operations"]["arrivals_count"] = 4
        text, items = _build_heuristic_briefing(ctx)
        assert "arriv" in text.lower() or "check-in" in text.lower()

    def test_no_tasks_says_no_open_tasks(self):
        ctx = _empty_context()
        text, items = _build_heuristic_briefing(ctx)
        assert "No open tasks" in text

    def test_scheduled_future_tasks_not_framed_as_problems(self):
        """Phase 1043: future-only tasks must say scheduled ahead, not alarm."""
        ctx = _empty_context()
        ctx["tasks"]["total_open"] = 3
        ctx["tasks"]["future"] = 3
        ctx["tasks"]["actionable_now"] = 0
        text, items = _build_heuristic_briefing(ctx)
        assert "3" in text
        assert "scheduled" in text.lower() or "attention" in text.lower()
        # Must NOT say 13 high/critical or similar alarmist language
        assert "CRITICAL" not in text or "SLA" in text  # only CRITICAL if SLA breach


# ---------------------------------------------------------------------------
# Endpoint integration tests
# ---------------------------------------------------------------------------

class TestMorningBriefingEndpoint:
    def _make_empty_db(self):
        db = MagicMock()
        table_mock = MagicMock()
        for m in ("select", "eq", "in_", "order", "limit", "gte", "is_", "execute"):
            getattr(table_mock, m).return_value = table_mock
        result = MagicMock()
        result.data = []
        result.count = 0
        table_mock.execute.return_value = result
        db.table.return_value = table_mock
        return db

    def _make_app(self):
        from fastapi import FastAPI
        from api.manager_copilot_router import router
        app = FastAPI()
        app.include_router(router)
        return app

    def test_returns_200_heuristic_when_no_llm_key(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.manager_copilot_router as cop_mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._make_app()
        db = self._make_empty_db()

        with patch("api.manager_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(cop_mod, "_get_db", return_value=db):
            client = TestClient(app)
            resp = client.post("/ai/copilot/morning-briefing", json={"language": "en"}, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["generated_by"] == "heuristic"
        assert "briefing_text" in data
        assert "action_items" in data
        assert "context_signals" in data
        assert data["language"] == "en"

    def test_generated_by_llm_when_mock_llm_returns_text(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.manager_copilot_router as cop_mod
        import services.llm_client as lc

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        app = self._make_app()
        db = self._make_empty_db()

        with patch("api.manager_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(cop_mod, "_get_db", return_value=db), \
             patch.object(lc, "is_configured", return_value=True), \
             patch.object(lc, "generate", return_value="Mock LLM briefing text."):
            client = TestClient(app)
            resp = client.post("/ai/copilot/morning-briefing", json={"language": "en"}, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["generated_by"] == "llm"
        assert data["briefing_text"] == "Mock LLM briefing text."

    def test_defaults_to_heuristic_when_llm_returns_none(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.manager_copilot_router as cop_mod
        import services.llm_client as lc

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        app = self._make_app()
        db = self._make_empty_db()

        with patch("api.manager_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(cop_mod, "_get_db", return_value=db), \
             patch.object(lc, "is_configured", return_value=True), \
             patch.object(lc, "generate", return_value=None):  # LLM failed
            client = TestClient(app)
            resp = client.post("/ai/copilot/morning-briefing", json={"language": "en"}, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        assert resp.json()["generated_by"] == "heuristic"

    def test_unsupported_language_falls_back_to_en(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.manager_copilot_router as cop_mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._make_app()
        db = self._make_empty_db()

        with patch("api.manager_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(cop_mod, "_get_db", return_value=db):
            client = TestClient(app)
            resp = client.post("/ai/copilot/morning-briefing", json={"language": "klingon"}, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        assert resp.json()["language"] == "en"

    def test_context_signals_has_expected_keys(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.manager_copilot_router as cop_mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._make_app()
        db = self._make_empty_db()

        with patch("api.manager_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(cop_mod, "_get_db", return_value=db):
            client = TestClient(app)
            resp = client.post("/ai/copilot/morning-briefing", json={}, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        signals = resp.json()["context_signals"]
        assert "operations" in signals
        assert "tasks" in signals
        assert "outbound_sync" in signals
        assert "ai_hints" in signals
        assert "dlq" not in signals  # Phase 1043: DLQ removed from OM context

    def test_response_always_has_generated_at(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.manager_copilot_router as cop_mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._make_app()
        db = self._make_empty_db()

        with patch("api.manager_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(cop_mod, "_get_db", return_value=db):
            client = TestClient(app)
            resp = client.post("/ai/copilot/morning-briefing", json={}, headers={"Authorization": "Bearer fake"})

        assert "generated_at" in resp.json()
        assert "tenant_id" in resp.json()
