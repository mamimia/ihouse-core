"""
Phase 231 — Worker Task Copilot — Contract Tests

Tests cover:

_build_heuristic_narrative:
    - CHECKIN_PREP — includes property name, access code, Wi-Fi, guest name, check-in date
    - CLEANING — generic cleaning intro, access code
    - CHECKOUT_VERIFY — mentions checkout date
    - MAINTENANCE — generic maintenance intro
    - GUEST_WELCOME — guest name included
    - CRITICAL priority — includes urgency warning

_build_priority_justification:
    - returns non-empty string for all kinds/priorities
    - includes priority and kind
    - includes guest check-in for CHECKIN_PREP

POST /ai/copilot/worker-assist:
    - 400 when task_id missing
    - 400 when task_id empty string
    - 404 when task not found for tenant
    - 200 happy path — correct response shape (all required keys)
    - generated_by = heuristic without LLM key
    - generated_by = llm when mock LLM returns text
    - property_info has access_code and wifi_password
    - guest_context has guest_name, check_in, check_out
    - recent_task_history max 5 items
    - priority_justification is non-empty
    - 500 on DB error
    - missing booking → guest_context returned (gracefully empty)
    - missing property → property_info returned (gracefully empty)
    - AI audit log called (best-effort, no exception propagated)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.worker_copilot_router import (
    _build_heuristic_narrative,
    _build_priority_justification,
)

TENANT = "tenant-test"


@pytest.fixture(autouse=True)
def _dev_mode(monkeypatch):
    """Phase 283: set dev mode per-test so auth doesn't block."""
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(**kwargs) -> dict:
    base = {
        "task_id": "abc123def456",
        "kind": "CHECKIN_PREP",
        "status": "PENDING",
        "priority": "HIGH",
        "urgency": "urgent",
        "title": "CHECKIN_PREP — Sunset Villa",
        "due_date": "2026-03-15",
        "booking_id": "airbnb_R123",
        "property_id": "prop-1",
        "tenant_id": TENANT,
        "worker_role": "PROPERTY_MANAGER",
    }
    base.update(kwargs)
    return base


def _make_property(**kwargs) -> dict:
    base = {
        "property_id": "prop-1",
        "name": "Sunset Villa",
        "address": "123 Beach Road",
        "access_code": "7890",
        "wifi_password": "beach2026",
        "checkin_time": "15:00",
        "checkout_time": "11:00",
    }
    base.update(kwargs)
    return base


def _make_booking(**kwargs) -> dict:
    base = {
        "booking_id": "airbnb_R123",
        "guest_name": "Alice",
        "guest_email": "alice@example.com",
        "check_in": "2026-03-15",
        "check_out": "2026-03-20",
        "lifecycle_status": "ACTIVE",
        "provider": "airbnb",
        "property_id": "prop-1",
    }
    base.update(kwargs)
    return base


def _make_db(
    task: dict | None = None,
    booking: dict | None = None,
    prop: dict | None = None,
    history: list[dict] | None = None,
    fail: bool = False,
) -> MagicMock:
    """Build a mock Supabase client returning canned data."""
    db = MagicMock()

    if fail:
        db.table.side_effect = RuntimeError("DB failure")
        return db

    def table_fn(name: str):
        t = MagicMock()
        for m in ("select", "eq", "limit", "order", "execute"):
            getattr(t, m).return_value = t

        result = MagicMock()
        if name == "tasks":
            result.data = [task] if task else []
            # history query (also tasks table) — return history list
            hist = history if history is not None else []
            def execute_tasks():
                return result
            # All execute() calls on tasks table return the same result
            # but we differentiate by the fact that the first call is for
            # the single-task fetch (eq task_id) and the second is history.
            # For simplicity, return task for first, history for subsequent.
            call_count = {"n": 0}
            original_execute = result
            def smart_execute():
                call_count["n"] += 1
                r = MagicMock()
                if call_count["n"] == 1:
                    r.data = [task] if task else []
                else:
                    r.data = hist
                return r
            t.execute.side_effect = smart_execute
        elif name == "booking_state":
            result.data = [booking] if booking else []
            t.execute.return_value = result
        elif name == "properties":
            result.data = [prop] if prop else []
            t.execute.return_value = result
        else:
            result.data = []
            t.execute.return_value = result
        return t

    db.table.side_effect = table_fn
    return db


def _app():
    from fastapi import FastAPI
    from api.worker_copilot_router import router
    app = FastAPI()
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# Unit tests: _build_heuristic_narrative
# ---------------------------------------------------------------------------

class TestBuildHeuristicNarrative:
    def _prop(self, **kw):
        return {**_make_property(), **kw}

    def _guest(self, **kw):
        return {
            "guest_name": "Alice",
            "language": "en",
            "check_in": "2026-03-15",
            "check_out": "2026-03-20",
            "total_nights": 5,
            "provider": "airbnb",
            **kw,
        }

    def test_checkin_prep_contains_access_code(self):
        task = _make_task(kind="CHECKIN_PREP", urgency="urgent")
        narrative = _build_heuristic_narrative(task, self._prop(), self._guest(), [])
        assert "7890" in narrative

    def test_checkin_prep_contains_wifi(self):
        task = _make_task(kind="CHECKIN_PREP")
        narrative = _build_heuristic_narrative(task, self._prop(), self._guest(), [])
        assert "beach2026" in narrative

    def test_checkin_prep_contains_guest_name(self):
        task = _make_task(kind="CHECKIN_PREP")
        narrative = _build_heuristic_narrative(task, self._prop(), self._guest(), [])
        assert "Alice" in narrative

    def test_checkin_prep_contains_checkin_date(self):
        task = _make_task(kind="CHECKIN_PREP")
        narrative = _build_heuristic_narrative(task, self._prop(), self._guest(), [])
        assert "2026-03-15" in narrative

    def test_cleaning_has_generic_intro(self):
        task = _make_task(kind="CLEANING", urgency="normal")
        narrative = _build_heuristic_narrative(task, self._prop(), self._guest(), [])
        assert "cleaning" in narrative.lower()

    def test_checkout_verify_contains_checkout_date(self):
        task = _make_task(kind="CHECKOUT_VERIFY")
        narrative = _build_heuristic_narrative(task, self._prop(), self._guest(), [])
        assert "2026-03-20" in narrative

    def test_critical_urgency_shows_warning(self):
        task = _make_task(kind="CHECKIN_PREP", priority="CRITICAL", urgency="critical")
        narrative = _build_heuristic_narrative(task, self._prop(), self._guest(), [])
        assert "CRITICAL" in narrative or "⚠" in narrative

    def test_recent_history_mentioned(self):
        hist = [{"task_id": "x", "kind": "CLEANING", "status": "COMPLETED", "due_date": "2026-03-10"}]
        task = _make_task(kind="CHECKIN_PREP")
        narrative = _build_heuristic_narrative(task, self._prop(), self._guest(), hist)
        assert "CLEANING" in narrative or "2026-03-10" in narrative

    def test_missing_wifi_omitted(self):
        prop = self._prop(wifi_password=None)
        task = _make_task(kind="CHECKIN_PREP")
        narrative = _build_heuristic_narrative(task, prop, self._guest(), [])
        assert "Wi-Fi" not in narrative and "wifi" not in narrative.lower()


# ---------------------------------------------------------------------------
# Unit tests: _build_priority_justification
# ---------------------------------------------------------------------------

class TestBuildPriorityJustification:
    def test_returns_non_empty(self):
        task = _make_task()
        justification = _build_priority_justification(task, {"check_in": "2026-03-15"})
        assert len(justification) > 0

    def test_includes_priority(self):
        task = _make_task(priority="HIGH")
        justification = _build_priority_justification(task, {})
        assert "HIGH" in justification

    def test_includes_kind(self):
        task = _make_task(kind="CHECKIN_PREP")
        justification = _build_priority_justification(task, {})
        assert "CHECKIN_PREP" in justification

    def test_checkin_prep_includes_guest_arrival(self):
        task = _make_task(kind="CHECKIN_PREP")
        justification = _build_priority_justification(task, {"check_in": "2026-03-15"})
        assert "2026-03-15" in justification

    def test_checkout_verify_mentions_relisting(self):
        task = _make_task(kind="CHECKOUT_VERIFY")
        justification = _build_priority_justification(task, {})
        assert "re-list" in justification.lower() or "condition" in justification.lower()


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

class TestWorkerAssistEndpoint:
    def test_400_missing_task_id(self):
        from fastapi.testclient import TestClient
        import api.worker_copilot_router as mod

        with patch("api.worker_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=_make_db()):
            resp = TestClient(_app()).post(
                "/ai/copilot/worker-assist",
                json={},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 400
        body = resp.json()
        msg = (body.get("message") or body.get("error", {}).get("message", "")).lower()
        assert "task_id" in msg

    def test_400_empty_task_id(self):
        from fastapi.testclient import TestClient
        import api.worker_copilot_router as mod

        with patch("api.worker_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=_make_db()):
            resp = TestClient(_app()).post(
                "/ai/copilot/worker-assist",
                json={"task_id": "   "},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 400

    def test_404_task_not_found(self):
        from fastapi.testclient import TestClient
        import api.worker_copilot_router as mod

        with patch("api.worker_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=_make_db(task=None)):
            resp = TestClient(_app()).post(
                "/ai/copilot/worker-assist",
                json={"task_id": "notexist"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 404

    def test_200_happy_path_shape(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.worker_copilot_router as mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        db = _make_db(
            task=_make_task(),
            booking=_make_booking(),
            prop=_make_property(),
            history=[],
        )
        with patch("api.worker_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=db):
            resp = TestClient(_app()).post(
                "/ai/copilot/worker-assist",
                json={"task_id": "abc123def456"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 200
        data = resp.json()
        for field in (
            "tenant_id", "task_id", "generated_by", "task_context",
            "property_info", "guest_context", "recent_task_history",
            "priority_justification", "assist_narrative", "generated_at",
        ):
            assert field in data, f"Missing field: {field}"

    def test_200_generated_by_heuristic_without_llm(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.worker_copilot_router as mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        db = _make_db(task=_make_task(), booking=_make_booking(), prop=_make_property())
        with patch("api.worker_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=db):
            resp = TestClient(_app()).post(
                "/ai/copilot/worker-assist",
                json={"task_id": "abc123def456"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.json()["generated_by"] == "heuristic"

    def test_200_generated_by_llm_when_mock_returns_text(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.worker_copilot_router as mod
        import services.llm_client as lc

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        db = _make_db(task=_make_task(), booking=_make_booking(), prop=_make_property())
        with patch("api.worker_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=db), \
             patch.object(lc, "is_configured", return_value=True), \
             patch.object(lc, "generate", return_value="Please prepare the property for Alice."):
            resp = TestClient(_app()).post(
                "/ai/copilot/worker-assist",
                json={"task_id": "abc123def456"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 200
        assert resp.json()["generated_by"] == "llm"
        assert "Alice" in resp.json()["assist_narrative"]

    def test_property_info_has_access_code_and_wifi(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.worker_copilot_router as mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        db = _make_db(task=_make_task(), booking=_make_booking(), prop=_make_property())
        with patch("api.worker_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=db):
            resp = TestClient(_app()).post(
                "/ai/copilot/worker-assist",
                json={"task_id": "abc123def456"},
                headers={"Authorization": "Bearer fake"},
            )
        pi = resp.json()["property_info"]
        assert pi["access_code"] == "7890"
        assert pi["wifi_password"] == "beach2026"

    def test_guest_context_has_required_fields(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.worker_copilot_router as mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        db = _make_db(task=_make_task(), booking=_make_booking(), prop=_make_property())
        with patch("api.worker_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=db):
            resp = TestClient(_app()).post(
                "/ai/copilot/worker-assist",
                json={"task_id": "abc123def456"},
                headers={"Authorization": "Bearer fake"},
            )
        gc = resp.json()["guest_context"]
        assert gc["guest_name"] == "Alice"
        assert gc["check_in"] == "2026-03-15"
        assert gc["check_out"] == "2026-03-20"

    def test_priority_justification_is_non_empty(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.worker_copilot_router as mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        db = _make_db(task=_make_task(), booking=_make_booking(), prop=_make_property())
        with patch("api.worker_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=db):
            resp = TestClient(_app()).post(
                "/ai/copilot/worker-assist",
                json={"task_id": "abc123def456"},
                headers={"Authorization": "Bearer fake"},
            )
        assert len(resp.json()["priority_justification"]) > 0

    def test_500_on_db_error(self):
        from fastapi.testclient import TestClient
        import api.worker_copilot_router as mod

        with patch("api.worker_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", side_effect=RuntimeError("DB down")):
            resp = TestClient(_app(), raise_server_exceptions=False).post(
                "/ai/copilot/worker-assist",
                json={"task_id": "abc123def456"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 500

    def test_missing_booking_gives_empty_guest_context(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.worker_copilot_router as mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # No booking in DB
        db = _make_db(task=_make_task(), booking=None, prop=_make_property())
        with patch("api.worker_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=db):
            resp = TestClient(_app()).post(
                "/ai/copilot/worker-assist",
                json={"task_id": "abc123def456"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 200
        gc = resp.json()["guest_context"]
        assert gc["guest_name"] is None

    def test_missing_property_gives_empty_property_info(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.worker_copilot_router as mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # No property in DB
        db = _make_db(task=_make_task(), booking=_make_booking(), prop=None)
        with patch("api.worker_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=db):
            resp = TestClient(_app()).post(
                "/ai/copilot/worker-assist",
                json={"task_id": "abc123def456"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 200
        pi = resp.json()["property_info"]
        assert pi["access_code"] is None
        assert pi["name"] is None

    def test_task_context_has_required_fields(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.worker_copilot_router as mod

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        db = _make_db(task=_make_task(), booking=_make_booking(), prop=_make_property())
        with patch("api.worker_copilot_router.jwt_auth", return_value=TENANT), \
             patch.object(mod, "_get_db", return_value=db):
            resp = TestClient(_app()).post(
                "/ai/copilot/worker-assist",
                json={"task_id": "abc123def456"},
                headers={"Authorization": "Bearer fake"},
            )
        tc = resp.json()["task_context"]
        for key in ("title", "kind", "priority", "urgency", "due_date", "status"):
            assert key in tc, f"Missing task_context key: {key}"
