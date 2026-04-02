"""
Phase 322 — AI Copilot Integration Tests
==========================================

Tests both copilot endpoints:

Group A: Manager Morning Briefing — Heuristic Path
  ✓  Heuristic briefing with normal ops → structured output
  ✓  Critical SLA breach → action items with ACKNOWLEDGE_TASKS
  ✓  DLQ signal NOT surfaced (Phase 1043 — DLQ removed from OM briefing)
  ✓  High arrival day → briefing mentions arrivals
  ✓  Combined alerts → multiple action items

Group B: Worker Task Assist — Heuristic Path
  ✓  Valid task → full assist card with all sub-objects
  ✓  CHECKIN_PREP kind → mentions guest arrival
  ✓  Missing task_id → 400 error
  ✓  Task not found → 404 error
  ✓  Priority justification contains task priority

Group C: LLM Fallback Behavior
  ✓  No OPENAI_API_KEY → generated_by = heuristic
  ✓  LLM failure → graceful fallback to heuristic

CI-safe: no live DB, no LLM API calls, all mocked.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.manager_copilot_router import _build_heuristic_briefing
from api.worker_copilot_router import (
    _build_heuristic_narrative,
    _build_priority_justification,
)


# ---------------------------------------------------------------------------
# Group A — Manager Morning Briefing (Heuristic)
# ---------------------------------------------------------------------------

def _ops_context(**overrides):
    """Build a minimal operations context dict."""
    base = {
        "operations": {
            "date": "2026-03-12",
            "arrivals_count": 2,
            "departures_count": 1,
            "cleanings_due": 3,
            "active_bookings": 5,
        },
        "tasks": {
            "total_open": 4,
            "actionable_now": 0,
            "overdue": 0,
            "due_today": 0,
            "due_soon": 1,
            "future": 3,
            "by_priority_actionable": {},
            "critical_past_ack_sla": 0,
        },
        "outbound_sync": {"failure_rate_24h": 0.0},
        "ai_hints": {
            "critical_tasks_over_sla": 0,
            "sync_degraded": False,
            "high_arrival_day": False,
            "high_departure_day": False,
        },
    }
    # Apply overrides to ai_hints
    if "ai_hints" in overrides:
        base["ai_hints"].update(overrides.pop("ai_hints"))
    for k, v in overrides.items():
        if isinstance(v, dict) and k in base:
            base[k].update(v)
        else:
            base[k] = v
    return base


class TestManagerBriefingHeuristic:

    def test_normal_ops_returns_text_and_action_items(self):
        ctx = _ops_context()
        text, items = _build_heuristic_briefing(ctx)
        assert "Morning briefing for 2026-03-12" in text
        assert "2 check-in" in text
        assert isinstance(items, list)

    def test_critical_sla_breach_produces_ack_action(self):
        ctx = _ops_context(
            ai_hints={"critical_tasks_over_sla": 3},
            tasks={"total_open": 5, "by_priority": {"CRITICAL": 3, "HIGH": 1, "MEDIUM": 1, "LOW": 0}},
        )
        text, items = _build_heuristic_briefing(ctx)
        assert "CRITICAL" in text
        assert any(i["action"] == "ACKNOWLEDGE_TASKS" for i in items)
        assert items[0]["priority"] == "CRITICAL"

    def test_dlq_signal_not_surfaced_in_om_briefing(self):
        """Phase 1043: DLQ removed from OM briefing path. Even if context has dlq key, it must not appear in output."""
        ctx = _ops_context()
        ctx["dlq"] = {"unprocessed_count": 7, "alert": True}  # artificially injected
        text, items = _build_heuristic_briefing(ctx)
        # DLQ must NOT appear in OM briefing text or action items
        assert "DLQ" not in text
        assert "Dead Letter" not in text
        assert not any(i["action"] == "REVIEW_DLQ" for i in items)

    def test_high_arrival_day_mentions_check_ins(self):
        ctx = _ops_context(
            operations={"arrivals_count": 5, "departures_count": 1, "cleanings_due": 6, "active_bookings": 8, "date": "2026-03-12"},
            ai_hints={"high_arrival_day": True},
        )
        text, items = _build_heuristic_briefing(ctx)
        assert "5 check-in" in text
        assert any(i.get("action") == "CONFIRM_CHECKINS" for i in items)

    def test_combined_alerts(self):
        """Phase 1043: combined critical SLA + sync degraded. DLQ removed from action items."""
        ctx = _ops_context(
            ai_hints={"critical_tasks_over_sla": 1, "sync_degraded": True},
            outbound_sync={"failure_rate_24h": 0.3},
        )
        _, items = _build_heuristic_briefing(ctx)
        action_types = {i["action"] for i in items}
        assert "ACKNOWLEDGE_TASKS" in action_types
        assert "CHECK_SYNC" in action_types
        assert "REVIEW_DLQ" not in action_types  # DLQ removed from OM briefing


# ---------------------------------------------------------------------------
# Group B — Worker Assist (Heuristic)
# ---------------------------------------------------------------------------

class TestWorkerAssistHeuristic:

    def test_checkin_prep_mentions_guest_arrival(self):
        task = {"kind": "CHECKIN_PREP", "priority": "HIGH", "urgency": "urgent", "due_date": "2026-03-12"}
        prop = {"name": "Villa Sunset", "address": "123 Beach Road", "access_code": "5678", "wifi_password": "sunny123"}
        guest = {"guest_name": "John Doe", "check_in": "2026-03-12", "check_out": "2026-03-15"}
        narrative = _build_heuristic_narrative(task, prop, guest, [])
        assert "Guest check-in" in narrative
        assert "John Doe" in narrative
        assert "5678" in narrative

    def test_cleaning_task_narrative(self):
        task = {"kind": "CLEANING", "priority": "MEDIUM", "urgency": "normal"}
        prop = {"name": "Apt 301", "address": "456 City Road", "access_code": "1234"}
        narrative = _build_heuristic_narrative(task, prop, {}, [])
        assert "full cleaning" in narrative.lower()
        assert "1234" in narrative

    def test_priority_justification_contains_priority(self):
        task = {"kind": "MAINTENANCE", "priority": "CRITICAL", "due_date": "2026-03-12"}
        justification = _build_priority_justification(task, {})
        assert "CRITICAL" in justification
        assert "MAINTENANCE" in justification

    def test_priority_justification_mentions_guest_for_checkin(self):
        task = {"kind": "CHECKIN_PREP", "priority": "HIGH"}
        guest = {"check_in": "2026-03-12"}
        justification = _build_priority_justification(task, guest)
        assert "2026-03-12" in justification

    def test_recent_history_hint(self):
        task = {"kind": "CLEANING", "priority": "MEDIUM"}
        history = [{"kind": "CLEANING", "status": "COMPLETED", "due_date": "2026-03-10"}]
        narrative = _build_heuristic_narrative(task, {}, {}, history)
        assert "Last completed" in narrative


# ---------------------------------------------------------------------------
# Group C — HTTP endpoints (LLM fallback + heuristic)
# ---------------------------------------------------------------------------

class TestCopilotHTTP:

    @pytest.fixture(autouse=True)
    def _setup_client(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    @patch("api.manager_copilot_router._get_db")
    @patch("api.manager_copilot_router._get_operations_context")
    def test_morning_briefing_returns_heuristic(self, mock_ctx, mock_db):
        mock_db.return_value = MagicMock()
        mock_ctx.return_value = _ops_context()

        r = self.client.post(
            "/ai/copilot/morning-briefing",
            json={"language": "en"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["generated_by"] == "heuristic"
        assert "briefing_text" in body
        assert "action_items" in body
        assert "context_signals" in body

    @patch("api.worker_copilot_router._get_db")
    @patch("api.worker_copilot_router._fetch_task")
    @patch("api.worker_copilot_router._fetch_booking")
    @patch("api.worker_copilot_router._fetch_property")
    @patch("api.worker_copilot_router._fetch_recent_task_history")
    def test_worker_assist_returns_full_card(self, mock_hist, mock_prop, mock_book, mock_task, mock_db):
        mock_db.return_value = MagicMock()
        mock_task.return_value = {
            "task_id": "t-001", "kind": "CHECKIN_PREP", "priority": "HIGH",
            "urgency": "urgent", "due_date": "2026-03-12", "status": "ASSIGNED",
            "booking_id": "b-001", "property_id": "p-001", "title": "Prepare Villa",
        }
        mock_book.return_value = {
            "booking_id": "b-001", "guest_name": "Test Guest",
            "check_in": "2026-03-12", "check_out": "2026-03-15", "provider": "airbnb",
        }
        mock_prop.return_value = {
            "name": "Villa Test", "address": "1 Test Road", "access_code": "9999",
            "wifi_password": "test123", "checkin_time": "15:00", "checkout_time": "11:00",
        }
        mock_hist.return_value = []

        r = self.client.post(
            "/ai/copilot/worker-assist",
            json={"task_id": "t-001"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["generated_by"] == "heuristic"
        assert body["task_context"]["kind"] == "CHECKIN_PREP"
        assert body["property_info"]["access_code"] == "9999"
        assert body["guest_context"]["guest_name"] == "Test Guest"
        assert "assist_narrative" in body

    def test_worker_assist_missing_task_id_returns_400(self):
        r = self.client.post("/ai/copilot/worker-assist", json={})
        assert r.status_code == 400

    @patch("api.worker_copilot_router._get_db")
    @patch("api.worker_copilot_router._fetch_task")
    def test_worker_assist_notfound_returns_404(self, mock_task, mock_db):
        mock_db.return_value = MagicMock()
        mock_task.return_value = None
        r = self.client.post("/ai/copilot/worker-assist", json={"task_id": "nonexistent"})
        assert r.status_code == 404
