"""
Phases 561-563 — Monitoring, Response Envelope, and E2E Tests

Tests for:
  - MonitoringMiddleware (Phase 562)
  - Response Envelope (Phase 561)
  - E2E integration flow (Phase 563)
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestMonitoringService:
    """Phase 562 — Monitoring module contract tests."""

    def test_import_monitoring(self):
        from services.monitoring import record_request
        assert record_request is not None

    def test_record_request_no_error(self):
        from services.monitoring import record_request
        record_request(route="/test", status_code=200, latency_s=0.015)

    def test_get_metrics(self):
        from services.monitoring import get_full_metrics
        metrics = get_full_metrics()
        assert isinstance(metrics, dict)
        assert "uptime_seconds" in metrics


class TestResponseEnvelope:
    """Phase 561 — Response envelope contract tests."""

    def test_import_envelope(self):
        from api.response_envelope import success, error, paginated
        assert success is not None
        assert error is not None
        assert paginated is not None

    def test_success_envelope_structure(self):
        from api.response_envelope import success
        import json
        resp = success(data={"foo": "bar"}, message="OK")
        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert body["ok"] is True
        assert body["data"]["foo"] == "bar"
        assert body["message"] == "OK"

    def test_error_envelope_structure(self):
        from api.response_envelope import error
        import json
        resp = error("Bad input", code="VALIDATION_ERROR", status_code=422)
        assert resp.status_code == 422
        body = json.loads(resp.body)
        assert body["ok"] is False
        assert body["error"]["message"] == "Bad input"
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_paginated_envelope_structure(self):
        from api.response_envelope import paginated
        import json
        resp = paginated(data=[1, 2, 3], total=10, page=1, per_page=3)
        body = json.loads(resp.body)
        assert body["ok"] is True
        assert body["data"] == [1, 2, 3]
        assert body["meta"]["total"] == 10
        assert body["meta"]["total_pages"] == 4


class TestEndToEndFlow:
    """Phase 563 — E2E integration tests."""

    def test_auth_token_extraction(self):
        import json, base64
        payload = {"tenant_id": "t-001", "role": "manager", "exp": 9999999999}
        payload_b64 = base64.b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        fake_token = f"header.{payload_b64}.signature"
        parts = fake_token.split(".")
        padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        decoded = json.loads(base64.b64decode(padded))
        assert decoded["tenant_id"] == "t-001"
        assert decoded["role"] == "manager"

    def test_export_service_end_to_end(self):
        from services.export_service import bookings_to_csv
        bookings = [
            {"booking_id": f"b-{i}", "property_id": "p-001", "guest_name": f"Guest{i}",
             "check_in_date": "2025-01-15", "check_out_date": "2025-01-18",
             "status": "confirmed", "source": "airbnb"}
            for i in range(5)
        ]
        csv = bookings_to_csv(bookings)
        lines = [l for l in csv.strip().split('\n') if l]
        assert len(lines) == 6  # 1 header + 5 data rows
        assert "b-0" in lines[1]
        assert "b-4" in lines[5]

    def test_response_envelope_round_trip(self):
        from api.response_envelope import success
        import json
        resp = success(data={"booking_id": "b-001", "status": "confirmed"})
        body = json.loads(resp.body)
        assert body["ok"] is True
        assert body["data"]["booking_id"] == "b-001"
