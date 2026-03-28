"""
Phase 985 — OCR Router Tests
==============================

Tests for /worker/ocr/* and /admin/ocr/* endpoints.

Patch strategy:
  - jwt_auth / jwt_identity are FastAPI dependencies — override via
    app.dependency_overrides, the canonical FastAPI testing approach.
  - process_ocr_request is imported inside the endpoint function body;
    we patch at ocr.fallback module level.
  - _get_supabase_client is patched at the router module level.

Tests cover:
  - Scope guard blocks invalid capture_type before any OCR (HTTP 422)
  - Valid capture types reach the provider chain
  - Missing required fields → HTTP 422
  - OCR failure is non-blocking (still HTTP 200)
  - INV-OCR-02: review_required always True in response
  - Admin role guard on /admin/* endpoints
"""
from __future__ import annotations

import asyncio
import base64
import io
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient


# ─── Shared test helpers ──────────────────────────────────────────

def _make_test_jpeg_b64() -> str:
    """Return a base64-encoded JPEG string."""
    try:
        from PIL import Image
        img = Image.new("RGB", (80, 60), (160, 160, 160))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        return base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 200).decode()


def _make_mock_ocr_success(capture_type: str = "identity_document_capture"):
    from ocr.provider_base import OcrResult, OcrResultStatus
    return OcrResult(
        status=OcrResultStatus.SUCCESS,
        provider_name="local_mrz",
        capture_type=capture_type,
        extracted_fields={"full_name": "JOHN DOE"},
        field_confidences={"full_name": 0.95},
        processing_time_ms=150,
    )


def _make_mock_ocr_failed(capture_type: str = "identity_document_capture"):
    from ocr.provider_base import OcrResult, OcrResultStatus
    return OcrResult(
        status=OcrResultStatus.FAILED,
        provider_name="all_failed",
        capture_type=capture_type,
        error_message="no providers succeeded",
    )


def _make_mock_db(rows=None):
    """Build a MagicMock that looks like a Supabase client for read queries."""
    rows = rows or []
    mock = MagicMock()
    # Chain: .table().select().eq().eq()...execute().data
    chain = mock.table.return_value.select.return_value
    for attr in ("eq", "neq", "order", "limit", "maybe_single"):
        getattr(chain, attr).return_value = chain
    chain.execute.return_value.data = rows
    # Also for insert/update chains
    mock.table.return_value.insert.return_value.execute.return_value = MagicMock()
    mock.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()
    return mock


def _override_jwt_auth(app, tenant_id="test-tenant"):
    """Override jwt_auth dependency with a plain function."""
    from api.auth import jwt_auth
    app.dependency_overrides[jwt_auth] = lambda: tenant_id
    return app


def _override_jwt_identity(app, role="admin", tenant_id="test-tenant", user_id="user-123"):
    """Override jwt_identity dependency."""
    from api.auth import jwt_identity
    identity = {"tenant_id": tenant_id, "user_id": user_id, "role": role, "sub": tenant_id}
    app.dependency_overrides[jwt_identity] = lambda: identity
    return app


_AUTH_HEADER = {"Authorization": "Bearer test-token"}

_PROCESS_VALID_BODY = {
    "capture_type": "identity_document_capture",
    "image_data": _make_test_jpeg_b64(),
    "booking_id": "BK001",
    "document_type": "PASSPORT",
}

_METER_VALID_BODY = {
    "capture_type": "checkin_opening_meter_capture",
    "image_data": _make_test_jpeg_b64(),
    "booking_id": "BK002",
}


# ═══════════════════════════════════════════════════════════════════
# Scope Enforcement Tests
# ═══════════════════════════════════════════════════════════════════

class TestOcrScopeEnforcement:
    """Scope guard must fire BEFORE any provider call."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from main import app
        _override_jwt_auth(app)
        self.client = TestClient(app, raise_server_exceptions=False)
        yield
        app.dependency_overrides.clear()

    def _post_process(self, capture_type: str):
        return self.client.post(
            "/worker/ocr/process",
            json={
                "capture_type": capture_type,
                "image_data": _make_test_jpeg_b64(),
                "booking_id": "BK001",
            },
            headers=_AUTH_HEADER,
        )

    def test_cleaning_photo_blocked(self):
        with patch("ocr.fallback.process_ocr_request") as mock_ocr:
            resp = self._post_process("cleaning_photo")
        assert resp.status_code == 422
        data = resp.json()
        assert "SCOPE_VIOLATION" in str(data)
        # OCR must never have been called
        mock_ocr.assert_not_called()

    def test_property_gallery_blocked(self):
        with patch("ocr.fallback.process_ocr_request") as mock_ocr:
            resp = self._post_process("property_gallery")
        assert resp.status_code == 422
        mock_ocr.assert_not_called()

    def test_atmosphere_media_blocked(self):
        with patch("ocr.fallback.process_ocr_request") as mock_ocr:
            resp = self._post_process("atmosphere_media")
        assert resp.status_code == 422
        mock_ocr.assert_not_called()

    def test_generic_upload_blocked(self):
        with patch("ocr.fallback.process_ocr_request") as mock_ocr:
            resp = self._post_process("generic_upload")
        assert resp.status_code == 422
        mock_ocr.assert_not_called()

    def test_task_image_blocked(self):
        with patch("ocr.fallback.process_ocr_request") as mock_ocr:
            resp = self._post_process("task_image")
        assert resp.status_code == 422
        mock_ocr.assert_not_called()

    def test_empty_capture_type_blocked(self):
        with patch("ocr.fallback.process_ocr_request") as mock_ocr:
            resp = self._post_process("")
        assert resp.status_code == 422
        mock_ocr.assert_not_called()

    def test_identity_document_capture_passes(self):
        """Valid capture type passes scope guard and reaches OCR layer."""
        mock_ocr_result = _make_mock_ocr_success("identity_document_capture")
        with (
            patch("api.ocr_router._get_supabase_client", return_value=_make_mock_db()),
            patch("api.ocr_router._get_tenant_provider_configs", new=AsyncMock(return_value=[])),
            patch("api.ocr_router._save_ocr_result", return_value="res-001"),
            patch("ocr.fallback.process_ocr_request", new=AsyncMock(return_value=mock_ocr_result)),
        ):
            resp = self.client.post(
                "/worker/ocr/process",
                json=_PROCESS_VALID_BODY,
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 200

    def test_checkin_meter_passes(self):
        mock_ocr_result = _make_mock_ocr_success("checkin_opening_meter_capture")
        with (
            patch("api.ocr_router._get_supabase_client", return_value=_make_mock_db()),
            patch("api.ocr_router._get_tenant_provider_configs", new=AsyncMock(return_value=[])),
            patch("api.ocr_router._save_ocr_result", return_value="res-002"),
            patch("ocr.fallback.process_ocr_request", new=AsyncMock(return_value=mock_ocr_result)),
        ):
            resp = self.client.post(
                "/worker/ocr/process",
                json=_METER_VALID_BODY,
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 200

    def test_checkout_meter_passes(self):
        mock_ocr_result = _make_mock_ocr_success("checkout_closing_meter_capture")
        with (
            patch("api.ocr_router._get_supabase_client", return_value=_make_mock_db()),
            patch("api.ocr_router._get_tenant_provider_configs", new=AsyncMock(return_value=[])),
            patch("api.ocr_router._save_ocr_result", return_value="res-003"),
            patch("ocr.fallback.process_ocr_request", new=AsyncMock(return_value=mock_ocr_result)),
        ):
            resp = self.client.post(
                "/worker/ocr/process",
                json={**_METER_VALID_BODY, "capture_type": "checkout_closing_meter_capture"},
                headers=_AUTH_HEADER,
            )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# Validation Tests
# ═══════════════════════════════════════════════════════════════════

class TestProcessValidation:
    """Required field validation for /worker/ocr/process."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from main import app
        _override_jwt_auth(app)
        self.client = TestClient(app, raise_server_exceptions=False)
        yield
        app.dependency_overrides.clear()

    def test_missing_capture_type_rejected(self):
        resp = self.client.post(
            "/worker/ocr/process",
            json={"image_data": _make_test_jpeg_b64(), "booking_id": "BK001"},
            headers=_AUTH_HEADER,
        )
        assert resp.status_code == 422

    def test_missing_image_data_rejected(self):
        resp = self.client.post(
            "/worker/ocr/process",
            json={"capture_type": "identity_document_capture", "booking_id": "BK001"},
            headers=_AUTH_HEADER,
        )
        assert resp.status_code == 422

    def test_missing_booking_id_rejected(self):
        resp = self.client.post(
            "/worker/ocr/process",
            json={
                "capture_type": "identity_document_capture",
                "image_data": _make_test_jpeg_b64(),
            },
            headers=_AUTH_HEADER,
        )
        assert resp.status_code == 422

    def test_invalid_base64_rejected(self):
        resp = self.client.post(
            "/worker/ocr/process",
            json={
                "capture_type": "identity_document_capture",
                "image_data": "!!!not-base64!!!",
                "booking_id": "BK001",
            },
            headers=_AUTH_HEADER,
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# OCR Failure Non-blocking Tests (INV-OCR-04)
# ═══════════════════════════════════════════════════════════════════

class TestOcrNonBlocking:
    """OCR failures must never block the worker (HTTP 200 always)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from main import app
        _override_jwt_auth(app)
        self.client = TestClient(app, raise_server_exceptions=False)
        yield
        app.dependency_overrides.clear()

    def test_provider_failure_returns_200(self):
        """All providers fail → HTTP 200 with status=failed, not 500."""
        failed_result = _make_mock_ocr_failed("identity_document_capture")
        with (
            patch("api.ocr_router._get_supabase_client", return_value=_make_mock_db()),
            patch("api.ocr_router._get_tenant_provider_configs", new=AsyncMock(return_value=[])),
            patch("api.ocr_router._save_ocr_result", return_value="res-fail"),
            patch("ocr.fallback.process_ocr_request", new=AsyncMock(return_value=failed_result)),
        ):
            resp = self.client.post(
                "/worker/ocr/process",
                json=_PROCESS_VALID_BODY,
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "failed"

    def test_review_required_always_true(self):
        """INV-OCR-02: review_required is always True regardless of confidence."""
        success_result = _make_mock_ocr_success("identity_document_capture")
        with (
            patch("api.ocr_router._get_supabase_client", return_value=_make_mock_db()),
            patch("api.ocr_router._get_tenant_provider_configs", new=AsyncMock(return_value=[])),
            patch("api.ocr_router._save_ocr_result", return_value="res-review"),
            patch("ocr.fallback.process_ocr_request", new=AsyncMock(return_value=success_result)),
        ):
            resp = self.client.post(
                "/worker/ocr/process",
                json=_PROCESS_VALID_BODY,
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["review_required"] is True

    def test_db_write_failure_still_returns_ocr_data(self):
        """If DB save fails, OCR data is still returned to the worker."""
        success_result = _make_mock_ocr_success("identity_document_capture")
        with (
            patch("api.ocr_router._get_supabase_client", return_value=_make_mock_db()),
            patch("api.ocr_router._get_tenant_provider_configs", new=AsyncMock(return_value=[])),
            patch("api.ocr_router._save_ocr_result", side_effect=Exception("DB write failed")),
            patch("ocr.fallback.process_ocr_request", new=AsyncMock(return_value=success_result)),
        ):
            resp = self.client.post(
                "/worker/ocr/process",
                json=_PROCESS_VALID_BODY,
                headers=_AUTH_HEADER,
            )

        # Worker still gets OCR data even if DB write failed
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["extracted_fields"]["full_name"] == "JOHN DOE"
        assert data["result_id"] is None  # no ID because save failed


# ═══════════════════════════════════════════════════════════════════
# Response Shape Tests
# ═══════════════════════════════════════════════════════════════════

class TestProcessResponseShape:
    """Verify the /process response contains all expected fields."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from main import app
        _override_jwt_auth(app)
        self.client = TestClient(app, raise_server_exceptions=False)
        yield
        app.dependency_overrides.clear()

    def test_response_shape_complete(self):
        from ocr.provider_base import OcrResult, OcrResultStatus
        result = OcrResult(
            status=OcrResultStatus.SUCCESS,
            provider_name="azure_document_intelligence",
            capture_type="identity_document_capture",
            document_type="PASSPORT",
            extracted_fields={
                "full_name": "JANE DOE",
                "document_number": "AB123456",
                "date_of_birth": "1990-05-20",
            },
            field_confidences={
                "full_name": 0.99,
                "document_number": 0.98,
                "date_of_birth": 0.97,
            },
            image_quality_score=0.92,
            processing_time_ms=540,
        )

        with (
            patch("api.ocr_router._get_supabase_client", return_value=_make_mock_db()),
            patch("api.ocr_router._get_tenant_provider_configs", new=AsyncMock(return_value=[])),
            patch("api.ocr_router._save_ocr_result", return_value="shape-result-id"),
            patch("ocr.fallback.process_ocr_request", new=AsyncMock(return_value=result)),
        ):
            resp = self.client.post(
                "/worker/ocr/process",
                json=_PROCESS_VALID_BODY,
                headers=_AUTH_HEADER,
            )

        assert resp.status_code == 200
        d = resp.json()["data"]

        # Required response fields
        for field in [
            "result_id", "capture_type", "status", "provider_used",
            "extracted_fields", "field_confidences", "overall_confidence",
            "requires_review", "review_required",
        ]:
            assert field in d, f"Missing field: {field}"

        assert d["result_id"] == "shape-result-id"
        assert d["status"] == "success"
        assert d["extracted_fields"]["full_name"] == "JANE DOE"
        assert d["review_required"] is True
        assert isinstance(d["overall_confidence"], float)


# ═══════════════════════════════════════════════════════════════════
# Admin Role Guard Tests
# ═══════════════════════════════════════════════════════════════════

class TestAdminRoleGuard:
    """Admin endpoints must reject non-admin roles."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from main import app
        self.app = app
        yield
        app.dependency_overrides.clear()

    def _client_with_role(self, role: str):
        _override_jwt_identity(self.app, role=role)
        return TestClient(self.app, raise_server_exceptions=False)

    def test_review_queue_rejects_worker(self):
        client = self._client_with_role("worker")
        resp = client.get("/admin/ocr/review-queue", headers=_AUTH_HEADER)
        assert resp.status_code == 403

    def test_provider_config_rejects_worker(self):
        client = self._client_with_role("worker")
        resp = client.get("/admin/ocr/provider-config", headers=_AUTH_HEADER)
        assert resp.status_code == 403

    def test_test_connection_rejects_worker(self):
        client = self._client_with_role("worker")
        resp = client.post(
            "/admin/ocr/test-connection",
            json={"provider_name": "local_mrz"},
            headers=_AUTH_HEADER,
        )
        assert resp.status_code == 403

    def test_review_queue_allows_admin(self):
        mock_db = _make_mock_db(rows=[])
        _override_jwt_identity(self.app, role="admin")
        client = TestClient(self.app, raise_server_exceptions=False)

        with patch("api.ocr_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/admin/ocr/review-queue", headers=_AUTH_HEADER)
        assert resp.status_code == 200

    def test_review_queue_allows_manager(self):
        mock_db = _make_mock_db(rows=[])
        _override_jwt_identity(self.app, role="manager")
        client = TestClient(self.app, raise_server_exceptions=False)

        with patch("api.ocr_router._get_supabase_client", return_value=mock_db):
            resp = client.get("/admin/ocr/review-queue", headers=_AUTH_HEADER)
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# Prefill Endpoint Tests (Phase 986)
# ═══════════════════════════════════════════════════════════════════

class TestOcrPrefill:
    """GET /worker/ocr/prefill/{booking_id}/{capture_type} — wizard pre-fill."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from main import app
        _override_jwt_auth(app)
        self.client = TestClient(app, raise_server_exceptions=False)
        yield
        app.dependency_overrides.clear()

    def _prefill(self, booking_id="BK001", capture_type="identity_document_capture", db=None):
        mock_db = db or _make_mock_db(rows=[])
        with patch("api.ocr_router._get_supabase_client", return_value=mock_db):
            return self.client.get(
                f"/worker/ocr/prefill/{booking_id}/{capture_type}",
                headers=_AUTH_HEADER,
            )

    def test_no_ocr_result_returns_200_empty(self):
        """When no OCR result exists, return 200 with empty prefill (non-blocking)."""
        resp = self._prefill()
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert d["result_id"] is None
        assert d["ocr_status"] == "none"
        assert d["prefill_fields"] == {}
        assert d["review_required"] is True

    def test_pending_review_returns_extracted_fields(self):
        """pending_review result → prefill with extracted_fields."""
        row = {
            "id": "ocr-123",
            "status": "pending_review",
            "extracted_fields": {"full_name": "JANE DOE", "document_number": "AB123"},
            "corrected_fields": None,
            "field_confidences": {"full_name": 0.99, "document_number": 0.95},
            "overall_confidence": 0.97,
            "quality_warnings": [],
            "document_type": "PASSPORT",
            "provider_used": "local_mrz",
            "created_at": "2026-03-29T00:00:00Z",
            "error_message": None,
        }
        resp = self._prefill(db=_make_mock_db(rows=[row]))
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert d["result_id"] == "ocr-123"
        assert d["ocr_status"] == "pending_review"
        assert d["prefill_fields"]["full_name"] == "JANE DOE"
        assert d["review_required"] is True

    def test_corrected_fields_supersede_extracted(self):
        """corrected status → corrected_fields override extracted_fields."""
        row = {
            "id": "ocr-456",
            "status": "corrected",
            "extracted_fields": {"full_name": "JAN DOE", "document_number": "AB999"},
            "corrected_fields": {"full_name": "JANE DOE"},  # worker fixed name
            "field_confidences": {"full_name": 0.70, "document_number": 0.99},
            "overall_confidence": 0.84,
            "quality_warnings": ["blur"],
            "document_type": "NATIONAL_ID",
            "provider_used": "azure_document_intelligence",
            "created_at": "2026-03-29T00:01:00Z",
            "error_message": None,
        }
        resp = self._prefill(db=_make_mock_db(rows=[row]))
        assert resp.status_code == 200
        d = resp.json()["data"]
        # Corrected value wins
        assert d["prefill_fields"]["full_name"] == "JANE DOE"
        # Uncorrected field still there from extracted
        assert d["prefill_fields"]["document_number"] == "AB999"

    def test_low_confidence_fields_flagged(self):
        """Fields with confidence < 0.85 must appear in low_confidence_fields."""
        row = {
            "id": "ocr-789",
            "status": "pending_review",
            "extracted_fields": {
                "full_name": "JOHN DOE",
                "date_of_birth": "1990-01-15",
                "document_number": "XY999",
            },
            "corrected_fields": None,
            "field_confidences": {
                "full_name": 0.99,       # high
                "date_of_birth": 0.72,   # low → should be flagged
                "document_number": 0.80, # low → should be flagged
            },
            "overall_confidence": 0.84,
            "quality_warnings": [],
            "document_type": "PASSPORT",
            "provider_used": "local_mrz",
            "created_at": "2026-03-29T00:02:00Z",
            "error_message": None,
        }
        resp = self._prefill(db=_make_mock_db(rows=[row]))
        assert resp.status_code == 200
        d = resp.json()["data"]
        assert "date_of_birth" in d["low_confidence_fields"]
        assert "document_number" in d["low_confidence_fields"]
        assert "full_name" not in d["low_confidence_fields"]

    def test_review_required_always_true(self):
        """INV-OCR-02: review_required is always True in prefill response."""
        row = {
            "id": "ocr-confirmed",
            "status": "confirmed",
            "extracted_fields": {"full_name": "OK"},
            "corrected_fields": None,
            "field_confidences": {"full_name": 1.0},
            "overall_confidence": 1.0,
            "quality_warnings": [],
            "document_type": "PASSPORT",
            "provider_used": "azure_document_intelligence",
            "created_at": "2026-03-29T00:03:00Z",
            "error_message": None,
        }
        resp = self._prefill(db=_make_mock_db(rows=[row]))
        assert resp.status_code == 200
        assert resp.json()["data"]["review_required"] is True

    def test_response_has_required_keys(self):
        """Prefill response shape must be complete."""
        resp = self._prefill()  # empty result case
        assert resp.status_code == 200
        d = resp.json()["data"]
        for key in [
            "booking_id", "capture_type", "result_id", "ocr_status",
            "prefill_fields", "field_confidences", "low_confidence_fields",
            "quality_warnings", "overall_confidence", "document_type",
            "provider_used", "review_required",
        ]:
            assert key in d, f"Missing key in prefill response: {key}"

