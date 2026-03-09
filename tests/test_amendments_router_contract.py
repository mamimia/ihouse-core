"""
Phase 104 — Amendment History Router Contract Tests

Uses FastAPI TestClient + mocked Supabase — no live DB required.
Pattern: identical to test_financial_router_contract.py (Phase 67).

Structure:
  Group A — Happy path: 200, booking amended once
  Group B — Empty amendments: booking exists but has never been amended
  Group C — Unknown booking: 404 when no rows found for this tenant at all
  Group D — Auth: 403 when JWT invalid
  Group E — Multiple amendments: count, ordering, field correctness
  Group F — Tenant isolation + 500 error
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.auth import jwt_auth
from api.amendments_router import router


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------

def _make_test_app(mock_tenant_id: str = "tenant_test") -> TestClient:
    app = FastAPI()

    async def _stub_auth():
        return mock_tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app)


def _reject_auth_app() -> TestClient:
    app = FastAPI()

    async def _reject():
        raise HTTPException(status_code=403, detail="AUTH_FAILED")

    app.dependency_overrides[jwt_auth] = _reject
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# DB row fixture
# ---------------------------------------------------------------------------

def _amended_row(
    booking_id: str = "bookingcom_BK-001",
    tenant_id: str = "tenant_test",
    provider: str = "bookingcom",
    total_price: str = "1100.00",
    currency: str = "USD",
    ota_commission: str = "165.00",
    net_to_property: str = "935.00",
    source_confidence: str = "FULL",
    recorded_at: str = "2026-06-20T12:00:00+00:00",
) -> dict:
    return {
        "id": 2,
        "booking_id": booking_id,
        "tenant_id": tenant_id,
        "provider": provider,
        "total_price": total_price,
        "currency": currency,
        "ota_commission": ota_commission,
        "taxes": None,
        "fees": None,
        "net_to_property": net_to_property,
        "source_confidence": source_confidence,
        "event_kind": "BOOKING_AMENDED",
        "recorded_at": recorded_at,
    }


def _created_row(booking_id: str = "bookingcom_BK-001") -> dict:
    return {
        "id": 1,
        "booking_id": booking_id,
        "tenant_id": "tenant_test",
        "event_kind": "BOOKING_CREATED",
        "recorded_at": "2026-06-15T10:00:00+00:00",
    }


def _mock_db_amended_then_exists(amended_rows: list, exists_rows: list) -> MagicMock:
    """
    Mock where:
    - first .execute() (BOOKING_AMENDED query) returns amended_rows
    - second .execute() (existence check) returns exists_rows
    """
    mock_db = MagicMock()
    execute_mock = MagicMock()
    execute_mock.side_effect = [
        MagicMock(data=amended_rows),
        MagicMock(data=exists_rows),
    ]
    (
        mock_db.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .eq.return_value
        .order.return_value
        .execute
    ) = execute_mock

    # Existence check — separate chain without event_kind eq
    (
        mock_db.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .limit.return_value
        .execute
    ) = execute_mock

    return mock_db


def _mock_db_with_amended(rows: list) -> MagicMock:
    """Mock where BOOKING_AMENDED query returns rows (existence check not needed)."""
    mock_db = MagicMock()
    (
        mock_db.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .eq.return_value
        .order.return_value
        .execute.return_value
    ) = MagicMock(data=rows)
    return mock_db


# ---------------------------------------------------------------------------
# Group A — Happy path: booking amended once
# ---------------------------------------------------------------------------

class TestGroupAHappyPath:

    def test_a1_returns_200(self) -> None:
        mock_db = _mock_db_with_amended([_amended_row()])
        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/amendments/bookingcom_BK-001")
        assert resp.status_code == 200

    def test_a2_response_has_booking_id(self) -> None:
        mock_db = _mock_db_with_amended([_amended_row()])
        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            body = client.get("/amendments/bookingcom_BK-001").json()
        assert body["booking_id"] == "bookingcom_BK-001"

    def test_a3_response_has_amendment_count(self) -> None:
        mock_db = _mock_db_with_amended([_amended_row()])
        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            body = client.get("/amendments/bookingcom_BK-001").json()
        assert body["amendment_count"] == 1

    def test_a4_response_has_amendments_list(self) -> None:
        mock_db = _mock_db_with_amended([_amended_row()])
        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            body = client.get("/amendments/bookingcom_BK-001").json()
        assert isinstance(body["amendments"], list)
        assert len(body["amendments"]) == 1

    def test_a5_amendment_entry_has_required_fields(self) -> None:
        mock_db = _mock_db_with_amended([_amended_row()])
        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            body = client.get("/amendments/bookingcom_BK-001").json()
        entry = body["amendments"][0]
        required = {
            "booking_id", "provider", "currency", "total_price",
            "ota_commission", "net_to_property", "source_confidence", "recorded_at",
        }
        assert required.issubset(set(entry.keys()))

    def test_a6_amendment_entry_has_correct_net(self) -> None:
        mock_db = _mock_db_with_amended([_amended_row(net_to_property="935.00")])
        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            body = client.get("/amendments/bookingcom_BK-001").json()
        assert body["amendments"][0]["net_to_property"] == "935.00"

    def test_a7_amendment_entry_has_correct_currency(self) -> None:
        mock_db = _mock_db_with_amended([_amended_row(currency="EUR")])
        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            body = client.get("/amendments/bookingcom_BK-001").json()
        assert body["amendments"][0]["currency"] == "EUR"

    def test_a8_response_has_tenant_id(self) -> None:
        mock_db = _mock_db_with_amended([_amended_row()])
        client = _make_test_app(mock_tenant_id="tenant_a")
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            body = client.get("/amendments/bookingcom_BK-001").json()
        assert body["tenant_id"] == "tenant_a"


# ---------------------------------------------------------------------------
# Group B — Empty amendments: booking exists but never amended
# ---------------------------------------------------------------------------

class TestGroupBNeverAmended:

    def test_b1_no_amendments_returns_200(self) -> None:
        """Booking exists (BOOKING_CREATED only) — should return 200 with empty list."""
        mock_db = MagicMock()
        # First call (BOOKING_AMENDED query) → empty
        # Second call (existence check) → has a row
        execute_mock = MagicMock()
        execute_mock.side_effect = [
            MagicMock(data=[]),        # BOOKING_AMENDED query
            MagicMock(data=[_created_row()]),  # existence check
        ]
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .execute
        ) = execute_mock
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .limit.return_value
            .execute
        ) = execute_mock

        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/amendments/bookingcom_BK-001")
        assert resp.status_code == 200

    def test_b2_empty_amendments_count_is_zero(self) -> None:
        mock_db = MagicMock()
        execute_mock = MagicMock()
        execute_mock.side_effect = [
            MagicMock(data=[]),
            MagicMock(data=[_created_row()]),
        ]
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .execute
        ) = execute_mock
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .limit.return_value
            .execute
        ) = execute_mock

        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            body = client.get("/amendments/bookingcom_BK-001").json()
        assert body["amendment_count"] == 0
        assert body["amendments"] == []


# ---------------------------------------------------------------------------
# Group C — Unknown booking: 404
# ---------------------------------------------------------------------------

class TestGroupCUnknownBooking:

    def test_c1_unknown_booking_returns_404(self) -> None:
        """No rows at all for this booking_id + tenant_id → 404."""
        mock_db = MagicMock()
        execute_mock = MagicMock()
        execute_mock.side_effect = [
            MagicMock(data=[]),   # BOOKING_AMENDED query
            MagicMock(data=[]),   # existence check — also empty
        ]
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .execute
        ) = execute_mock
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .limit.return_value
            .execute
        ) = execute_mock

        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/amendments/bookingcom_UNKNOWN")
        assert resp.status_code == 404

    def test_c2_404_code_is_booking_not_found(self) -> None:
        mock_db = MagicMock()
        execute_mock = MagicMock()
        execute_mock.side_effect = [
            MagicMock(data=[]),
            MagicMock(data=[]),
        ]
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .execute
        ) = execute_mock
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .limit.return_value
            .execute
        ) = execute_mock

        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            body = client.get("/amendments/bookingcom_UNKNOWN").json()
        assert body["code"] == "BOOKING_NOT_FOUND"


# ---------------------------------------------------------------------------
# Group D — Auth
# ---------------------------------------------------------------------------

class TestGroupDAuth:

    def test_d1_no_auth_returns_403(self) -> None:
        client = _reject_auth_app()
        resp = client.get("/amendments/bookingcom_BK-001")
        assert resp.status_code == 403

    def test_d2_valid_auth_passes(self) -> None:
        mock_db = _mock_db_with_amended([_amended_row()])
        client = _make_test_app(mock_tenant_id="valid_tenant")
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/amendments/bookingcom_BK-001")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Group E — Multiple amendments
# ---------------------------------------------------------------------------

class TestGroupEMultipleAmendments:

    def test_e1_two_amendments_gives_count_2(self) -> None:
        rows = [
            _amended_row(recorded_at="2026-06-20T10:00:00+00:00"),
            _amended_row(recorded_at="2026-06-25T10:00:00+00:00", total_price="1200.00"),
        ]
        mock_db = _mock_db_with_amended(rows)
        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            body = client.get("/amendments/bookingcom_BK-001").json()
        assert body["amendment_count"] == 2
        assert len(body["amendments"]) == 2

    def test_e2_amendments_ordered_oldest_first(self) -> None:
        rows = [
            _amended_row(recorded_at="2026-06-20T10:00:00+00:00", total_price="1100.00"),
            _amended_row(recorded_at="2026-06-25T10:00:00+00:00", total_price="1200.00"),
        ]
        mock_db = _mock_db_with_amended(rows)
        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            body = client.get("/amendments/bookingcom_BK-001").json()
        # First amendment (oldest) should have lower recorded_at
        assert body["amendments"][0]["recorded_at"] < body["amendments"][1]["recorded_at"]

    def test_e3_each_amendment_has_recorded_at(self) -> None:
        rows = [_amended_row(), _amended_row(recorded_at="2026-07-01T00:00:00+00:00")]
        mock_db = _mock_db_with_amended(rows)
        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            body = client.get("/amendments/bookingcom_BK-001").json()
        for entry in body["amendments"]:
            assert entry["recorded_at"] is not None


# ---------------------------------------------------------------------------
# Group F — Tenant isolation + 500
# ---------------------------------------------------------------------------

class TestGroupFIsolationAndErrors:

    def test_f1_tenant_isolation_gives_404(self) -> None:
        """Attacker sees no rows for victim booking → 404."""
        mock_db = MagicMock()
        execute_mock = MagicMock()
        execute_mock.side_effect = [
            MagicMock(data=[]),
            MagicMock(data=[]),
        ]
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .execute
        ) = execute_mock
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .limit.return_value
            .execute
        ) = execute_mock

        client = _make_test_app(mock_tenant_id="attacker")
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/amendments/victim_booking")
        assert resp.status_code == 404

    def test_f2_supabase_error_returns_500(self) -> None:
        mock_db = MagicMock()
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .execute.side_effect
        ) = RuntimeError("DB timeout")
        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/amendments/bookingcom_BK-001")
        assert resp.status_code == 500

    def test_f3_500_code_is_internal_error(self) -> None:
        mock_db = MagicMock()
        (
            mock_db.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .eq.return_value
            .order.return_value
            .execute.side_effect
        ) = RuntimeError("network error")
        client = _make_test_app()
        with patch("api.amendments_router._get_supabase_client", return_value=mock_db):
            body = client.get("/amendments/bookingcom_BK-001").json()
        assert body["code"] == "INTERNAL_ERROR"
