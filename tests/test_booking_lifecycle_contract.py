"""
Phase 242 — Booking Lifecycle State Machine Visualization API
Contract test suite.

Test groups:
    A — Response shape
    B — Empty tenant (no bookings, no events)
    C — State distribution (active/canceled counts)
    D — By-provider aggregation
    E — Transition counts from event_log
    F — Rates: amendment_rate_pct / cancellation_rate_pct
    G — Edge cases (zero denominator, unknown status)
    H — Auth + route registration
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

_BEARER = {"Authorization": "Bearer test-token"}
_URL = "/admin/bookings/lifecycle-states"
_PATCH_DB = "api.booking_lifecycle_router._get_supabase_client"


# ---------------------------------------------------------------------------
# Fake DB builders
# ---------------------------------------------------------------------------

def _fake_db_empty():
    """No bookings, no events."""
    class _R:
        data = []
    class _Q:
        def select(self, *a): return self
        def eq(self, *a): return self
        def in_(self, *a): return self
        def execute(self): return _R()
    class _DB:
        def table(self, *a): return _Q()
    return _DB()


def _fake_db_bookings(bookings, events=None):
    """
    Builds a fake DB from:
        bookings: list of {booking_id, source, status}
        events: list of {event_type} — defaults to []
    """
    events = events or []

    class _R:
        def __init__(self, d): self.data = d
    class _Q:
        def __init__(self, t): self._t = t; self._data = []
        def select(self, *a): return self
        def eq(self, *a): return self
        def in_(self, *a): return self
        def execute(self):
            return _R(self._data)
    class _BookingQ(_Q):
        def execute(self): return _R(bookings)
    class _EventQ(_Q):
        def execute(self): return _R(events)
    class _DB:
        def table(self, name):
            if name == "booking_state": return _BookingQ(name)
            return _EventQ(name)
    return _DB()


def _make_bookings():
    return [
        {"booking_id": "airbnb_a1", "source": "airbnb", "status": "active"},
        {"booking_id": "airbnb_a2", "source": "airbnb", "status": "active"},
        {"booking_id": "airbnb_c1", "source": "airbnb", "status": "canceled"},
        {"booking_id": "bookingcom_a1", "source": "bookingcom", "status": "active"},
        {"booking_id": "bookingcom_c1", "source": "bookingcom", "status": "canceled"},
    ]


def _make_events():
    return [
        {"event_type": "BOOKING_CREATED"},
        {"event_type": "BOOKING_CREATED"},
        {"event_type": "BOOKING_CREATED"},
        {"event_type": "BOOKING_AMENDED"},
        {"event_type": "BOOKING_CANCELED"},
    ]


# ---------------------------------------------------------------------------
# Group A — Response shape
# ---------------------------------------------------------------------------

class TestGroupAShape:
    def _body(self):
        with patch(_PATCH_DB, return_value=_fake_db_empty()):
            return client.get(_URL, headers=_BEARER).json()

    def test_a1_returns_200(self):
        with patch(_PATCH_DB, return_value=_fake_db_empty()):
            assert client.get(_URL, headers=_BEARER).status_code == 200

    def test_a2_required_keys_present(self):
        body = self._body()
        for k in (
            "tenant_id", "generated_at", "total_bookings",
            "state_distribution", "by_provider",
            "transition_counts", "amendment_rate_pct", "cancellation_rate_pct",
        ):
            assert k in body

    def test_a3_tenant_id_present(self):
        body = self._body()
        assert body["tenant_id"] == "dev-tenant"

    def test_a4_generated_at_is_iso(self):
        body = self._body()
        assert "T" in body["generated_at"]

    def test_a5_by_provider_is_list(self):
        assert isinstance(self._body()["by_provider"], list)

    def test_a6_state_distribution_is_dict(self):
        assert isinstance(self._body()["state_distribution"], dict)

    def test_a7_transition_counts_is_dict(self):
        assert isinstance(self._body()["transition_counts"], dict)


# ---------------------------------------------------------------------------
# Group B — Empty tenant
# ---------------------------------------------------------------------------

class TestGroupBEmpty:
    def _body(self):
        with patch(_PATCH_DB, return_value=_fake_db_empty()):
            return client.get(_URL, headers=_BEARER).json()

    def test_b1_total_bookings_zero(self):
        assert self._body()["total_bookings"] == 0

    def test_b2_state_distribution_empty(self):
        assert self._body()["state_distribution"] == {}

    def test_b3_by_provider_empty(self):
        assert self._body()["by_provider"] == []

    def test_b4_rates_none_when_no_created(self):
        body = self._body()
        assert body["amendment_rate_pct"] is None
        assert body["cancellation_rate_pct"] is None


# ---------------------------------------------------------------------------
# Group C — State distribution
# ---------------------------------------------------------------------------

class TestGroupCStateDistribution:
    def _body(self):
        with patch(_PATCH_DB, return_value=_fake_db_bookings(_make_bookings(), _make_events())):
            return client.get(_URL, headers=_BEARER).json()

    def test_c1_total_bookings_correct(self):
        assert self._body()["total_bookings"] == 5

    def test_c2_active_count(self):
        assert self._body()["state_distribution"]["active"] == 3

    def test_c3_canceled_count(self):
        assert self._body()["state_distribution"]["canceled"] == 2


# ---------------------------------------------------------------------------
# Group D — By-provider breakdown
# ---------------------------------------------------------------------------

class TestGroupDByProvider:
    def _body(self):
        with patch(_PATCH_DB, return_value=_fake_db_bookings(_make_bookings())):
            return client.get(_URL, headers=_BEARER).json()

    def test_d1_two_providers(self):
        assert len(self._body()["by_provider"]) == 2

    def test_d2_airbnb_has_3_total(self):
        entry = next(e for e in self._body()["by_provider"] if e["provider"] == "airbnb")
        assert entry["total"] == 3

    def test_d3_airbnb_active_canceled(self):
        entry = next(e for e in self._body()["by_provider"] if e["provider"] == "airbnb")
        assert entry["active"] == 2
        assert entry["canceled"] == 1

    def test_d4_pct_fields_present(self):
        entry = self._body()["by_provider"][0]
        assert "active_pct" in entry
        assert "canceled_pct" in entry

    def test_d5_sorted_worst_first(self):
        body = self._body()
        totals = [e["total"] for e in body["by_provider"]]
        assert totals == sorted(totals, reverse=True)

    def test_d6_provider_entry_has_all_keys(self):
        entry = self._body()["by_provider"][0]
        for k in ("provider", "total", "active", "canceled", "active_pct", "canceled_pct"):
            assert k in entry


# ---------------------------------------------------------------------------
# Group E — Transition counts
# ---------------------------------------------------------------------------

class TestGroupETransitions:
    def _body(self):
        with patch(_PATCH_DB, return_value=_fake_db_bookings(_make_bookings(), _make_events())):
            return client.get(_URL, headers=_BEARER).json()

    def test_e1_created_count(self):
        assert self._body()["transition_counts"]["BOOKING_CREATED"] == 3

    def test_e2_amended_count(self):
        assert self._body()["transition_counts"]["BOOKING_AMENDED"] == 1

    def test_e3_canceled_count(self):
        assert self._body()["transition_counts"]["BOOKING_CANCELED"] == 1


# ---------------------------------------------------------------------------
# Group F — Rate calculations
# ---------------------------------------------------------------------------

class TestGroupFRates:
    def _body(self):
        with patch(_PATCH_DB, return_value=_fake_db_bookings(_make_bookings(), _make_events())):
            return client.get(_URL, headers=_BEARER).json()

    def test_f1_amendment_rate(self):
        body = self._body()
        # 1 amended / 3 created = 33.3%
        assert body["amendment_rate_pct"] == pytest.approx(33.3, abs=0.1)

    def test_f2_cancellation_rate(self):
        body = self._body()
        # 1 canceled / 3 created = 33.3%
        assert body["cancellation_rate_pct"] == pytest.approx(33.3, abs=0.1)

    def test_f3_rate_none_when_zero_created(self):
        from api.booking_lifecycle_router import _rate_pct
        assert _rate_pct(5, 0) is None

    def test_f4_rate_100_when_equal(self):
        from api.booking_lifecycle_router import _rate_pct
        assert _rate_pct(3, 3) == 100.0


# ---------------------------------------------------------------------------
# Group G — Edge cases (pure helpers)
# ---------------------------------------------------------------------------

class TestGroupGEdgeCases:
    def test_g1_unknown_status_captured(self):
        from api.booking_lifecycle_router import _state_distribution
        bookings = [{"status": None}]
        dist = _state_distribution(bookings)
        assert "unknown" in dist

    def test_g2_missing_source_grouped_as_unknown(self):
        from api.booking_lifecycle_router import _by_provider
        bookings = [{"source": None, "status": "active"}]
        result = _by_provider(bookings)
        assert result[0]["provider"] == "unknown"

    def test_g3_pct_rounded_to_1dp(self):
        from api.booking_lifecycle_router import _rate_pct
        assert _rate_pct(1, 3) == 33.3


# ---------------------------------------------------------------------------
# Group H — Auth + route registration
# ---------------------------------------------------------------------------

class TestGroupHAuth:
    def test_h1_route_registered(self):
        routes = [r.path for r in app.routes]
        assert _URL in routes

    def test_h2_returns_200_with_valid_bearer(self):
        with patch(_PATCH_DB, return_value=_fake_db_empty()):
            resp = client.get(_URL, headers=_BEARER)
        assert resp.status_code == 200
