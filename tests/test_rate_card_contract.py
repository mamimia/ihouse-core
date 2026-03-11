"""
Phase 246 — Rate Card & Pricing Rules Engine
Contract test suite.

Groups:
    A — GET /properties/{id}/rate-cards response shape
    B — GET empty (no rate cards)
    C — POST creates rate card
    D — POST validation errors
    E — GET /check — no rate card found
    F — GET /check — within threshold (no alert)
    G — GET /check — alert above threshold
    H — GET /check — alert below threshold
    I — Pure helpers (price_deviation_detector)
    J — Route registration
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

_BEARER = {"Authorization": "Bearer test-token"}
_LIST_URL = "/properties/prop-1/rate-cards"
_POST_URL = "/properties/prop-1/rate-cards"
_CHECK_URL = "/properties/prop-1/rate-cards/check"
_PATCH_DB = "api.rate_card_router._get_supabase_client"


# ---------------------------------------------------------------------------
# Mock DB helpers
# ---------------------------------------------------------------------------

def _make_db(rows, *, upsert_result=None):
    class _R:
        def __init__(self, d): self.data = d
    class _Q:
        def __init__(self, r, ur): self._r = r; self._ur = ur
        def select(self, *a): return self
        def eq(self, *a): return self
        def order(self, *a, **kw): return self
        def upsert(self, row, **kw):
            self._upsert_row = row
            return self
        def execute(self):
            if hasattr(self, "_upsert_row"):
                return _R(self._ur or [self._upsert_row])
            return _R(self._r)
    class _DB:
        def __init__(self, r, ur): self._r = r; self._ur = ur
        def table(self, *a): return _Q(self._r, self._ur)
    return _DB(rows, upsert_result)


def _card(room_type="standard", season="high", base_rate="10000.00", currency="THB"):
    return {
        "id": "test-uuid",
        "property_id": "prop-1",
        "room_type": room_type,
        "season": season,
        "base_rate": base_rate,
        "currency": currency,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Group A — GET list response shape
# ---------------------------------------------------------------------------

class TestGroupAListShape:
    def _body(self, rows):
        with patch(_PATCH_DB, return_value=_make_db(rows)):
            return client.get(_LIST_URL, headers=_BEARER).json()

    def test_a1_returns_200(self):
        with patch(_PATCH_DB, return_value=_make_db([])):
            assert client.get(_LIST_URL, headers=_BEARER).status_code == 200

    def test_a2_required_keys(self):
        b = self._body([])
        for k in ("tenant_id", "property_id", "count", "rate_cards"):
            assert k in b

    def test_a3_property_echoed(self):
        assert self._body([])["property_id"] == "prop-1"

    def test_a4_rate_cards_is_list(self):
        assert isinstance(self._body([])["rate_cards"], list)


# ---------------------------------------------------------------------------
# Group B — GET empty
# ---------------------------------------------------------------------------

class TestGroupBEmpty:
    def _body(self):
        with patch(_PATCH_DB, return_value=_make_db([])):
            return client.get(_LIST_URL, headers=_BEARER).json()

    def test_b1_count_zero(self):
        assert self._body()["count"] == 0

    def test_b2_cards_empty(self):
        assert self._body()["rate_cards"] == []


# ---------------------------------------------------------------------------
# Group C — POST creates rate card
# ---------------------------------------------------------------------------

class TestGroupCPost:
    def _post(self, body, db=None):
        db = db or _make_db([], upsert_result=[body])
        with patch(_PATCH_DB, return_value=db):
            return client.post(_POST_URL, json=body, headers=_BEARER)

    def test_c1_returns_201(self):
        r = self._post({"room_type": "standard", "season": "high", "base_rate": 10000})
        assert r.status_code == 201

    def test_c2_response_has_rate_card(self):
        r = self._post({"room_type": "standard", "season": "high", "base_rate": 10000})
        assert "rate_card" in r.json()

    def test_c3_currency_defaults_to_thb(self):
        body = {"room_type": "standard", "season": "high", "base_rate": 10000}
        upsert_row = {**body, "currency": "THB"}
        db = _make_db([], upsert_result=[upsert_row])
        with patch(_PATCH_DB, return_value=db):
            r = client.post(_POST_URL, json=body, headers=_BEARER)
        assert r.json()["rate_card"]["currency"] == "THB"

    def test_c4_custom_currency_uppercased(self):
        body = {"room_type": "deluxe", "season": "low", "base_rate": 5000, "currency": "usd"}
        upsert_row = {**body, "currency": "USD"}
        db = _make_db([], upsert_result=[upsert_row])
        with patch(_PATCH_DB, return_value=db):
            r = client.post(_POST_URL, json=body, headers=_BEARER)
        assert r.json()["rate_card"]["currency"] == "USD"


# ---------------------------------------------------------------------------
# Group D — POST validation errors
# ---------------------------------------------------------------------------

class TestGroupDValidation:
    def _post(self, body):
        with patch(_PATCH_DB, return_value=_make_db([])):
            return client.post(_POST_URL, json=body, headers=_BEARER)

    def test_d1_missing_room_type(self):
        r = self._post({"season": "high", "base_rate": 5000})
        assert r.status_code == 400

    def test_d2_missing_season(self):
        r = self._post({"room_type": "standard", "base_rate": 5000})
        assert r.status_code == 400

    def test_d3_invalid_base_rate_string(self):
        r = self._post({"room_type": "standard", "season": "high", "base_rate": "bad"})
        assert r.status_code == 400

    def test_d4_negative_base_rate(self):
        r = self._post({"room_type": "standard", "season": "high", "base_rate": -100})
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Group E — GET /check — no matching rate card
# ---------------------------------------------------------------------------

class TestGroupECheckNoCard:
    def _check(self, **params):
        with patch(_PATCH_DB, return_value=_make_db([])):
            return client.get(_CHECK_URL, params=params, headers=_BEARER)

    def test_e1_returns_200(self):
        assert self._check(price=10000).status_code == 200

    def test_e2_no_rate_card_true(self):
        assert self._check(price=10000).json()["no_rate_card"] is True

    def test_e3_alert_false(self):
        assert self._check(price=10000).json()["alert"] is False

    def test_e4_base_rate_null(self):
        assert self._check(price=10000).json()["base_rate"] is None


# ---------------------------------------------------------------------------
# Group F — GET /check — within threshold (no alert)
# ---------------------------------------------------------------------------

class TestGroupFWithinThreshold:
    def _check(self, price, **params):
        cards = [{"room_type": "standard", "season": "high", "base_rate": "10000.00", "currency": "THB"}]
        with patch(_PATCH_DB, return_value=_make_db(cards)):
            return client.get(_CHECK_URL, params={"price": price, "currency": "THB", "season": "high", **params}, headers=_BEARER)

    def test_f1_exact_match_no_alert(self):
        assert self._check(10000).json()["alert"] is False

    def test_f2_within_15pct_no_alert(self):
        # 11000 is +10% — within threshold
        assert self._check(11000).json()["alert"] is False

    def test_f3_below_15pct_no_alert(self):
        # 9000 is -10% — within threshold
        assert self._check(9000).json()["alert"] is False


# ---------------------------------------------------------------------------
# Group G — GET /check — alert, price above threshold
# ---------------------------------------------------------------------------

class TestGroupGAlertAbove:
    def _check(self, price):
        cards = [{"room_type": "standard", "season": "high", "base_rate": "10000.00", "currency": "THB"}]
        with patch(_PATCH_DB, return_value=_make_db(cards)):
            return client.get(_CHECK_URL, params={"price": price, "currency": "THB", "season": "high"}, headers=_BEARER)

    def test_g1_alert_true(self):
        # 12000 = +20% — above threshold
        assert self._check(12000).json()["alert"] is True

    def test_g2_direction_above(self):
        assert self._check(12000).json()["direction"] == "above"

    def test_g3_deviation_pct_present(self):
        body = self._check(12000).json()
        assert body["deviation_pct"] is not None
        assert float(body["deviation_pct"]) == pytest.approx(20.0, abs=0.1)


# ---------------------------------------------------------------------------
# Group H — GET /check — alert, price below threshold
# ---------------------------------------------------------------------------

class TestGroupHAlertBelow:
    def _check(self, price):
        cards = [{"room_type": "standard", "season": "high", "base_rate": "10000.00", "currency": "THB"}]
        with patch(_PATCH_DB, return_value=_make_db(cards)):
            return client.get(_CHECK_URL, params={"price": price, "currency": "THB", "season": "high"}, headers=_BEARER)

    def test_h1_alert_true(self):
        # 8000 = -20% — below threshold
        assert self._check(8000).json()["alert"] is True

    def test_h2_direction_below(self):
        assert self._check(8000).json()["direction"] == "below"


# ---------------------------------------------------------------------------
# Group I — Pure helpers (price_deviation_detector)
# ---------------------------------------------------------------------------

class TestGroupIDetector:
    def _run(self, incoming, base_rate, season="high", room_type="standard", currency="THB"):
        from services.price_deviation_detector import check_price_deviation
        cards = [{"room_type": room_type, "season": season, "base_rate": str(base_rate), "currency": currency}]
        return check_price_deviation(
            booking_id="tst",
            property_id="p1",
            incoming_price=Decimal(str(incoming)),
            currency=currency,
            rate_cards=cards,
            season=season,
        )

    def test_i1_no_alert_exact(self):
        r = self._run(10000, 10000)
        assert r.alert is False

    def test_i2_alert_above(self):
        r = self._run(12000, 10000)
        assert r.alert is True and r.direction == "above"

    def test_i3_alert_below(self):
        r = self._run(8000, 10000)
        assert r.alert is True and r.direction == "below"

    def test_i4_no_rate_card_when_currency_mismatch(self):
        from services.price_deviation_detector import check_price_deviation
        cards = [{"room_type": "standard", "season": "high", "base_rate": "10000", "currency": "USD"}]
        r = check_price_deviation(
            booking_id="t", property_id="p", incoming_price=Decimal("10000"),
            currency="THB", rate_cards=cards,
        )
        assert r.no_rate_card is True

    def test_i5_season_inference_november_high(self):
        from services.price_deviation_detector import _infer_season
        assert _infer_season(11) == "high"

    def test_i6_season_inference_july_low(self):
        from services.price_deviation_detector import _infer_season
        assert _infer_season(7) == "low"


# ---------------------------------------------------------------------------
# Group J — Route registration
# ---------------------------------------------------------------------------

class TestGroupJRoutes:
    def test_j1_list_route_registered(self):
        routes = [r.path for r in app.routes]
        assert "/properties/{property_id}/rate-cards" in routes

    def test_j2_check_route_registered(self):
        routes = [r.path for r in app.routes]
        assert "/properties/{property_id}/rate-cards/check" in routes

    def test_j3_list_returns_200_with_auth(self):
        with patch(_PATCH_DB, return_value=_make_db([])):
            assert client.get(_LIST_URL, headers=_BEARER).status_code == 200
