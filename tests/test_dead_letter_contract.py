"""
Phase 38 — Contract tests for the Dead Letter Queue (DLQ).

Verifies that:
1. write_to_dlq does not raise even when Supabase is unreachable (best-effort)
2. write_to_dlq swallows errors silently
3. dead_letter module is importable and callable
4. ingest_provider_event remains unaffected (backward compatibility)
"""
from __future__ import annotations

import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from adapters.ota.dead_letter import write_to_dlq
from adapters.ota.service import ingest_provider_event


# ---------------------------------------------------------------------------
# DLQ write_to_dlq — unit tests
# ---------------------------------------------------------------------------

class TestWriteToDlqIsNonBlocking:

    def test_does_not_raise_when_supabase_is_missing(self, monkeypatch) -> None:
        """DLQ write must be best-effort — must never raise."""
        monkeypatch.setenv("SUPABASE_URL", "")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")

        # Should complete without raising
        write_to_dlq(
            provider="bookingcom",
            event_type="BOOKING_CANCELED",
            rejection_code="BOOKING_NOT_FOUND",
            rejection_msg="test",
            envelope_json={"type": "BOOKING_CANCELED"},
        )

    def test_does_not_raise_when_client_throws(self, monkeypatch) -> None:
        """DLQ write must swallow any exception from the Supabase client."""
        monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")

        def _bad_client(url, key):
            raise RuntimeError("connection refused")

        with patch("adapters.ota.dead_letter.create_client", _bad_client):
            # Should not raise
            write_to_dlq(
                provider="bookingcom",
                event_type="BOOKING_CANCELED",
                rejection_code="P0001",
                rejection_msg="BOOKING_NOT_FOUND",
                envelope_json={"type": "BOOKING_CANCELED"},
                emitted_json=[],
            )

    def test_logs_warning_to_stderr_on_failure(self, monkeypatch, capsys) -> None:
        """DLQ failures must log a WARNING to stderr."""
        monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")

        def _bad_client(url, key):
            raise RuntimeError("simulated failure")

        with patch("adapters.ota.dead_letter.create_client", _bad_client):
            write_to_dlq(
                provider="bookingcom",
                event_type="BOOKING_CANCELED",
                rejection_code="P0001",
                rejection_msg="test",
                envelope_json={},
            )

        captured = capsys.readouterr()
        assert "[DLQ] WARNING" in captured.err

    def test_accepts_all_optional_fields_as_none(self, monkeypatch) -> None:
        """write_to_dlq must accept None for optional fields without raising."""
        monkeypatch.setenv("SUPABASE_URL", "")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")

        write_to_dlq(
            provider="expedia",
            event_type="BOOKING_CANCELED",
            rejection_code="BOOKING_NOT_FOUND",
            rejection_msg=None,
            envelope_json={},
            emitted_json=None,
            trace_id=None,
        )

    def test_calls_supabase_insert_when_configured(self, monkeypatch) -> None:
        """When Supabase is configured, write_to_dlq must call table().insert()."""
        monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "fake-key")

        mock_execute = MagicMock()
        mock_insert = MagicMock(return_value=MagicMock(execute=mock_execute))
        mock_table = MagicMock(return_value=MagicMock(insert=mock_insert))
        mock_client = MagicMock(table=mock_table)

        with patch("adapters.ota.dead_letter.create_client", return_value=mock_client):
            write_to_dlq(
                provider="bookingcom",
                event_type="BOOKING_CANCELED",
                rejection_code="P0001",
                rejection_msg="BOOKING_NOT_FOUND",
                envelope_json={"type": "BOOKING_CANCELED"},
                emitted_json=[{"type": "BOOKING_CANCELED", "payload": {"booking_id": "b_001"}}],
                trace_id="test-trace-001",
            )

        mock_table.assert_called_once_with("ota_dead_letter")
        call_kwargs = mock_insert.call_args[0][0]
        assert call_kwargs["provider"] == "bookingcom"
        assert call_kwargs["event_type"] == "BOOKING_CANCELED"
        assert call_kwargs["rejection_code"] == "P0001"
        assert call_kwargs["trace_id"] == "test-trace-001"
        mock_execute.assert_called_once()


# ---------------------------------------------------------------------------
# Backward compatibility — original ingest_provider_event remains thin wrapper
# ---------------------------------------------------------------------------

class TestServiceBackwardCompatibility:

    def test_ingest_provider_event_is_still_thin_wrapper(self, monkeypatch) -> None:
        """Original ingest_provider_event must remain unaffected by Phase 38 changes."""
        import adapters.ota.service as service_module

        calls = []
        expected_envelope = object()

        def fake_process(*, provider, payload, tenant_id):
            calls.append({"provider": provider, "payload": payload, "tenant_id": tenant_id})
            return expected_envelope

        monkeypatch.setattr(service_module, "process_ota_event", fake_process)

        result = ingest_provider_event(
            provider="bookingcom",
            payload={"event_id": "evt_001"},
            tenant_id="tenant_001",
        )

        assert result is expected_envelope
        assert calls == [{"provider": "bookingcom", "payload": {"event_id": "evt_001"}, "tenant_id": "tenant_001"}]
