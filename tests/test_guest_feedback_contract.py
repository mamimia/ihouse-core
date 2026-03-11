"""
Phase 247 — Guest Feedback Collection API
Contract test suite.

Groups:
    A — POST /guest-feedback/{booking_id} — happy path
    B — POST validation errors
    C — POST booking not found
    D — GET /admin/guest-feedback — response shape
    E — GET empty tenant
    F — GET NPS calculation
    G — GET category breakdown
    H — GET by_property aggregation
    I — GET date filtering (query params)
    J — Route registration
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

_BEARER = {"Authorization": "Bearer test-token"}
_ADMIN_URL = "/admin/guest-feedback"
_PATCH_DB = "api.guest_feedback_router._get_supabase_client"


# ---------------------------------------------------------------------------
# Fake DB helpers
# ---------------------------------------------------------------------------

def _make_db(bs_rows=None, fb_rows=None, *, insert_result=None):
    """
    bs_rows  — booking_state rows (for POST tenant lookup)
    fb_rows  — guest_feedback rows (for GET admin view)
    insert_result — rows returned from insert in POST
    """
    class _R:
        def __init__(self, d): self.data = d

    class _Q:
        def __init__(self, t, bsr, fbr, ir):
            self._t = t; self._bsr = bsr; self._fbr = fbr; self._ir = ir
            self._filters = {}; self._is_insert = False

        def select(self, *a): return self
        def eq(self, k, v):
            self._filters[k] = v
            return self
        def gte(self, *a): return self
        def lte(self, *a): return self
        def limit(self, *a): return self
        def order(self, *a, **kw): return self

        def insert(self, row):
            self._is_insert = True
            self._insert_row = row
            return self

        def execute(self):
            if self._is_insert:
                return _R(self._ir or [self._insert_row])
            if self._t == "booking_state":
                return _R(self._bsr)
            return _R(self._fbr)

    class _DB:
        def __init__(self, bsr, fbr, ir):
            self._bsr = bsr or []
            self._fbr = fbr or []
            self._ir = ir

        def table(self, name):
            return _Q(name, self._bsr, self._fbr, self._ir)

    return _DB(bs_rows, fb_rows, insert_result)


def _booking_state(tid="dev-tenant", pid="prop-1"):
    return [{"tenant_id": tid, "property_id": pid}]


def _feedback(rating=5, category="cleanliness", pid="prop-1"):
    return {"id": "f1", "booking_id": "b1", "property_id": pid,
            "rating": rating, "category": category,
            "comment": "Great!", "submitted_at": "2025-01-01T00:00:00Z"}


def _post_body(token="tok-1", rating=5, category="cleanliness", comment="Loved it"):
    return {
        "verification_token": token,
        "rating": rating,
        "category": category,
        "comment": comment,
    }


# ---------------------------------------------------------------------------
# Group A — POST happy path
# ---------------------------------------------------------------------------

class TestGroupAPost:
    def _submit(self, body=None, **kw):
        body = body or _post_body(**kw)
        db = _make_db(bs_rows=_booking_state(), insert_result=[{"id": "f-uuid", **body}])
        with patch(_PATCH_DB, return_value=db):
            return client.post("/guest-feedback/b1", json=body)

    def test_a1_returns_201(self):
        assert self._submit().status_code == 201

    def test_a2_response_has_message(self):
        assert "message" in self._submit().json()

    def test_a3_booking_id_echoed(self):
        assert self._submit().json()["booking_id"] == "b1"

    def test_a4_rating_echoed(self):
        assert self._submit(rating=4).json()["rating"] == 4

    def test_a5_nps_category_promoter(self):
        assert self._submit(rating=5).json()["nps_category"] == "promoter"

    def test_a6_nps_category_passive(self):
        assert self._submit(rating=4).json()["nps_category"] == "passive"

    def test_a7_nps_category_detractor(self):
        assert self._submit(rating=2).json()["nps_category"] == "detractor"


# ---------------------------------------------------------------------------
# Group B — POST validation errors
# ---------------------------------------------------------------------------

class TestGroupBValidation:
    def _post(self, body):
        db = _make_db(bs_rows=_booking_state())
        with patch(_PATCH_DB, return_value=db):
            return client.post("/guest-feedback/b1", json=body)

    def test_b1_missing_token(self):
        assert self._post({"rating": 5}).status_code == 400

    def test_b2_rating_above_5(self):
        assert self._post({"verification_token": "t", "rating": 6}).status_code == 400

    def test_b3_rating_below_1(self):
        assert self._post({"verification_token": "t", "rating": 0}).status_code == 400

    def test_b4_rating_string(self):
        assert self._post({"verification_token": "t", "rating": "five"}).status_code == 400

    def test_b5_missing_rating(self):
        assert self._post({"verification_token": "t"}).status_code == 400


# ---------------------------------------------------------------------------
# Group C — POST booking not found
# ---------------------------------------------------------------------------

class TestGroupCNotFound:
    def test_c1_booking_not_found_404(self):
        db = _make_db(bs_rows=[], fb_rows=[])
        with patch(_PATCH_DB, return_value=db):
            r = client.post("/guest-feedback/nonexistent", json=_post_body())
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Group D — GET admin response shape
# ---------------------------------------------------------------------------

class TestGroupDAdminShape:
    def _get(self, rows=None):
        db = _make_db(fb_rows=rows or [])
        with patch(_PATCH_DB, return_value=db):
            return client.get(_ADMIN_URL, headers=_BEARER)

    def test_d1_returns_200(self):
        assert self._get().status_code == 200

    def test_d2_required_keys(self):
        b = self._get().json()
        for k in ("tenant_id", "total_count", "avg_rating", "nps_score",
                   "category_breakdown", "by_property", "feedback"):
            assert k in b

    def test_d3_filters_echoed(self):
        b = self._get().json()
        assert "filters" in b


# ---------------------------------------------------------------------------
# Group E — GET empty tenant
# ---------------------------------------------------------------------------

class TestGroupEEmpty:
    def _body(self):
        with patch(_PATCH_DB, return_value=_make_db(fb_rows=[])):
            return client.get(_ADMIN_URL, headers=_BEARER).json()

    def test_e1_total_count_zero(self):
        assert self._body()["total_count"] == 0

    def test_e2_avg_rating_null(self):
        assert self._body()["avg_rating"] is None

    def test_e3_nps_null(self):
        assert self._body()["nps_score"] is None

    def test_e4_by_property_empty(self):
        assert self._body()["by_property"] == {}


# ---------------------------------------------------------------------------
# Group F — GET NPS calculation
# ---------------------------------------------------------------------------

class TestGroupFNPS:
    def _nps_body(self, ratings):
        rows = [{"property_id": "p1", "rating": r, "category": "value"} for r in ratings]
        with patch(_PATCH_DB, return_value=_make_db(fb_rows=rows)):
            return client.get(_ADMIN_URL, headers=_BEARER).json()

    def test_f1_all_promoters_nps_100(self):
        b = self._nps_body([5, 5, 5, 5])
        assert b["nps_score"] == pytest.approx(100.0)

    def test_f2_all_detractors_nps_minus_100(self):
        b = self._nps_body([1, 2, 3, 1])
        assert b["nps_score"] == pytest.approx(-100.0)

    def test_f3_mixed_nps(self):
        # 2 promoters, 1 passive, 1 detractor → (2-1)/4 × 100 = 25.0
        b = self._nps_body([5, 5, 4, 2])
        assert b["nps_score"] == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# Group G — GET category breakdown
# ---------------------------------------------------------------------------

class TestGroupGCategory:
    def test_g1_counts_categories(self):
        rows = [
            {"property_id": "p1", "rating": 5, "category": "cleanliness"},
            {"property_id": "p1", "rating": 4, "category": "cleanliness"},
            {"property_id": "p1", "rating": 3, "category": "location"},
        ]
        with patch(_PATCH_DB, return_value=_make_db(fb_rows=rows)):
            b = client.get(_ADMIN_URL, headers=_BEARER).json()
        assert b["category_breakdown"]["cleanliness"] == 2
        assert b["category_breakdown"]["location"] == 1

    def test_g2_null_category_counts_as_uncategorized(self):
        rows = [{"property_id": "p1", "rating": 5, "category": None}]
        with patch(_PATCH_DB, return_value=_make_db(fb_rows=rows)):
            b = client.get(_ADMIN_URL, headers=_BEARER).json()
        assert "uncategorized" in b["category_breakdown"]


# ---------------------------------------------------------------------------
# Group H — GET by_property
# ---------------------------------------------------------------------------

class TestGroupHByProperty:
    def test_h1_groups_by_property(self):
        rows = [
            {"property_id": "p1", "rating": 5, "category": "v"},
            {"property_id": "p2", "rating": 2, "category": "v"},
        ]
        with patch(_PATCH_DB, return_value=_make_db(fb_rows=rows)):
            b = client.get(_ADMIN_URL, headers=_BEARER).json()
        assert "p1" in b["by_property"]
        assert "p2" in b["by_property"]

    def test_h2_per_property_has_metrics(self):
        rows = [{"property_id": "p1", "rating": 5, "category": "v"}]
        with patch(_PATCH_DB, return_value=_make_db(fb_rows=rows)):
            b = client.get(_ADMIN_URL, headers=_BEARER).json()
        p = b["by_property"]["p1"]
        assert "count" in p and "avg_rating" in p and "nps_score" in p


# ---------------------------------------------------------------------------
# Group I — Route registration
# ---------------------------------------------------------------------------

class TestGroupIRoutes:
    def test_i1_post_route_registered(self):
        routes = [r.path for r in app.routes]
        assert "/guest-feedback/{booking_id}" in routes

    def test_i2_admin_route_registered(self):
        routes = [r.path for r in app.routes]
        assert "/admin/guest-feedback" in routes

    def test_i3_admin_returns_200_with_bearer(self):
        with patch(_PATCH_DB, return_value=_make_db(fb_rows=[])):
            assert client.get(_ADMIN_URL, headers=_BEARER).status_code == 200
