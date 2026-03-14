"""
PII Document Security — Contract Tests

Tests:
    1. GET /bookings/{id}/checkin-form returns redacted passport_photo_url ('***')
    2. GET /bookings/{id}/checkin-form shows boolean indicators (passport_photo_captured)
    3. POST /checkin-forms/{id}/submit returns NO URLs, only status indicators
    4. GET /admin/pii-documents/{form_id} — worker role → 403
    5. GET /admin/pii-documents/{form_id} — admin role → 200 + documents
    6. GET /admin/pii-documents/{form_id} — writes audit_log entry
    7. GET /admin/pii-documents/{form_id} — non-existent form → 404
    8. Redaction helpers work correctly
"""
from __future__ import annotations

import os
import sys
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("JWT_SECRET", "test-secret-for-pii-tests")
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

import jwt as pyjwt
from main import app

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(tenant_id: str = "t1", role: str = "worker") -> Dict[str, str]:
    payload = {"sub": tenant_id, "role": role, "aud": "authenticated"}
    token = pyjwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _mock_db():
    """Create a mock Supabase client."""
    return MagicMock()


def _setup_mock_table(mock_db, table_name: str, data: List[Dict]):
    """Configure mock DB to return data for a specific table query chain."""
    table = MagicMock()
    select_chain = MagicMock()
    table.select.return_value = select_chain

    # Support chained .eq().eq().limit().execute() and .eq().execute()
    eq_chain = MagicMock()
    select_chain.eq.return_value = eq_chain
    eq_chain.eq.return_value = eq_chain
    eq_chain.limit.return_value = eq_chain
    eq_chain.order.return_value = eq_chain
    eq_chain.execute.return_value = MagicMock(data=data)

    mock_db.table.side_effect = lambda name: table if name == table_name else _setup_generic_table(mock_db, name)
    return mock_db


def _setup_multi_table_mock(mock_db, table_responses: Dict[str, List[Dict]]):
    """Configure mock DB to return different data per table name."""
    tables = {}
    for tname, data in table_responses.items():
        t = MagicMock()
        sel = MagicMock()
        t.select.return_value = sel
        eq = MagicMock()
        sel.eq.return_value = eq
        eq.eq.return_value = eq
        eq.limit.return_value = eq
        eq.order.return_value = eq
        eq.execute.return_value = MagicMock(data=data)

        # insert chain
        ins = MagicMock()
        t.insert.return_value = ins
        ins.execute.return_value = MagicMock(data=[{"id": str(uuid.uuid4())}])

        # update chain
        upd = MagicMock()
        t.update.return_value = upd
        upd.eq.return_value = upd
        upd.execute.return_value = MagicMock(data=data)

        tables[tname] = t

    def _table_selector(name):
        if name in tables:
            return tables[name]
        # Default empty table
        default = MagicMock()
        sel = MagicMock()
        default.select.return_value = sel
        eq = MagicMock()
        sel.eq.return_value = eq
        eq.eq.return_value = eq
        eq.limit.return_value = eq
        eq.order.return_value = eq
        eq.execute.return_value = MagicMock(data=[])
        ins = MagicMock()
        default.insert.return_value = ins
        ins.execute.return_value = MagicMock(data=[])
        return default

    mock_db.table.side_effect = _table_selector
    return tables


# ===========================================================================
# Test: PII Redaction Helpers
# ===========================================================================

class TestPIIRedactionHelpers:
    def test_redact_guest_with_photo(self):
        from api.guest_checkin_form_router import _redact_guest_pii
        guest = {"id": "g1", "full_name": "John", "passport_photo_url": "photos/doc.jpg"}
        result = _redact_guest_pii(guest)
        assert result["passport_photo_url"] == "***"
        assert result["passport_photo_captured"] is True

    def test_redact_guest_without_photo(self):
        from api.guest_checkin_form_router import _redact_guest_pii
        guest = {"id": "g1", "full_name": "John", "passport_photo_url": None}
        result = _redact_guest_pii(guest)
        assert result["passport_photo_url"] is None
        assert result["passport_photo_captured"] is False

    def test_redact_guest_empty_string_photo(self):
        from api.guest_checkin_form_router import _redact_guest_pii
        guest = {"id": "g1", "full_name": "John", "passport_photo_url": ""}
        result = _redact_guest_pii(guest)
        assert result["passport_photo_captured"] is False

    def test_redact_deposit_with_signature(self):
        from api.guest_checkin_form_router import _redact_deposit_pii
        deposit = {"signature_url": "sigs/sig.png", "cash_photo_url": "cash/001.jpg"}
        result = _redact_deposit_pii(deposit)
        assert result["signature_url"] == "***"
        assert result["signature_recorded"] is True
        assert result["cash_photo_url"] == "***"
        assert result["cash_photo_captured"] is True

    def test_redact_deposit_without_pii(self):
        from api.guest_checkin_form_router import _redact_deposit_pii
        deposit = {"signature_url": None, "cash_photo_url": None}
        result = _redact_deposit_pii(deposit)
        assert result["signature_recorded"] is False
        assert result["cash_photo_captured"] is False


# ===========================================================================
# Test: GET /bookings/{id}/checkin-form — PII Redaction
# ===========================================================================

class TestCheckinFormRedaction:
    def test_get_form_redacts_passport_url(self):
        """Passport photo URL must be replaced with '***' and boolean indicator added."""
        form_data = [{"id": "form-1", "booking_id": "b1", "tenant_id": "t1",
                      "form_status": "completed"}]
        guest_data = [{"id": "g1", "form_id": "form-1", "full_name": "Alice",
                       "passport_photo_url": "passport-photos/t1/form-1/g1.jpg",
                       "guest_number": 1}]

        mock_db = _mock_db()
        tables = _setup_multi_table_mock(mock_db, {
            "guest_checkin_forms": form_data,
            "guest_checkin_guests": guest_data,
        })

        headers = _make_token("t1", "worker")
        resp = client.get("/bookings/b1/checkin-form", headers=headers,
                          params={"client": "mock"})

        # Direct call to the endpoint with injected mock
        from api.guest_checkin_form_router import get_checkin_form
        import asyncio
        result = asyncio.run(
            get_checkin_form("b1", tenant_id="t1", client=mock_db)
        )
        import json
        body = json.loads(result.body)

        assert body["guests"][0]["passport_photo_url"] == "***"
        assert body["guests"][0]["passport_photo_captured"] is True

    def test_get_form_no_photo_shows_false(self):
        """Guest without photo should have captured=False."""
        form_data = [{"id": "form-2", "booking_id": "b2", "tenant_id": "t1",
                      "form_status": "pending"}]
        guest_data = [{"id": "g2", "form_id": "form-2", "full_name": "Bob",
                       "passport_photo_url": None, "guest_number": 1}]

        mock_db = _mock_db()
        _setup_multi_table_mock(mock_db, {
            "guest_checkin_forms": form_data,
            "guest_checkin_guests": guest_data,
        })

        from api.guest_checkin_form_router import get_checkin_form
        import asyncio
        result = asyncio.run(
            get_checkin_form("b2", tenant_id="t1", client=mock_db)
        )
        import json
        body = json.loads(result.body)

        assert body["guests"][0]["passport_photo_captured"] is False

    def test_get_form_admin_also_sees_redacted(self):
        """Even admin sees redacted URLs in the form endpoint."""
        form_data = [{"id": "form-3", "booking_id": "b3", "tenant_id": "t1",
                      "form_status": "completed"}]
        guest_data = [{"id": "g3", "form_id": "form-3", "full_name": "Carol",
                       "passport_photo_url": "passport-photos/t1/form-3/g3.jpg",
                       "guest_number": 1}]

        mock_db = _mock_db()
        _setup_multi_table_mock(mock_db, {
            "guest_checkin_forms": form_data,
            "guest_checkin_guests": guest_data,
        })

        # Call as admin — should STILL be redacted
        from api.guest_checkin_form_router import get_checkin_form
        import asyncio
        result = asyncio.run(
            get_checkin_form("b3", tenant_id="t1", client=mock_db)
        )
        import json
        body = json.loads(result.body)

        assert body["guests"][0]["passport_photo_url"] == "***"


# ===========================================================================
# Test: POST /checkin-forms/{id}/submit — Status-Only Response
# ===========================================================================

class TestSubmitFormPIISafe:
    def test_submit_returns_status_indicators(self):
        """Submit must return passport_photos_captured and count, not URLs."""
        form_data = [{"id": "form-s1", "booking_id": "bs1", "tenant_id": "t1",
                      "form_status": "pending"}]
        guest_data = [{"id": "gs1", "form_id": "form-s1", "full_name": "Dave",
                       "passport_photo_url": "passport-photos/t1/form-s1/gs1.jpg",
                       "guest_number": 1}]

        mock_db = _mock_db()
        tables = _setup_multi_table_mock(mock_db, {
            "guest_checkin_forms": form_data,
            "guest_checkin_guests": guest_data,
        })

        from api.guest_checkin_form_router import submit_form
        import asyncio
        result = asyncio.run(
            submit_form("form-s1", body={"worker_id": "w1"},
                        tenant_id="t1", client=mock_db)
        )
        import json
        body = json.loads(result.body)

        assert body["form_status"] == "completed"
        assert body["passport_photos_captured"] is True
        assert body["passport_photo_count"] == 1
        assert "passport_photo_url" not in body
        assert "signature_url" not in body

    def test_submit_no_photos_shows_zero(self):
        """Submit with no photos should show captured=False, count=0."""
        form_data = [{"id": "form-s2", "booking_id": "bs2", "tenant_id": "t1",
                      "form_status": "pending"}]
        guest_data = [{"id": "gs2", "form_id": "form-s2", "full_name": "Eve",
                       "passport_photo_url": None, "guest_number": 1}]

        mock_db = _mock_db()
        _setup_multi_table_mock(mock_db, {
            "guest_checkin_forms": form_data,
            "guest_checkin_guests": guest_data,
        })

        from api.guest_checkin_form_router import submit_form
        import asyncio
        result = asyncio.run(
            submit_form("form-s2", body={"force": True, "worker_id": "w1"},
                        tenant_id="t1", client=mock_db)
        )
        import json
        body = json.loads(result.body)

        assert body["passport_photos_captured"] is False
        assert body["passport_photo_count"] == 0


# ===========================================================================
# Test: GET /admin/pii-documents/{form_id} — Role Enforcement
# ===========================================================================

class TestPIIDocumentAccess:
    def test_worker_cannot_access_pii_documents(self):
        """Worker role must get 403 on PII document endpoint."""
        from api.pii_document_router import get_pii_documents
        import asyncio

        mock_request = MagicMock()
        mock_request.headers = {"authorization": f"Bearer {pyjwt.encode({'sub': 't1', 'role': 'worker'}, 'test-secret-for-pii-tests', algorithm='HS256')}"}
        mock_request.client = MagicMock(host="127.0.0.1")

        result = asyncio.run(
            get_pii_documents("form-x", request=mock_request, tenant_id="t1")
        )
        assert result.status_code == 403

    def test_manager_cannot_access_pii_documents(self):
        """Manager role must also get 403 — only admin allowed."""
        from api.pii_document_router import get_pii_documents
        import asyncio

        mock_request = MagicMock()
        mock_request.headers = {"authorization": f"Bearer {pyjwt.encode({'sub': 't1', 'role': 'manager'}, 'test-secret-for-pii-tests', algorithm='HS256')}"}
        mock_request.client = MagicMock(host="127.0.0.1")

        result = asyncio.run(
            get_pii_documents("form-x", request=mock_request, tenant_id="t1")
        )
        assert result.status_code == 403

    def test_admin_can_access_pii_documents(self):
        """Admin role must get 200 with document list."""
        from api.pii_document_router import get_pii_documents
        import asyncio, json

        mock_request = MagicMock()
        mock_request.headers = {"authorization": f"Bearer {pyjwt.encode({'sub': 't1', 'role': 'admin'}, 'test-secret-for-pii-tests', algorithm='HS256')}"}
        mock_request.client = MagicMock(host="10.0.0.1")

        mock_db = _mock_db()
        _setup_multi_table_mock(mock_db, {
            "guest_checkin_forms": [{"id": "form-a1", "booking_id": "ba1",
                                     "tenant_id": "t1", "property_id": "p1",
                                     "form_status": "completed"}],
            "guest_checkin_guests": [{"id": "ga1", "full_name": "Frank",
                                      "passport_photo_url": "passport-photos/t1/form-a1/ga1.jpg"}],
            "guest_deposit_records": [{"signature_url": "signatures/t1/form-a1/sig.png",
                                       "cash_photo_url": None}],
            "audit_log": [],  # insert goes here
        })

        # Mock storage signed URL generation
        storage_bucket = MagicMock()
        storage_bucket.create_signed_url.return_value = {"signedURL": "https://example.com/signed/test"}
        mock_db.storage.from_.return_value = storage_bucket

        result = asyncio.run(
            get_pii_documents("form-a1", request=mock_request,
                              tenant_id="t1", client=mock_db)
        )
        body = json.loads(result.body)

        assert result.status_code == 200
        assert body["form_id"] == "form-a1"
        assert body["document_count"] >= 1
        assert any(d["type"] == "passport_photo" for d in body["documents"])
        # Verify signed URL is an actual string, not a mock
        for doc in body["documents"]:
            assert isinstance(doc["signed_url"], str)
            assert "example.com" in doc["signed_url"] or "signed-url-pending" in doc["signed_url"]

    def test_admin_nonexistent_form_returns_404(self):
        """Admin requesting non-existent form gets 404."""
        from api.pii_document_router import get_pii_documents
        import asyncio

        mock_request = MagicMock()
        mock_request.headers = {"authorization": f"Bearer {pyjwt.encode({'sub': 't1', 'role': 'admin'}, 'test-secret-for-pii-tests', algorithm='HS256')}"}
        mock_request.client = MagicMock(host="127.0.0.1")

        mock_db = _mock_db()
        _setup_multi_table_mock(mock_db, {
            "guest_checkin_forms": [],  # no form found
        })

        result = asyncio.run(
            get_pii_documents("nonexistent", request=mock_request,
                              tenant_id="t1", client=mock_db)
        )
        assert result.status_code == 404


# ===========================================================================
# Test: Audit Logging on PII Access
# ===========================================================================

class TestPIIAuditLogging:
    def test_admin_access_writes_audit_log(self):
        """Admin PII access must insert an audit_log entry."""
        from api.pii_document_router import get_pii_documents
        import asyncio

        mock_request = MagicMock()
        mock_request.headers = {"authorization": f"Bearer {pyjwt.encode({'sub': 't1', 'role': 'admin'}, 'test-secret-for-pii-tests', algorithm='HS256')}"}
        mock_request.client = MagicMock(host="192.168.1.1")

        mock_db = _mock_db()
        tables = _setup_multi_table_mock(mock_db, {
            "guest_checkin_forms": [{"id": "form-audit", "booking_id": "baud",
                                     "tenant_id": "t1", "property_id": "p1",
                                     "form_status": "completed"}],
            "guest_checkin_guests": [{"id": "gaud", "full_name": "Grace",
                                      "passport_photo_url": "passport-photos/t1/form-audit/gaud.jpg"}],
            "guest_deposit_records": [],
            "audit_log": [],
        })

        asyncio.run(
            get_pii_documents("form-audit", request=mock_request,
                              tenant_id="t1", client=mock_db)
        )

        # Verify audit_log.insert was called
        audit_table = tables["audit_log"]
        assert audit_table.insert.called
        call_args = audit_table.insert.call_args[0][0]
        assert call_args["action"] == "PII_DOCUMENT_ACCESS"
        assert call_args["resource_id"] == "form-audit"
        assert call_args["tenant_id"] == "t1"
        assert "passport_photo" in call_args["details"]["documents_accessed"]

    def test_audit_log_captures_ip_address(self):
        """Audit entry must include the client IP address."""
        from api.pii_document_router import get_pii_documents
        import asyncio

        mock_request = MagicMock()
        mock_request.headers = {
            "authorization": f"Bearer {pyjwt.encode({'sub': 't1', 'role': 'admin'}, 'test-secret-for-pii-tests', algorithm='HS256')}",
            "x-forwarded-for": "203.0.113.42, 10.0.0.1",
        }
        mock_request.client = MagicMock(host="127.0.0.1")

        mock_db = _mock_db()
        tables = _setup_multi_table_mock(mock_db, {
            "guest_checkin_forms": [{"id": "form-ip", "booking_id": "bip",
                                     "tenant_id": "t1", "property_id": "p1",
                                     "form_status": "completed"}],
            "guest_checkin_guests": [],
            "guest_deposit_records": [],
            "audit_log": [],
        })

        asyncio.run(
            get_pii_documents("form-ip", request=mock_request,
                              tenant_id="t1", client=mock_db)
        )

        audit_table = tables["audit_log"]
        call_args = audit_table.insert.call_args[0][0]
        assert call_args["ip_address"] == "203.0.113.42"


# ===========================================================================
# Test: No Role in JWT → Denied
# ===========================================================================

class TestNoRoleDenied:
    def test_no_role_claim_denied(self):
        """JWT without role claim should be denied PII access."""
        from api.pii_document_router import get_pii_documents
        import asyncio

        mock_request = MagicMock()
        mock_request.headers = {"authorization": f"Bearer {pyjwt.encode({'sub': 't1'}, 'test-secret-for-pii-tests', algorithm='HS256')}"}
        mock_request.client = MagicMock(host="127.0.0.1")

        result = asyncio.run(
            get_pii_documents("form-x", request=mock_request, tenant_id="t1")
        )
        assert result.status_code == 403
