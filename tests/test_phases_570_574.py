"""
Phases 570-574 — Tests for response envelope, input validation, and API docs.
"""
import pytest
import json
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestResponseEnvelopeMiddleware:
    """Phase 570-572 — Middleware contract tests."""

    def test_import_middleware(self):
        from api.response_envelope_middleware import ResponseEnvelopeMiddleware
        assert ResponseEnvelopeMiddleware is not None

    def test_import_exception_handlers(self):
        from api.response_envelope_middleware import register_exception_handlers
        assert register_exception_handlers is not None

    def test_envelope_success_format(self):
        from api.response_envelope import success
        resp = success(data={"bookings": []}, message="OK")
        body = json.loads(resp.body)
        assert body["ok"] is True
        assert body["data"] == {"bookings": []}

    def test_envelope_error_format(self):
        from api.response_envelope import error
        resp = error("Not found", code="NOT_FOUND", status_code=404)
        body = json.loads(resp.body)
        assert body["ok"] is False
        assert body["error"]["code"] == "NOT_FOUND"

    def test_envelope_paginated(self):
        from api.response_envelope import paginated
        resp = paginated(data=[1, 2, 3], total=100, page=2, per_page=3)
        body = json.loads(resp.body)
        assert body["ok"] is True
        assert body["meta"]["total"] == 100
        assert body["meta"]["page"] == 2
        assert body["meta"]["total_pages"] == 34


class TestInputModels:
    """Phase 573 — Pydantic input model validation."""

    def test_booking_create_valid(self):
        from api.input_models import BookingCreateRequest
        req = BookingCreateRequest(
            booking_id="b-001",
            tenant_id="t-001",
            source="airbnb",
            property_id="p-001",
            check_in="2025-01-15",
            check_out="2025-01-18",
        )
        assert req.booking_id == "b-001"

    def test_booking_create_invalid_date(self):
        from api.input_models import BookingCreateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            BookingCreateRequest(
                booking_id="b-001",
                tenant_id="t-001",
                source="airbnb",
                property_id="p-001",
                check_in="not-a-date",
                check_out="2025-01-18",
            )

    def test_booking_create_missing_required(self):
        from api.input_models import BookingCreateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            BookingCreateRequest(
                booking_id="b-001",
                # missing tenant_id, source, property_id, etc.
            )

    def test_task_create_valid(self):
        from api.input_models import TaskCreateRequest
        req = TaskCreateRequest(
            tenant_id="t-001",
            property_id="p-001",
            task_kind="cleaning",
            priority="high",
        )
        assert req.priority == "high"

    def test_task_create_invalid_priority(self):
        from api.input_models import TaskCreateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            TaskCreateRequest(
                tenant_id="t-001",
                property_id="p-001",
                task_kind="cleaning",
                priority="super_high",  # invalid
            )

    def test_property_create_valid(self):
        from api.input_models import PropertyCreateRequest
        req = PropertyCreateRequest(
            tenant_id="t-001",
            name="Beach Villa",
            bedrooms=3,
        )
        assert req.name == "Beach Villa"

    def test_property_create_invalid_bedrooms(self):
        from api.input_models import PropertyCreateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PropertyCreateRequest(
                tenant_id="t-001",
                name="X",
                bedrooms=-5,  # invalid
            )

    def test_maintenance_create_valid(self):
        from api.input_models import MaintenanceCreateRequest
        req = MaintenanceCreateRequest(
            property_id="p-001",
            title="Broken AC",
            priority="urgent",
        )
        assert req.priority == "urgent"

    def test_booking_flags_valid(self):
        from api.input_models import BookingFlagsRequest
        req = BookingFlagsRequest(is_vip=True, operator_note="VIP guest")
        assert req.is_vip is True


class TestApiDocs:
    """Phase 574 — API documentation metadata verification."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_main(self):
        try:
            from main import app  # noqa: F401
        except ImportError:
            pytest.skip("main.py not importable in test env (relative imports)")

    def test_main_app_has_description(self):
        from main import app
        assert app.description is not None
        assert "iHouse Core" in app.description

    def test_main_app_has_tags(self):
        from main import app
        assert app.openapi_tags is not None
        assert len(app.openapi_tags) > 10

    def test_main_app_has_version(self):
        from main import app
        assert app.version is not None

    def test_main_app_has_contact(self):
        from main import app
        assert app.contact is not None
        assert "url" in app.contact
