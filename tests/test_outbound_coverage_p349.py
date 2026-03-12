"""
Phase 349 — Outbound Sync Coverage Expansion
=============================================

Tests for previously-untested outbound modules:
  - booking_dates.py (fetch_booking_dates)
  - bookingcom_content.py (build_content_payload, push_property_content)
  - Registry expansion + iCal push adapter edge cases

Groups:
  A — Booking Dates (6 tests)
  B — Content Payload Builder (8 tests)
  C — Content Push End-to-End (6 tests)
  D — Registry + iCal Push Edge Cases (6 tests)
  E — Adapter Base Class + Helpers (5 tests)
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch
from datetime import date

os.environ.setdefault("IHOUSE_ENV", "test")
os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("IHOUSE_THROTTLE_DISABLED", "true")
os.environ.setdefault("IHOUSE_RETRY_DISABLED", "true")

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from adapters.outbound.booking_dates import fetch_booking_dates  # noqa: E402
from adapters.outbound.bookingcom_content import (  # noqa: E402
    build_content_payload,
    list_pushed_fields,
    push_property_content,
    PushResult,
)
from adapters.outbound.registry import build_adapter_registry, get_adapter  # noqa: E402
from adapters.outbound import (  # noqa: E402
    AdapterResult,
    OutboundAdapter,
    _build_idempotency_key,
    _throttle,
    _retry_with_backoff,
)


TENANT = "test-tenant"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _query_chain(rows: list | None = None):
    q = MagicMock()
    for m in ("select", "eq", "limit", "order", "insert", "update"):
        setattr(q, m, MagicMock(return_value=q))
    q.execute.return_value = MagicMock(data=rows if rows is not None else [])
    return q


def _property_meta(**overrides) -> dict:
    base = {
        "property_id": "prop-001",
        "bcom_hotel_id": "H-12345",
        "external_id": "EXT-001",
        "name": "Domaniqo Beach Villa",
        "description": "A stunning beachfront villa in Phuket.",
        "address": "123 Beach Road, Rawai",
        "city": "Phuket",
        "country_code": "TH",
        "star_rating": 4,
        "amenities": [1, 5, 7, 28, 47],
        "photos": ["https://example.com/villa1.jpg", "https://example.com/villa2.jpg"],
        "check_in_time": "14:00",
        "check_out_time": "11:00",
        "cancellation_policy_code": "FLEX",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Group A — Booking Dates
# ---------------------------------------------------------------------------

class TestGroupABookingDates:
    """Tests for fetch_booking_dates from booking_state table."""

    def test_a1_returns_ical_format_dates(self):
        """fetch_booking_dates returns (YYYYMMDD, YYYYMMDD) tuple."""
        db = MagicMock()
        db.table.return_value = _query_chain([
            {"check_in": "2026-06-01", "check_out": "2026-06-05"}
        ])
        result = fetch_booking_dates("bk-001", TENANT, client=db)
        assert result == ("20260601", "20260605")

    def test_a2_missing_booking_returns_none_tuple(self):
        """No booking_state row → (None, None)."""
        db = MagicMock()
        db.table.return_value = _query_chain([])
        result = fetch_booking_dates("bk-missing", TENANT, client=db)
        assert result == (None, None)

    def test_a3_db_error_returns_none_tuple(self):
        """DB exception → (None, None), never raises."""
        db = MagicMock()
        db.table.side_effect = RuntimeError("DB down")
        result = fetch_booking_dates("bk-001", TENANT, client=db)
        assert result == (None, None)

    def test_a4_null_dates_return_none(self):
        """Row with null check_in/check_out → (None, None)."""
        db = MagicMock()
        db.table.return_value = _query_chain([
            {"check_in": None, "check_out": None}
        ])
        result = fetch_booking_dates("bk-002", TENANT, client=db)
        assert result == (None, None)

    def test_a5_tenant_isolation(self):
        """Query filters by tenant_id."""
        db = MagicMock()
        chain = _query_chain([{"check_in": "2026-07-01", "check_out": "2026-07-10"}])
        db.table.return_value = chain
        fetch_booking_dates("bk-003", "tenant-X", client=db)
        # Verify eq was called with tenant_id
        calls = [str(c) for c in chain.eq.call_args_list]
        assert any("tenant-X" in c for c in calls)

    def test_a6_iso_to_ical_format_strips_hyphens(self):
        """Correctly strips hyphens from ISO 8601 dates."""
        db = MagicMock()
        db.table.return_value = _query_chain([
            {"check_in": "2026-12-25", "check_out": "2027-01-02"}
        ])
        ci, co = fetch_booking_dates("bk-xmas", TENANT, client=db)
        assert ci == "20261225"
        assert co == "20270102"


# ---------------------------------------------------------------------------
# Group B — Content Payload Builder
# ---------------------------------------------------------------------------

class TestGroupBContentPayload:
    """Tests for build_content_payload (pure function)."""

    def test_b1_builds_valid_payload(self):
        """Minimal valid property_meta → complete payload dict."""
        payload = build_content_payload(_property_meta())
        assert payload["hotel_id"] == "H-12345"
        assert payload["name"] == "Domaniqo Beach Villa"
        assert payload["country_code"] == "TH"
        assert payload["cancellation_policy_code"] == "FLEX"

    def test_b2_includes_optional_fields(self):
        """star_rating, amenities, photos, check_in/out included when present."""
        payload = build_content_payload(_property_meta())
        assert payload["star_rating"] == 4
        assert payload["amenities"] == [1, 5, 7, 28, 47]
        assert len(payload["photos"]) == 2
        assert payload["check_in_time"] == "14:00"

    def test_b3_missing_hotel_id_raises(self):
        """Missing bcom_hotel_id AND external_id → ValueError."""
        with pytest.raises(ValueError, match="bcom_hotel_id or external_id"):
            build_content_payload(
                _property_meta(bcom_hotel_id=None, external_id=None)
            )

    def test_b4_missing_name_raises(self):
        """Missing name → ValueError."""
        with pytest.raises(ValueError, match="name"):
            build_content_payload(_property_meta(name=None))

    def test_b5_missing_address_raises(self):
        """Missing address → ValueError."""
        with pytest.raises(ValueError, match="address, city, country_code"):
            build_content_payload(_property_meta(address=None))

    def test_b6_invalid_country_code_raises(self):
        """3-char country_code → ValueError."""
        with pytest.raises(ValueError, match="alpha-2"):
            build_content_payload(_property_meta(country_code="THA"))

    def test_b7_description_truncated(self):
        """Description > 2000 chars gets truncated."""
        long_desc = "A" * 3000
        payload = build_content_payload(_property_meta(description=long_desc))
        assert len(payload["description"]) == 2000

    def test_b8_invalid_cancellation_code_raises(self):
        """Unknown cancellation code → ValueError."""
        with pytest.raises(ValueError, match="cancellation_policy_code"):
            build_content_payload(_property_meta(cancellation_policy_code="ULTRA_FLEX"))


# ---------------------------------------------------------------------------
# Group C — Content Push End-to-End
# ---------------------------------------------------------------------------

class TestGroupCContentPush:
    """Tests for push_property_content (dry-run + mock HTTP)."""

    def test_c1_dry_run_returns_success(self):
        """push_property_content dry_run=True → PushResult success, no HTTP."""
        result = push_property_content(_property_meta(), dry_run=True)
        assert isinstance(result, PushResult)
        assert result.success is True
        assert result.dry_run is True
        assert result.status_code is None

    def test_c2_dry_run_lists_fields_pushed(self):
        """Dry-run includes fields_pushed list."""
        result = push_property_content(_property_meta(), dry_run=True)
        assert "hotel_id" in result.fields_pushed
        assert "name" in result.fields_pushed

    def test_c3_validation_error_returns_failure(self):
        """Invalid property_meta → PushResult success=False."""
        result = push_property_content(
            _property_meta(name=None), dry_run=True
        )
        assert result.success is False
        assert result.error is not None
        assert "name" in result.error

    def test_c4_http_200_returns_success(self):
        """Mocked 200 response → success, dry_run=False."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "OK"
        mock_client.put.return_value = mock_resp

        result = push_property_content(
            _property_meta(), dry_run=False, _http_client=mock_client
        )
        assert result.success is True
        assert result.dry_run is False
        assert result.status_code == 200

    def test_c5_http_400_returns_failure(self):
        """Mocked 400 response → success=False."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_client.put.return_value = mock_resp

        result = push_property_content(
            _property_meta(), dry_run=False, _http_client=mock_client
        )
        assert result.success is False
        assert result.status_code == 400

    def test_c6_network_error_returns_failure(self):
        """HTTP exception → PushResult success=False, never raises."""
        mock_client = MagicMock()
        mock_client.put.side_effect = ConnectionError("network down")

        result = push_property_content(
            _property_meta(), dry_run=False, _http_client=mock_client
        )
        assert result.success is False
        assert "network down" in result.error


# ---------------------------------------------------------------------------
# Group D — Registry + iCal Push Edge Cases
# ---------------------------------------------------------------------------

class TestGroupDRegistryIcal:
    """Tests for outbound registry and iCal push adapter."""

    def test_d1_registry_has_7_providers(self):
        """build_adapter_registry returns 7 adapters."""
        reg = build_adapter_registry()
        assert len(reg) == 7
        for name in ("airbnb", "bookingcom", "expedia", "vrbo",
                      "hotelbeds", "tripadvisor", "despegar"):
            assert name in reg

    def test_d2_get_adapter_returns_none_for_unknown(self):
        """get_adapter('unknown') → None (not ValueError like inbound registry)."""
        result = get_adapter("unknown_provider")
        assert result is None

    def test_d3_ical_push_dry_run(self):
        """ICalPushAdapter.push() returns dry_run when no iCal URL."""
        adapter = get_adapter("hotelbeds")
        result = adapter.push("ext-001", "bk-001", rate_limit=60, dry_run=True)
        assert isinstance(result, AdapterResult)
        assert result.status == "dry_run"
        assert result.provider == "hotelbeds"

    def test_d4_expedia_vrbo_share_adapter(self):
        """Expedia and VRBO use ExpediaVrboAdapter with different provider names."""
        reg = build_adapter_registry()
        assert type(reg["expedia"]) is type(reg["vrbo"])
        assert reg["expedia"].provider == "expedia"
        assert reg["vrbo"].provider == "vrbo"

    def test_d5_airbnb_send_dry_run(self):
        """AirbnbAdapter.send() returns dry_run when no API key."""
        adapter = get_adapter("airbnb")
        result = adapter.send("ext-001", "bk-001", rate_limit=60, dry_run=True)
        assert result.status == "dry_run"
        assert result.provider == "airbnb"

    def test_d6_bookingcom_send_dry_run(self):
        """BookingComAdapter.send() returns dry_run when no API key."""
        adapter = get_adapter("bookingcom")
        result = adapter.send("ext-001", "bk-001", rate_limit=60, dry_run=True)
        assert result.status == "dry_run"
        assert result.provider == "bookingcom"


# ---------------------------------------------------------------------------
# Group E — Adapter Base Class + Helpers
# ---------------------------------------------------------------------------

class TestGroupEBaseHelpers:
    """Tests for base class helpers: idempotency key, throttle, retry."""

    def test_e1_idempotency_key_format(self):
        """Key format: {booking_id}:{external_id}:{YYYYMMDD}."""
        key = _build_idempotency_key("bk-001", "ext-001")
        parts = key.split(":")
        assert len(parts) == 3
        assert parts[0] == "bk-001"
        assert parts[1] == "ext-001"
        assert len(parts[2]) == 8  # YYYYMMDD

    def test_e2_idempotency_key_with_suffix(self):
        """Key with suffix: {booking_id}:{external_id}:{YYYYMMDD}:{suffix}."""
        key = _build_idempotency_key("bk-001", "ext-001", suffix="cancel")
        assert key.endswith(":cancel")
        parts = key.split(":")
        assert len(parts) == 4

    def test_e3_idempotency_key_day_stable(self):
        """Two calls in same UTC day produce the same key."""
        k1 = _build_idempotency_key("bk-X", "ext-Y")
        k2 = _build_idempotency_key("bk-X", "ext-Y")
        assert k1 == k2

    def test_e4_throttle_disabled_in_test(self):
        """_throttle does not block when IHOUSE_THROTTLE_DISABLED=true."""
        import time
        start = time.monotonic()
        _throttle(60)
        elapsed = time.monotonic() - start
        assert elapsed < 0.5  # Should return immediately

    def test_e5_adapter_result_shape(self):
        """AdapterResult has all required fields."""
        r = AdapterResult(
            provider="test", external_id="ext-1",
            strategy="api_first", status="dry_run",
            http_status=None, message="test"
        )
        assert r.provider == "test"
        assert r.status == "dry_run"
        assert r.http_status is None
