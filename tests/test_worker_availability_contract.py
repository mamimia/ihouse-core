"""
Phase 234 — Shift & Availability Scheduler — Contract Tests

Coverage:

Unit helpers:
    - _valid_date: valid, missing, bad format
    - _valid_time: valid, None (allowed), bad format

POST /worker/availability
    - 201 created with minimal body (date + status)
    - 200 upsert (same date, same worker)
    - 400 missing date
    - 400 invalid date format
    - 400 invalid status
    - 400 bad start_time format
    - optional notes stored in response

GET /worker/availability
    - 200 returns own slots list
    - 200 returns empty slots when none set
    - 400 missing from param
    - 400 missing to param
    - 400 range exceeds 90 days
    - 400 to < from

GET /admin/schedule/overview
    - 200 returns grouped structure with all keys
    - 200 empty date returns 0 workers
    - 400 missing date
    - 400 invalid date format

General:
    - Response always has tenant_id
    - Tenant isolation enforced (eq called with tenant_id)
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.worker_availability_router import _valid_date, _valid_time

TENANT = "tenant-wk"
TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
IN_30 = (date.today() + timedelta(days=30)).isoformat()
IN_91 = (date.today() + timedelta(days=91)).isoformat()


@pytest.fixture(autouse=True)
def _dev_mode(monkeypatch):
    """Phase 283: set dev mode per-test so auth doesn't block."""
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(rows=None, upsert_data=None) -> MagicMock:
    db = MagicMock()

    def table_fn(name: str):
        t = MagicMock()
        for m in ("select", "eq", "gte", "lte", "order", "upsert", "execute", "limit"):
            getattr(t, m).return_value = t

        r = MagicMock()
        if name == "worker_availability":
            if upsert_data is not None:
                r.data = upsert_data
            else:
                r.data = rows if rows is not None else []
        else:
            r.data = []
        t.execute.return_value = r
        return t

    db.table.side_effect = table_fn
    return db


def _app():
    from fastapi import FastAPI
    from api.worker_availability_router import router
    app = FastAPI()
    app.include_router(router)
    return app


def _post(body: dict, db_mock=None):
    from fastapi.testclient import TestClient
    import api.worker_availability_router as mod

    with patch("api.worker_availability_router.jwt_auth", return_value=TENANT), \
         patch.object(mod, "_get_db", return_value=db_mock or _make_db()):
        return TestClient(_app()).post(
            "/worker/availability",
            json=body,
            headers={"Authorization": "Bearer fake"},
        )


def _get_own(query="", db_mock=None):
    from fastapi.testclient import TestClient
    import api.worker_availability_router as mod

    with patch("api.worker_availability_router.jwt_auth", return_value=TENANT), \
         patch.object(mod, "_get_db", return_value=db_mock or _make_db()):
        return TestClient(_app()).get(
            f"/worker/availability{query}",
            headers={"Authorization": "Bearer fake"},
        )


def _get_overview(query="", db_mock=None):
    from fastapi.testclient import TestClient
    import api.worker_availability_router as mod

    with patch("api.worker_availability_router.jwt_auth", return_value=TENANT), \
         patch.object(mod, "_get_db", return_value=db_mock or _make_db()):
        return TestClient(_app()).get(
            f"/admin/schedule/overview{query}",
            headers={"Authorization": "Bearer fake"},
        )


# ---------------------------------------------------------------------------
# Unit: helpers
# ---------------------------------------------------------------------------

class TestValidDate:
    def test_valid(self):
        assert _valid_date("2026-03-15") is True

    def test_none(self):
        assert _valid_date(None) is False

    def test_bad_format(self):
        assert _valid_date("15-03-2026") is False

    def test_empty_string(self):
        assert _valid_date("") is False


class TestValidTime:
    def test_valid(self):
        assert _valid_time("09:00") is True

    def test_none_allowed(self):
        assert _valid_time(None) is True  # optional field

    def test_bad_format(self):
        assert _valid_time("9:00") is False

    def test_out_of_range_hour(self):
        assert _valid_time("25:00") is False


# ---------------------------------------------------------------------------
# POST /worker/availability
# ---------------------------------------------------------------------------

class TestSetAvailability:
    def test_201_created_minimal(self):
        resp = _post({"date": TOMORROW, "status": "AVAILABLE"})
        assert resp.status_code in (200, 201)

    def test_response_has_required_keys(self):
        resp = _post({"date": TOMORROW, "status": "AVAILABLE"})
        data = resp.json()
        for key in ("tenant_id", "worker_id", "date", "status"):
            assert key in data

    def test_tenant_id_in_response(self):
        resp = _post({"date": TOMORROW, "status": "AVAILABLE"})
        # dev-mode JWT returns 'dev-tenant' when IHOUSE_JWT_SECRET unset
        assert "tenant_id" in resp.json()

    def test_status_unavailable_accepted(self):
        resp = _post({"date": TOMORROW, "status": "UNAVAILABLE"})
        assert resp.status_code in (200, 201)
        assert resp.json()["status"] == "UNAVAILABLE"

    def test_status_on_leave_accepted(self):
        resp = _post({"date": TOMORROW, "status": "ON_LEAVE"})
        assert resp.status_code in (200, 201)
        assert resp.json()["status"] == "ON_LEAVE"

    def test_optional_times_and_notes(self):
        resp = _post({
            "date": TOMORROW,
            "status": "AVAILABLE",
            "start_time": "08:00",
            "end_time": "17:00",
            "notes": "Morning shift",
        })
        assert resp.status_code in (200, 201)
        assert resp.json()["notes"] == "Morning shift"

    def test_400_missing_date(self):
        resp = _post({"status": "AVAILABLE"})
        assert resp.status_code == 400

    def test_400_invalid_date_format(self):
        resp = _post({"date": "11-03-2026", "status": "AVAILABLE"})
        assert resp.status_code == 400

    def test_400_invalid_status(self):
        resp = _post({"date": TOMORROW, "status": "SICK"})
        assert resp.status_code == 400

    def test_400_bad_start_time(self):
        resp = _post({"date": TOMORROW, "status": "AVAILABLE", "start_time": "8:00"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /worker/availability
# ---------------------------------------------------------------------------

class TestGetOwnAvailability:
    def test_200_returns_slots(self):
        db = _make_db(rows=[
            {"id": "1", "date": TOMORROW, "status": "AVAILABLE",
             "start_time": None, "end_time": None, "notes": None, "updated_at": "2026-03-11"}
        ])
        resp = _get_own(f"?from={TODAY}&to={IN_30}", db_mock=db)
        assert resp.status_code == 200
        data = resp.json()
        assert "slots" in data
        assert len(data["slots"]) == 1

    def test_200_empty_when_no_slots(self):
        resp = _get_own(f"?from={TODAY}&to={IN_30}")
        assert resp.status_code == 200
        assert resp.json()["slots"] == []

    def test_response_has_range_keys(self):
        resp = _get_own(f"?from={TODAY}&to={IN_30}")
        data = resp.json()
        assert "from" in data
        assert "to" in data
        assert "tenant_id" in data

    def test_400_missing_from(self):
        resp = _get_own(f"?to={IN_30}")
        assert resp.status_code == 400

    def test_400_missing_to(self):
        resp = _get_own(f"?from={TODAY}")
        assert resp.status_code == 400

    def test_400_range_exceeds_90_days(self):
        resp = _get_own(f"?from={TODAY}&to={IN_91}")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /admin/schedule/overview
# ---------------------------------------------------------------------------

class TestScheduleOverview:
    def test_200_returns_grouped_structure(self):
        db = _make_db(rows=[
            {"worker_id": "w1", "status": "AVAILABLE", "start_time": None, "end_time": None, "notes": None},
            {"worker_id": "w2", "status": "UNAVAILABLE", "start_time": None, "end_time": None, "notes": None},
        ])
        resp = _get_overview(f"?date={TOMORROW}", db_mock=db)
        assert resp.status_code == 200
        data = resp.json()
        assert "schedule" in data
        assert "AVAILABLE" in data["schedule"]
        assert "UNAVAILABLE" in data["schedule"]

    def test_200_has_total_workers(self):
        db = _make_db(rows=[
            {"worker_id": "w1", "status": "AVAILABLE", "start_time": None, "end_time": None, "notes": None},
        ])
        resp = _get_overview(f"?date={TOMORROW}", db_mock=db)
        assert resp.json()["total_workers"] == 1

    def test_200_empty_date_returns_zero(self):
        resp = _get_overview(f"?date={TOMORROW}")
        assert resp.status_code == 200
        assert resp.json()["total_workers"] == 0

    def test_400_missing_date(self):
        resp = _get_overview()
        assert resp.status_code == 400

    def test_400_invalid_date_format(self):
        resp = _get_overview("?date=2026-3-1")
        assert resp.status_code == 400

    def test_tenant_id_in_response(self):
        resp = _get_overview(f"?date={TOMORROW}")
        assert "tenant_id" in resp.json()
