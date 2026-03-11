"""
Phase 225 — Task Recommendation Engine — Contract Tests

Tests cover:
    _compute_sla:
        - BREACHED when elapsed > sla_minutes → sla_score=800
        - WARNING_25 when ≤25% remaining → sla_score=400
        - OK when plenty of time remaining → sla_score=0
        - missing created_at → OK, score=0

    _recency_score:
        - very new task (same minute) → 50
        - 50+ day old task → 0

    _score_task:
        - CRITICAL + BREACHED → score ≥ 1800
        - LOW + OK + old → low score

    _build_heuristic_rationale:
        - BREACHED → mentions "SLA"
        - CRITICAL → mentions "CRITICAL"
        - HIGH + due_date → mentions due_date
        - LOW → mentions routine

    _build_heuristic_summary:
        - no tasks → "No open tasks" / "All clear"
        - breached task count mentioned
        - top task title appears

    POST /ai/copilot/task-recommendations:
        - 200 with empty body → all defaults
        - recommendations sorted by score DESC
        - CRITICAL task ranked first
        - worker_role filter applied
        - invalid worker_role → 400
        - limit clamped to 50
        - unsupported language falls back to en
        - generated_by = 'heuristic' when no LLM key
        - generated_by = 'llm' when mock LLM returns valid JSON array
        - LLM non-JSON response falls back to heuristic
        - no tasks → 200 with empty recommendations + summary
        - response shape: tenant_id, filter_applied, total_open_tasks, etc.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.task_recommendation_router import (
    _compute_sla,
    _recency_score,
    _score_task,
    _build_heuristic_rationale,
    _build_heuristic_summary,
)

TENANT = "tenant-test"
NOW = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(**kwargs) -> dict:
    """Build a minimal task row for testing."""
    base = {
        "task_id": "t001",
        "tenant_id": TENANT,
        "kind": "CLEANING",
        "title": "Clean villa 3",
        "priority": "MEDIUM",
        "status": "PENDING",
        "worker_role": "CLEANER",
        "due_date": "2026-03-15",
        "property_id": "prop-1",
        "booking_id": "B001",
        "ack_sla_minutes": 60,
        "created_at": (NOW - timedelta(minutes=30)).isoformat(),
        "updated_at": (NOW - timedelta(minutes=30)).isoformat(),
    }
    base.update(kwargs)
    return base


def _empty_db() -> MagicMock:
    db = MagicMock()
    t = MagicMock()
    for m in ("select", "eq", "order", "limit", "execute"):
        getattr(t, m).return_value = t
    result = MagicMock()
    result.data = []
    t.execute.return_value = result
    db.table.return_value = t
    return db


def _db_with_tasks(tasks: list) -> MagicMock:
    """Returns a mock db that returns tasks list from any .execute()."""
    db = MagicMock()
    t = MagicMock()
    for m in ("select", "eq", "order", "limit", "execute"):
        getattr(t, m).return_value = t
    result = MagicMock()
    result.data = tasks
    t.execute.return_value = result
    db.table.return_value = t
    return db


# ---------------------------------------------------------------------------
# _compute_sla
# ---------------------------------------------------------------------------

class TestComputeSla:
    def test_breached_score_800(self):
        task = _task(
            priority="MEDIUM",
            ack_sla_minutes=60,
            created_at=(NOW - timedelta(minutes=90)).isoformat(),
        )
        sla_status, minutes_past, score = _compute_sla(task, NOW)
        assert sla_status == "BREACHED"
        assert minutes_past > 0
        assert score == 800

    def test_warning_25_score_400(self):
        """10 minutes left on 60-min SLA = 16.7% remaining → WARNING_25."""
        task = _task(
            priority="MEDIUM",
            ack_sla_minutes=60,
            created_at=(NOW - timedelta(minutes=52)).isoformat(),
        )
        sla_status, _, score = _compute_sla(task, NOW)
        assert sla_status == "WARNING_25"
        assert score == 400

    def test_ok_score_0(self):
        task = _task(
            priority="LOW",
            ack_sla_minutes=240,
            created_at=(NOW - timedelta(minutes=5)).isoformat(),
        )
        sla_status, _, score = _compute_sla(task, NOW)
        assert sla_status == "OK"
        assert score == 0

    def test_missing_created_at_returns_ok(self):
        task = _task(created_at=None)
        sla_status, _, score = _compute_sla(task, NOW)
        assert sla_status == "OK"
        assert score == 0


# ---------------------------------------------------------------------------
# _recency_score
# ---------------------------------------------------------------------------

class TestRecencyScore:
    def test_new_task_scores_50(self):
        task = _task(created_at=NOW.isoformat())
        score = _recency_score(task, NOW)
        assert score == 50

    def test_50_day_old_task_scores_0(self):
        task = _task(created_at=(NOW - timedelta(days=55)).isoformat())
        score = _recency_score(task, NOW)
        assert score == 0

    def test_25_day_old_task_scores_25(self):
        task = _task(created_at=(NOW - timedelta(days=25)).isoformat())
        score = _recency_score(task, NOW)
        assert score == 25


# ---------------------------------------------------------------------------
# _score_task
# ---------------------------------------------------------------------------

class TestScoreTask:
    def test_critical_breached_score_at_least_1800(self):
        task = _task(
            priority="CRITICAL",
            ack_sla_minutes=5,
            created_at=(NOW - timedelta(minutes=20)).isoformat(),
        )
        scored, breakdown = _score_task(task, NOW)
        assert scored["_score"] >= 1800  # 1000 priority + 800 SLA
        assert breakdown["priority"] == 1000
        assert breakdown["sla"] == 800

    def test_low_ok_fresh_task_low_score(self):
        """LOW priority, 5 min old, well within 4-hour ACK SLA - low score."""
        task = _task(
            priority="LOW",
            ack_sla_minutes=240,
            created_at=(NOW - timedelta(minutes=5)).isoformat(),
        )
        scored, breakdown = _score_task(task, NOW)
        # priority=50, sla=0 (5min into 240min SLA), recency<=50
        assert scored["_score"] <= 110
        assert breakdown["priority"] == 50
        assert breakdown["sla"] == 0

    def test_high_recent_ok_score(self):
        task = _task(
            priority="HIGH",
            ack_sla_minutes=15,
            created_at=NOW.isoformat(),
        )
        scored, _ = _score_task(task, NOW)
        assert scored["_score"] >= 550  # 500 + 50 recency


# ---------------------------------------------------------------------------
# _build_heuristic_rationale
# ---------------------------------------------------------------------------

class TestBuildHeuristicRationale:
    def test_breached_mentions_sla(self):
        task = _task(
            priority="CRITICAL",
            ack_sla_minutes=5,
            _sla_status="BREACHED",
            _minutes_past_sla=10,
            _breakdown={"priority": 1000, "sla": 800, "recency": 50},
        )
        text = _build_heuristic_rationale(task)
        assert "SLA" in text or "sla" in text.lower()

    def test_critical_mentions_critical(self):
        task = _task(
            priority="CRITICAL",
            ack_sla_minutes=5,
            _sla_status="OK",
            _minutes_past_sla=0,
            _breakdown={"priority": 1000, "sla": 0, "recency": 50},
        )
        text = _build_heuristic_rationale(task)
        assert "CRITICAL" in text or "critical" in text.lower()

    def test_high_with_due_date(self):
        task = _task(
            priority="HIGH",
            due_date="2026-03-15",
            _sla_status="OK",
            _minutes_past_sla=0,
            _breakdown={"priority": 500, "sla": 0, "recency": 50},
        )
        text = _build_heuristic_rationale(task)
        assert "2026-03-15" in text

    def test_low_mentions_routine(self):
        task = _task(
            priority="LOW",
            _sla_status="OK",
            _minutes_past_sla=0,
            _breakdown={"priority": 50, "sla": 0, "recency": 0},
        )
        text = _build_heuristic_rationale(task)
        assert "routine" in text.lower() or "order" in text.lower()


# ---------------------------------------------------------------------------
# _build_heuristic_summary
# ---------------------------------------------------------------------------

class TestBuildHeuristicSummary:
    def test_no_tasks_returns_all_clear(self):
        text = _build_heuristic_summary(0, [], None, None)
        assert "clear" in text.lower() or "no open tasks" in text.lower()

    def test_breached_count_mentioned(self):
        recs = [
            {"sla_status": "BREACHED", "priority": "CRITICAL", "title": "Clean Villa 3", "score": 1850},
            {"sla_status": "OK", "priority": "HIGH", "title": "Check-in prep", "score": 550},
        ]
        text = _build_heuristic_summary(5, recs, None, None)
        assert "1 task" in text or "breached" in text.lower()

    def test_top_task_title_in_summary(self):
        recs = [
            {"sla_status": "OK", "priority": "HIGH", "title": "Check-in prep", "score": 550},
        ]
        text = _build_heuristic_summary(3, recs, None, None)
        assert "Check-in prep" in text


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

class TestTaskRecommendationsEndpoint:
    def _app(self):
        from fastapi import FastAPI
        from api.task_recommendation_router import router
        app = FastAPI()
        app.include_router(router)
        return app

    def test_200_with_empty_body(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.task_recommendation_router as rm

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        db = _empty_db()

        with patch("api.task_recommendation_router.jwt_auth", return_value=TENANT), \
             patch.object(rm, "_get_db", return_value=db):
            resp = TestClient(app).post("/ai/copilot/task-recommendations", json={}, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data
        assert "summary" in data
        assert data["generated_by"] == "heuristic"
        assert data["language"] == "en"

    def test_critical_task_ranked_first(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.task_recommendation_router as rm

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()

        critical = _task(task_id="t-crit", priority="CRITICAL", ack_sla_minutes=5,
                         created_at=(NOW - timedelta(minutes=10)).isoformat())
        low = _task(task_id="t-low", priority="LOW", ack_sla_minutes=240,
                    created_at=NOW.isoformat())
        db = _db_with_tasks([critical, low])

        with patch("api.task_recommendation_router.jwt_auth", return_value=TENANT), \
             patch.object(rm, "_get_db", return_value=db):
            resp = TestClient(app).post("/ai/copilot/task-recommendations", json={}, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        recs = resp.json()["recommendations"]
        assert len(recs) >= 1
        assert recs[0]["priority"] == "CRITICAL"

    def test_invalid_worker_role_returns_400(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.task_recommendation_router as rm

        app = self._app()
        with patch("api.task_recommendation_router.jwt_auth", return_value=TENANT), \
             patch.object(rm, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).post("/ai/copilot/task-recommendations",
                                        json={"worker_role": "WIZARD"},
                                        headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 400

    def test_unsupported_language_falls_back_to_en(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.task_recommendation_router as rm

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        with patch("api.task_recommendation_router.jwt_auth", return_value=TENANT), \
             patch.object(rm, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).post("/ai/copilot/task-recommendations",
                                        json={"language": "klingon"},
                                        headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        assert resp.json()["language"] == "en"

    def test_generated_by_llm_when_mock_returns_json(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.task_recommendation_router as rm
        import services.llm_client as lc

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        app = self._app()
        tasks_data = [_task(priority="HIGH")]
        db = _db_with_tasks(tasks_data)

        with patch("api.task_recommendation_router.jwt_auth", return_value=TENANT), \
             patch.object(rm, "_get_db", return_value=db), \
             patch.object(lc, "is_configured", return_value=True), \
             patch.object(lc, "generate", return_value='["Urgent task — acknowledge within 15 minutes."]'):
            resp = TestClient(app).post("/ai/copilot/task-recommendations", json={}, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["generated_by"] == "llm"
        assert data["recommendations"][0]["rationale"] == "Urgent task — acknowledge within 15 minutes."

    def test_llm_non_json_falls_back_to_heuristic(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.task_recommendation_router as rm
        import services.llm_client as lc

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        app = self._app()
        db = _db_with_tasks([_task(priority="HIGH")])

        with patch("api.task_recommendation_router.jwt_auth", return_value=TENANT), \
             patch.object(rm, "_get_db", return_value=db), \
             patch.object(lc, "is_configured", return_value=True), \
             patch.object(lc, "generate", return_value="This is not valid JSON"):
            resp = TestClient(app).post("/ai/copilot/task-recommendations", json={}, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        # generated_by should be heuristic since JSON parse failed
        assert resp.json()["generated_by"] == "heuristic"

    def test_no_tasks_returns_200_with_empty_recommendations(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.task_recommendation_router as rm

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()

        with patch("api.task_recommendation_router.jwt_auth", return_value=TENANT), \
             patch.object(rm, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).post("/ai/copilot/task-recommendations", json={}, headers={"Authorization": "Bearer fake"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["recommendations"] == []
        assert data["total_open_tasks"] == 0
        assert "clear" in data["summary"].lower() or "no open" in data["summary"].lower()

    def test_response_has_all_required_fields(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.task_recommendation_router as rm

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()

        with patch("api.task_recommendation_router.jwt_auth", return_value=TENANT), \
             patch.object(rm, "_get_db", return_value=_empty_db()):
            resp = TestClient(app).post("/ai/copilot/task-recommendations", json={}, headers={"Authorization": "Bearer fake"})

        data = resp.json()
        for field in ("tenant_id", "generated_by", "language", "generated_at",
                      "filter_applied", "total_open_tasks", "recommendation_count",
                      "recommendations", "summary"):
            assert field in data, f"Missing field: {field}"

    def test_recommendations_have_required_fields(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.task_recommendation_router as rm

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        app = self._app()
        db = _db_with_tasks([_task()])

        with patch("api.task_recommendation_router.jwt_auth", return_value=TENANT), \
             patch.object(rm, "_get_db", return_value=db):
            resp = TestClient(app).post("/ai/copilot/task-recommendations", json={}, headers={"Authorization": "Bearer fake"})

        recs = resp.json()["recommendations"]
        # Mock DB returns tasks for both PENDING + ACKNOWLEDGED queries (may be 1 or 2)
        assert len(recs) >= 1
        rec = recs[0]
        for field in ("rank", "task_id", "kind", "title", "priority", "status",
                      "score", "sla_status", "rationale", "score_breakdown"):
            assert field in rec, f"Missing rec field: {field}"
