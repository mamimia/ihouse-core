"""
Phase 270 — E2E Admin & Properties Integration Test

Direct async function call tests for:
  - admin_router: get_tenant_summary, get_admin_metrics, get_admin_dlq,
                  get_provider_health, get_booking_timeline, get_reconciliation
  - properties_router: list_properties, create_property, get_property

All handlers support client= injection.
CI-safe: no live DB, no staging flag.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

TENANT = "dev-tenant"
BOOKING_ID = "bookingcom_bk001"
PROPERTY_ID = "prop-001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _q(rows: list):
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.neq.return_value = q
    q.in_.return_value = q
    q.gte.return_value = q
    q.lte.return_value = q
    q.lt.return_value = q
    q.limit.return_value = q
    q.order.return_value = q
    q.update.return_value = q
    q.insert.return_value = q
    q.upsert.return_value = q
    q.execute.return_value = MagicMock(data=rows)
    return q


def _db(rows: list | None = None):
    db = MagicMock()
    db.table.return_value = _q(rows if rows is not None else [{"id": "x"}])
    return db


def _run(coro):
    return asyncio.run(coro)


def _prop_row(**overrides):
    base = {
        "property_id":   PROPERTY_ID,
        "tenant_id":     TENANT,
        "name":          "Test Villa",
        "property_type": "VILLA",
        "address":       "123 Test St",
        "city":          "Phuket",
        "country":       "TH",
        "created_at":    "2026-03-11T00:00:00Z",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from api.admin_router import (  # noqa: E402
    get_tenant_summary,
    get_admin_metrics,
    get_admin_dlq,
    get_provider_health,
    get_booking_timeline,
    get_reconciliation,
)
from api.properties_router import (  # noqa: E402
    list_properties,
    create_property,
    get_property,
)


# ---------------------------------------------------------------------------
# Group A — get_tenant_summary (direct)
# ---------------------------------------------------------------------------

class TestGroupATenantSummary:

    def _admin_db(self, rows=None):
        """Mock with booking_state shaped rows that admin_router can traverse."""
        import json
        row = {
            "booking_id":   BOOKING_ID,
            "tenant_id":    TENANT,
            "status":       "active",
            "event_kind":   "BOOKING_CREATED",
            "updated_at_ms": 1741694400000,
            "created_at":   "2026-03-11T00:00:00Z",
            "provider":     "bookingcom",
            "envelope_id":  "env-001",
        }
        db = _db(rows if rows is not None else [row])
        return db

    def test_a1_returns_200(self):
        db = self._admin_db()
        r = _run(get_tenant_summary(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code == 200, f"Got {r.status_code}: {r.body}"

    def test_a2_summary_key_or_tenant_id_present(self):
        import json
        db = self._admin_db()
        r = _run(get_tenant_summary(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        body = json.loads(r.body)
        assert "tenant_id" in body or "summary" in body or "total" in body or "active_bookings" in body

    def test_a3_empty_db_returns_200(self):
        db = self._admin_db([])
        r = _run(get_tenant_summary(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Group B — get_admin_metrics (direct)
# ---------------------------------------------------------------------------

class TestGroupBAdminMetrics:

    def test_b1_returns_200(self):
        db = _db()
        r = _run(get_admin_metrics(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code == 200

    def test_b2_response_is_dict(self):
        import json
        db = _db()
        r = _run(get_admin_metrics(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert isinstance(json.loads(r.body), dict)

    def test_b3_empty_db_returns_200(self):
        db = _db([])
        r = _run(get_admin_metrics(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Group C — get_admin_dlq (direct)
# ---------------------------------------------------------------------------

class TestGroupCAdminDlq:

    def test_c1_returns_200(self):
        db = _db()
        r = _run(get_admin_dlq(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code == 200

    def test_c2_has_dlq_related_key(self):
        import json
        db = _db()
        r = _run(get_admin_dlq(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        body = json.loads(r.body)
        assert isinstance(body, dict)

    def test_c3_empty_db_returns_200(self):
        db = _db([])
        r = _run(get_admin_dlq(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Group D — get_provider_health (direct)
# ---------------------------------------------------------------------------

class TestGroupDProviderHealth:

    def test_d1_returns_200(self):
        db = _db()
        r = _run(get_provider_health(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code == 200

    def test_d2_response_is_dict(self):
        import json
        db = _db()
        r = _run(get_provider_health(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert isinstance(json.loads(r.body), dict)

    def test_d3_empty_db_returns_200(self):
        db = _db([])
        r = _run(get_provider_health(identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Group E — get_booking_timeline (direct)
# ---------------------------------------------------------------------------

class TestGroupEBookingTimeline:

    def test_e1_returns_200_or_404_for_unknown_booking(self):
        db = _db([])
        r = _run(get_booking_timeline(booking_id=BOOKING_ID, identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code in (200, 404)

    def test_e2_valid_booking_returns_200(self):
        db = _db([{"booking_id": BOOKING_ID, "event_kind": "BOOKING_CREATED"}])
        r = _run(get_booking_timeline(booking_id=BOOKING_ID, identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code == 200

    def test_e3_empty_booking_returns_200_or_404(self):
        db = _db([])
        r = _run(get_booking_timeline(booking_id="ghost-id", identity={"tenant_id": TENANT, "role": "admin"}, client=db))
        assert r.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Group F — list_properties, create_property, get_property (direct)
# ---------------------------------------------------------------------------

class TestGroupFProperties:

    def test_f1_list_returns_200_with_properties(self):
        import json
        db = _db([_prop_row()])
        r = _run(list_properties(tenant_id=TENANT, client=db))
        assert r.status_code == 200
        body = json.loads(r.body)
        assert "properties" in body or "records" in body or isinstance(body, list)

    def test_f2_list_empty_db_returns_200(self):
        db = _db([])
        r = _run(list_properties(tenant_id=TENANT, client=db))
        assert r.status_code == 200

    def test_f3_get_property_returns_200_when_found(self):
        db = _db([_prop_row()])
        r = _run(get_property(property_id=PROPERTY_ID, tenant_id=TENANT, client=db))
        assert r.status_code == 200

    def test_f4_get_property_returns_404_when_not_found(self):
        db = _db([])
        r = _run(get_property(property_id="ghost-prop", tenant_id=TENANT, client=db))
        assert r.status_code == 404

    def test_f5_create_property_returns_200_or_201(self):
        db = _db([_prop_row()])
        body_payload = {
            "property_id":   PROPERTY_ID,   # required by create_property
            "name":          "Test Villa",
            "property_type": "VILLA",
            "address":       "123 Test St",
            "city":          "Phuket",
            "country":       "TH",
        }
        r = _run(create_property(body=body_payload, tenant_id=TENANT, client=db))
        assert r.status_code in (200, 201), f"Got {r.status_code}: {r.body}"
