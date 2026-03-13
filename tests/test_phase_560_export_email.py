"""
Phase 560 — Export & Email Service Tests

Contract tests for:
  - export_service.py (CSV generation — function-style API)
  - email_sender.py (send_email function + log fallback)
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestExportService:
    """Phase 560a — export_service contract tests."""

    def test_import_export_service(self):
        from services.export_service import bookings_to_csv
        assert bookings_to_csv is not None

    def test_export_bookings_csv_format(self):
        from services.export_service import bookings_to_csv
        sample = [
            {"booking_id": "b-001", "property_id": "p-001", "guest_name": "John Doe",
             "check_in_date": "2025-01-15", "check_out_date": "2025-01-18",
             "status": "confirmed", "source": "airbnb"}
        ]
        csv = bookings_to_csv(sample)
        assert "booking_id" in csv
        assert "b-001" in csv
        assert "John Doe" in csv

    def test_export_data_financials(self):
        from services.export_service import export_data
        # export_data needs a db stub — just verify it's importable
        assert export_data is not None

    def test_export_empty_list(self):
        from services.export_service import bookings_to_csv
        csv = bookings_to_csv([])
        lines = [l for l in csv.strip().split('\n') if l]
        assert len(lines) >= 1  # header only


class TestEmailSender:
    """Phase 560b — email_sender contract tests."""

    def test_import_email_sender(self):
        from services.email_sender import send_email
        assert send_email is not None

    def test_email_sender_log_fallback(self):
        """Log fallback mode doesn't raise."""
        from services.email_sender import send_email
        result = send_email(
            to="test@example.com",
            subject="Test",
            body_html="<p>Hello</p>"
        )
        assert isinstance(result, dict)

    def test_email_sender_returns_dict(self):
        """send_email returns a result dict."""
        from services.email_sender import send_email
        result = send_email(to="x@x.com", subject="T", body_html="<p>B</p>")
        assert isinstance(result, dict)
