"""
Phase 108 — Financial List Query API contract tests.

GET /financial  — list financial fact records with filters:
  - ?provider=bookingcom
  - ?month=YYYY-MM
  - ?limit=N (server-clamped 1–100, default 50)

Uses FastAPI TestClient + mocked Supabase — no live DB required.

Groups:
  A — 200 success (no filters, with provider, with month, with both)
  B — Validation errors (bad month format)
  C — Limit clamping (below min, above max, valid)
  D — Tenant isolation
  E — Auth guard
  F — Response schema
  G — Edge cases (empty result, Supabase error, limit default)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Test app builder
# ---------------------------------------------------------------------------

def _make_test_app(mock_db=None, mock_tenant_id="tenant_test"):
    from fastapi import FastAPI
    from api.financial_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth():
        return mock_tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Reusable row fixture
# ---------------------------------------------------------------------------

def _row(
    booking_id="bookingcom_R001",
    tenant_id="tenant_test",
    provider="bookingcom",
    total_price="300.0000",
    currency="EUR",
    ota_commission="45.0000",
    taxes=None,
    fees=None,
    net_to_property="255.0000",
    source_confidence="FULL",
    event_kind="BOOKING_CREATED",
    recorded_at="2026-03-09T00:00:00+00:00",
):
    return {
        "id": 1,
        "booking_id": booking_id,
        "tenant_id": tenant_id,
        "provider": provider,
        "total_price": total_price,
        "currency": currency,
        "ota_commission": ota_commission,
        "taxes": taxes,
        "fees": fees,
        "net_to_property": net_to_property,
        "source_confidence": source_confidence,
        "event_kind": event_kind,
        "recorded_at": recorded_at,
    }


def _mock_db_list(rows):
    """Build a MagicMock chain that ends with execute() returning the given rows."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    # Stub all chaining calls to return the same chain object
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lt.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value = chain
    return mock_db, chain


# ---------------------------------------------------------------------------
# Group A — 200 success variants
# ---------------------------------------------------------------------------

class TestListFinancialSuccess:

    def test_no_filters_returns_200(self):
        rows = [_row(booking_id=f"bookingcom_R00{i}") for i in range(3)]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial")

        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == "tenant_test"
        assert body["count"] == 3
        assert body["limit"] == 50  # default
        assert len(body["records"]) == 3

    def test_provider_filter_returns_200(self):
        rows = [_row(provider="airbnb", booking_id="airbnb_A001")]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial?provider=airbnb")

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["records"][0]["provider"] == "airbnb"

    def test_month_filter_returns_200(self):
        rows = [_row(recorded_at="2026-03-09T00:00:00+00:00")]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial?month=2026-03")

        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_provider_and_month_combined_returns_200(self):
        rows = [_row(provider="expedia", booking_id="expedia_E001")]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial?provider=expedia&month=2026-03")

        assert resp.status_code == 200
        assert resp.json()["records"][0]["provider"] == "expedia"

    def test_december_month_boundary_is_correct(self):
        """month=YYYY-12 must compute next boundary as YYYY+1-01, not YYYY-13."""
        rows = [_row(recorded_at="2026-12-15T00:00:00+00:00")]
        mock_db, chain = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial?month=2026-12")

        assert resp.status_code == 200  # would 500 if month boundary arithmetic fails


# ---------------------------------------------------------------------------
# Group B — Validation errors
# ---------------------------------------------------------------------------

class TestListFinancialValidation:

    @pytest.mark.parametrize("bad_month", [
        "2026-13",   # month 13
        "2026-00",   # month 0
        "26-03",     # 2-digit year
        "2026/03",   # wrong separator
        "March",     # plain text
        "2026-3",    # no zero padding
        "",          # empty (treated as None by FastAPI — 200, not 400)
    ])
    def test_invalid_month_returns_400(self, bad_month):
        if bad_month == "":
            pytest.skip("Empty string treated as absent by FastAPI — not a validation error")
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get(f"/financial?month={bad_month}")

        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == "VALIDATION_ERROR"
        assert "month" in body.get("detail", "").lower()

    def test_valid_month_formats_accepted(self):
        for month in ["2026-01", "2026-12", "2025-06"]:
            mock_db, _ = _mock_db_list([])
            client = _make_test_app(mock_db)
            with patch("api.financial_router._get_supabase_client", return_value=mock_db):
                resp = client.get(f"/financial?month={month}")
            assert resp.status_code == 200, f"Expected 200 for month={month}"


# ---------------------------------------------------------------------------
# Group C — Limit clamping
# ---------------------------------------------------------------------------

class TestListFinancialLimit:

    def test_limit_default_is_50(self):
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial")

        assert resp.json()["limit"] == 50

    def test_limit_below_min_clamped_to_1(self):
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial?limit=0")

        assert resp.json()["limit"] == 1

    def test_limit_above_max_clamped_to_100(self):
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial?limit=999")

        assert resp.json()["limit"] == 100

    def test_limit_10_respected(self):
        mock_db, _ = _mock_db_list([_row() for _ in range(3)])
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial?limit=10")

        assert resp.json()["limit"] == 10


# ---------------------------------------------------------------------------
# Group D — Tenant isolation
# ---------------------------------------------------------------------------

class TestListFinancialTenantIsolation:

    def test_tenant_id_scoped_in_query(self):
        """Records returned belong only to the authenticated tenant."""
        rows = [_row(tenant_id="tenant_a", booking_id="bookingcom_A001")]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db, mock_tenant_id="tenant_a")

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial")

        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == "tenant_a"

    def test_other_tenant_sees_empty_list(self):
        """If a different tenant has no records, list returns empty (not 404)."""
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db, mock_tenant_id="attacker")

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial")

        assert resp.status_code == 200
        assert resp.json()["count"] == 0
        assert resp.json()["records"] == []


# ---------------------------------------------------------------------------
# Group E — Auth guard
# ---------------------------------------------------------------------------

class TestListFinancialAuth:

    def test_no_auth_returns_403(self):
        from fastapi import FastAPI, HTTPException
        from api.financial_router import router
        from api.auth import jwt_auth

        app = FastAPI()

        async def _reject():
            raise HTTPException(status_code=403, detail="AUTH_FAILED")

        app.dependency_overrides[jwt_auth] = _reject
        app.include_router(router)
        client = TestClient(app)

        resp = client.get("/financial")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Group F — Response schema
# ---------------------------------------------------------------------------

class TestListFinancialResponseSchema:

    def test_envelope_fields_present(self):
        rows = [_row()]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial")

        body = resp.json()
        assert "tenant_id" in body
        assert "count" in body
        assert "limit" in body
        assert "records" in body

    def test_record_fields_present(self):
        rows = [_row()]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial")

        record = resp.json()["records"][0]
        required = {
            "booking_id", "tenant_id", "provider",
            "total_price", "currency", "ota_commission",
            "taxes", "fees", "net_to_property",
            "source_confidence", "event_kind", "recorded_at",
        }
        assert required.issubset(set(record.keys()))

    def test_count_matches_records_length(self):
        rows = [_row(booking_id=f"bookingcom_R{i:03d}") for i in range(5)]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial")

        body = resp.json()
        assert body["count"] == len(body["records"]) == 5

    def test_booking_state_not_touched(self):
        """Confirm booking_state table is never queried."""
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            client.get("/financial")

        # The only table call must be to booking_financial_facts
        table_calls = [str(c) for c in mock_db.table.call_args_list]
        assert not any("booking_state" in c for c in table_calls)


# ---------------------------------------------------------------------------
# Group G — Edge cases
# ---------------------------------------------------------------------------

class TestListFinancialEdgeCases:

    def test_empty_result_returns_200_not_404(self):
        mock_db, _ = _mock_db_list([])
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial")

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["records"] == []

    def test_supabase_exception_returns_500(self):
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("DB down")
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value = chain
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial")

        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == "INTERNAL_ERROR"
        assert "DB down" not in str(body)

    def test_none_financial_fields_serialized_as_null(self):
        rows = [_row(taxes=None, fees=None, ota_commission=None)]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial")

        record = resp.json()["records"][0]
        assert record["taxes"] is None
        assert record["fees"] is None
        assert record["ota_commission"] is None

    def test_multiple_providers_in_result(self):
        rows = [
            _row(provider="bookingcom", booking_id="bookingcom_B001"),
            _row(provider="airbnb",     booking_id="airbnb_A001"),
            _row(provider="expedia",    booking_id="expedia_E001"),
        ]
        mock_db, _ = _mock_db_list(rows)
        client = _make_test_app(mock_db)

        with patch("api.financial_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/financial")

        providers = {r["provider"] for r in resp.json()["records"]}
        assert providers == {"bookingcom", "airbnb", "expedia"}
