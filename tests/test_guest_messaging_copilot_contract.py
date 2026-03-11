"""
Phase 227 — Guest Messaging Copilot v1 — Contract Tests

Tests cover:
    _build_heuristic_draft:
        - check_in_instructions → contains property name, entry code, Wi-Fi
        - booking_confirmation  → contains check-in + check-out dates + nights
        - pre_arrival_info      → contains property + check-in date
        - check_out_reminder    → contains check-out time and key return note
        - issue_apology         → contains apology language
        - custom                → returns custom_prompt content

    _build_subject:
        - each intent → subject contains property name
        - pre_arrival_info with check_in → includes date in subject

    Language / salutation:
        - Thai (th) → salutation in Thai
        - Japanese (ja) → salutation ends with 様
        - Unsupported language → falls back to English

    POST /ai/copilot/guest-message-draft:
        - 400 when booking_id missing
        - 400 when intent missing
        - 400 unknown intent
        - 400 custom intent without custom_prompt
        - 404 booking not found
        - 200 valid request — heuristic, correct shape
        - generated_by = heuristic without LLM key
        - generated_by = llm when mock LLM returns text
        - unsupported language falls back to en
        - unsupported tone falls back to friendly
        - character_count matches len(draft)
        - context_used has all required keys
        - subject present and non-empty
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.guest_messaging_copilot import (
    _build_heuristic_draft,
    _build_subject,
)

TENANT = "tenant-test"
NOW = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(**kwargs) -> dict:
    base = {
        "booking_id": "airbnb_R123",
        "property_name": "Sunset Villa",
        "property_address": "123 Beach Road",
        "property_wifi": "beach2026",
        "property_checkin_time": "15:00",
        "property_checkout_time": "11:00",
        "property_access_code": "7890",
        "guest_name": "Alice",
        "guest_email": "alice@example.com",
        "check_in": "2026-04-01",
        "check_out": "2026-04-05",
        "provider": "airbnb",
        "lifecycle_status": "ACTIVE",
        "total_nights": 4,
    }
    base.update(kwargs)
    return base


def _mock_db_found(booking: dict | None = None, property_data: dict | None = None) -> MagicMock:
    db = MagicMock()

    def table_fn(name: str):
        t = MagicMock()
        for m in ("select", "eq", "limit", "execute"):
            getattr(t, m).return_value = t
        result = MagicMock()
        if name == "booking_state":
            result.data = [booking] if booking else [
                {
                    "booking_id": "airbnb_R123",
                    "provider": "airbnb",
                    "guest_name": "Alice",
                    "guest_email": "alice@example.com",
                    "check_in": "2026-04-01",
                    "check_out": "2026-04-05",
                    "lifecycle_status": "ACTIVE",
                    "property_id": "prop-1",
                    "source_confidence": "FULL",
                }
            ]
        elif name == "properties":
            result.data = [property_data] if property_data else [
                {
                    "property_id": "prop-1",
                    "name": "Sunset Villa",
                    "address": "123 Beach Road",
                    "wifi_password": "beach2026",
                    "checkin_time": "15:00",
                    "checkout_time": "11:00",
                    "access_code": "7890",
                }
            ]
        else:
            result.data = []
        t.execute.return_value = result
        return t

    db.table.side_effect = table_fn
    return db


def _mock_db_empty() -> MagicMock:
    db = MagicMock()
    t = MagicMock()
    for m in ("select", "eq", "limit", "execute"):
        getattr(t, m).return_value = t
    result = MagicMock()
    result.data = []
    t.execute.return_value = result
    db.table.return_value = t
    return db


def _app():
    from fastapi import FastAPI
    from api.guest_messaging_copilot import router
    app = FastAPI()
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# _build_heuristic_draft
# ---------------------------------------------------------------------------

class TestBuildHeuristicDraft:
    def test_check_in_instructions_contains_key_info(self):
        ctx = _ctx()
        draft = _build_heuristic_draft("check_in_instructions", ctx, "en", "friendly", None)
        assert "Sunset Villa" in draft
        assert "7890" in draft
        assert "beach2026" in draft
        assert "15:00" in draft

    def test_booking_confirmation_contains_dates(self):
        ctx = _ctx()
        draft = _build_heuristic_draft("booking_confirmation", ctx, "en", "friendly", None)
        assert "2026-04-01" in draft
        assert "2026-04-05" in draft
        assert "4 nights" in draft

    def test_pre_arrival_info_contains_property_and_date(self):
        ctx = _ctx()
        draft = _build_heuristic_draft("pre_arrival_info", ctx, "en", "professional", None)
        assert "Sunset Villa" in draft
        assert "2026-04-01" in draft

    def test_check_out_reminder_mentions_checkout_time(self):
        ctx = _ctx()
        draft = _build_heuristic_draft("check_out_reminder", ctx, "en", "brief", None)
        assert "11:00" in draft
        assert "2026-04-05" in draft

    def test_issue_apology_contains_apology(self):
        ctx = _ctx()
        draft = _build_heuristic_draft("issue_apology", ctx, "en", "professional", None)
        assert "apologi" in draft.lower() or "sincerely" in draft.lower()

    def test_custom_returns_custom_prompt_content(self):
        ctx = _ctx()
        draft = _build_heuristic_draft("custom", ctx, "en", "friendly",
                                       "Please note the pool is closed for maintenance.")
        assert "pool" in draft.lower()

    def test_thai_salutation(self):
        ctx = _ctx()
        draft = _build_heuristic_draft("booking_confirmation", ctx, "th", "friendly", None)
        assert "Alice" in draft
        # Thai salutation contains เรียน
        assert "เรียน" in draft

    def test_japanese_salutation_ends_with_sama(self):
        ctx = _ctx()
        draft = _build_heuristic_draft("check_in_instructions", ctx, "ja", "professional", None)
        assert "Alice様" in draft

    def test_unsupported_language_falls_back_to_english(self):
        ctx = _ctx()
        draft = _build_heuristic_draft("booking_confirmation", ctx, "klingon", "friendly", None)
        assert "Dear Alice" in draft


# ---------------------------------------------------------------------------
# _build_subject
# ---------------------------------------------------------------------------

class TestBuildSubject:
    def test_check_in_subject_contains_property(self):
        ctx = _ctx()
        subject = _build_subject("check_in_instructions", ctx, "en")
        assert "Sunset Villa" in subject

    def test_booking_confirmation_subject(self):
        ctx = _ctx()
        subject = _build_subject("booking_confirmation", ctx, "en")
        assert "Confirmed" in subject or "Booking" in subject

    def test_pre_arrival_includes_checkin_date(self):
        ctx = _ctx()
        subject = _build_subject("pre_arrival_info", ctx, "en")
        assert "2026-04-01" in subject

    def test_issue_apology_subject(self):
        ctx = _ctx()
        subject = _build_subject("issue_apology", ctx, "en")
        assert "Apologi" in subject or "Sorry" in subject or "Apolog" in subject


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

class TestGuestMessageDraftEndpoint:
    def test_400_missing_booking_id(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.guest_messaging_copilot as gm

        with patch("api.guest_messaging_copilot.jwt_auth", return_value=TENANT), \
             patch.object(gm, "_get_db", return_value=_mock_db_empty()):
            resp = TestClient(_app()).post(
                "/ai/copilot/guest-message-draft",
                json={"intent": "booking_confirmation"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 400
        assert "booking_id" in resp.json().get("error", {}).get("message", "").lower() or \
               "booking_id" in str(resp.json())

    def test_400_missing_intent(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.guest_messaging_copilot as gm

        with patch("api.guest_messaging_copilot.jwt_auth", return_value=TENANT), \
             patch.object(gm, "_get_db", return_value=_mock_db_empty()):
            resp = TestClient(_app()).post(
                "/ai/copilot/guest-message-draft",
                json={"booking_id": "B001"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 400

    def test_400_invalid_intent(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.guest_messaging_copilot as gm

        with patch("api.guest_messaging_copilot.jwt_auth", return_value=TENANT), \
             patch.object(gm, "_get_db", return_value=_mock_db_empty()):
            resp = TestClient(_app()).post(
                "/ai/copilot/guest-message-draft",
                json={"booking_id": "B001", "intent": "teleport_guest"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 400

    def test_400_custom_without_custom_prompt(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.guest_messaging_copilot as gm

        with patch("api.guest_messaging_copilot.jwt_auth", return_value=TENANT), \
             patch.object(gm, "_get_db", return_value=_mock_db_empty()):
            resp = TestClient(_app()).post(
                "/ai/copilot/guest-message-draft",
                json={"booking_id": "B001", "intent": "custom"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 400

    def test_404_booking_not_found(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.guest_messaging_copilot as gm

        with patch("api.guest_messaging_copilot.jwt_auth", return_value=TENANT), \
             patch.object(gm, "_get_db", return_value=_mock_db_empty()):
            resp = TestClient(_app()).post(
                "/ai/copilot/guest-message-draft",
                json={"booking_id": "MISSING123", "intent": "booking_confirmation"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 404

    def test_200_valid_heuristic_request(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.guest_messaging_copilot as gm

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("api.guest_messaging_copilot.jwt_auth", return_value=TENANT), \
             patch.object(gm, "_get_db", return_value=_mock_db_found()):
            resp = TestClient(_app()).post(
                "/ai/copilot/guest-message-draft",
                json={"booking_id": "airbnb_R123", "intent": "check_in_instructions"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["generated_by"] == "heuristic"
        assert data["intent"] == "check_in_instructions"

    def test_generated_by_llm_when_mock_returns_text(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.guest_messaging_copilot as gm
        import services.llm_client as lc

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        with patch("api.guest_messaging_copilot.jwt_auth", return_value=TENANT), \
             patch.object(gm, "_get_db", return_value=_mock_db_found()), \
             patch.object(lc, "is_configured", return_value=True), \
             patch.object(lc, "generate", return_value="Dear Alice,\n\nWe are delighted to welcome you to Sunset Villa! Your entry code is 7890.\n\nWarm regards,\nYour Host"):
            resp = TestClient(_app()).post(
                "/ai/copilot/guest-message-draft",
                json={"booking_id": "airbnb_R123", "intent": "check_in_instructions"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 200
        assert resp.json()["generated_by"] == "llm"

    def test_response_shape(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.guest_messaging_copilot as gm

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("api.guest_messaging_copilot.jwt_auth", return_value=TENANT), \
             patch.object(gm, "_get_db", return_value=_mock_db_found()):
            resp = TestClient(_app()).post(
                "/ai/copilot/guest-message-draft",
                json={"booking_id": "airbnb_R123", "intent": "booking_confirmation"},
                headers={"Authorization": "Bearer fake"},
            )
        data = resp.json()
        for field in ("tenant_id", "booking_id", "generated_by", "intent", "language",
                      "tone", "draft", "subject", "character_count", "context_used", "generated_at"):
            assert field in data, f"Missing: {field}"

    def test_character_count_equals_len_draft(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.guest_messaging_copilot as gm

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("api.guest_messaging_copilot.jwt_auth", return_value=TENANT), \
             patch.object(gm, "_get_db", return_value=_mock_db_found()):
            resp = TestClient(_app()).post(
                "/ai/copilot/guest-message-draft",
                json={"booking_id": "airbnb_R123", "intent": "check_out_reminder"},
                headers={"Authorization": "Bearer fake"},
            )
        data = resp.json()
        assert data["character_count"] == len(data["draft"])

    def test_context_used_has_required_keys(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.guest_messaging_copilot as gm

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("api.guest_messaging_copilot.jwt_auth", return_value=TENANT), \
             patch.object(gm, "_get_db", return_value=_mock_db_found()):
            resp = TestClient(_app()).post(
                "/ai/copilot/guest-message-draft",
                json={"booking_id": "airbnb_R123", "intent": "pre_arrival_info"},
                headers={"Authorization": "Bearer fake"},
            )
        ctx = resp.json()["context_used"]
        for key in ("property_name", "guest_name", "check_in", "check_out", "total_nights"):
            assert key in ctx

    def test_unsupported_language_falls_back_to_en(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.guest_messaging_copilot as gm

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("api.guest_messaging_copilot.jwt_auth", return_value=TENANT), \
             patch.object(gm, "_get_db", return_value=_mock_db_found()):
            resp = TestClient(_app()).post(
                "/ai/copilot/guest-message-draft",
                json={"booking_id": "airbnb_R123", "intent": "booking_confirmation", "language": "klingon"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.json()["language"] == "en"

    def test_invalid_tone_falls_back_to_friendly(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.guest_messaging_copilot as gm

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("api.guest_messaging_copilot.jwt_auth", return_value=TENANT), \
             patch.object(gm, "_get_db", return_value=_mock_db_found()):
            resp = TestClient(_app()).post(
                "/ai/copilot/guest-message-draft",
                json={"booking_id": "airbnb_R123", "intent": "booking_confirmation", "tone": "sarcastic"},
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.json()["tone"] == "friendly"

    def test_subject_is_non_empty(self, monkeypatch):
        from fastapi.testclient import TestClient
        import api.guest_messaging_copilot as gm

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("api.guest_messaging_copilot.jwt_auth", return_value=TENANT), \
             patch.object(gm, "_get_db", return_value=_mock_db_found()):
            resp = TestClient(_app()).post(
                "/ai/copilot/guest-message-draft",
                json={"booking_id": "airbnb_R123", "intent": "issue_apology"},
                headers={"Authorization": "Bearer fake"},
            )
        assert len(resp.json()["subject"]) > 0
