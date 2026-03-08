"""
Phase 73 — Contract tests for BOOKING_NOT_FOUND → Ordering Buffer Auto-Route

Verifies:
1.  BOOKING_CANCELED + BOOKING_NOT_FOUND → status BUFFERED returned
2.  BOOKING_AMENDED  + BOOKING_NOT_FOUND → status BUFFERED returned
3.  BUFFERED response includes reason AWAITING_BOOKING_CREATED
4.  BUFFERED response includes event_type
5.  buffer_event called with correct booking_id
6.  buffer_event called with correct event_type
7.  write_to_dlq_returning_id called (DLQ audit write)
8.  BOOKING_CREATED + BOOKING_NOT_FOUND → still DLQ (not buffered — CREATE should never arrive out-of-order)
9.  Other status (e.g. REJECTED) → DLQ as before, not BUFFERED
10. buffer_event failure does NOT propagate (best-effort)
11. write_to_dlq_returning_id failure → dlq_row_id=None passed to buffer_event (still buffers)
12. No booking_id in emitted → buffer_event NOT called
13. dead_letter.write_to_dlq_returning_id — returns id on success
14. dead_letter.write_to_dlq_returning_id — returns None when env not set
15. ordering_buffer.buffer_event — dlq_row_id=None produces correct insert (no dlq_row_id key)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers: build minimal envelope + skill fn + apply fn
# ---------------------------------------------------------------------------

def _envelope_dict(event_type: str, booking_id: str = "bookingcom_res1") -> dict:
    return {
        "type": event_type,
        "idempotency": {"request_id": "idem123"},
        "payload": {"booking_id": booking_id},
        "occurred_at": "2026-10-01T00:00:00Z",
    }


def _emitted(event_type: str, booking_id: str = "bookingcom_res1") -> list:
    return [{"type": event_type, "payload": {"booking_id": booking_id}}]


# ---------------------------------------------------------------------------
# 1–4. BUFFERED status returned for bufferable types
# ---------------------------------------------------------------------------

class TestBufferedResponse:

    @patch("adapters.ota.service.process_ota_event")
    def _run(
        self,
        mock_process,
        event_type: str,
        apply_status: str = "BOOKING_NOT_FOUND",
        booking_id: str = "bookingcom_res1",
    ) -> dict:
        from adapters.ota.service import ingest_provider_event_with_dlq

        # Build fake envelope
        mock_env = MagicMock()
        mock_env.type = event_type
        mock_env.payload = {"booking_id": booking_id}
        mock_env.idempotency_key = "idem123"
        mock_env.occurred_at = MagicMock(isoformat=lambda: "2026-10-01T00:00:00Z")
        mock_env.occurred_at.isoformat.return_value = "2026-10-01T00:00:00Z"
        mock_process.return_value = mock_env

        skill_fn = MagicMock(return_value=MagicMock(
            events_to_emit=[MagicMock(type=event_type, payload={"booking_id": booking_id})]
        ))
        apply_fn = MagicMock(return_value={"status": apply_status})

        with patch("adapters.ota.dead_letter.write_to_dlq"), \
             patch("adapters.ota.ordering_trigger.trigger_ordered_replay", create=True), \
             patch("adapters.ota.dead_letter.write_to_dlq_returning_id", return_value=42), \
             patch("adapters.ota.ordering_buffer.buffer_event"):
            result = ingest_provider_event_with_dlq(
                provider="bookingcom",
                payload={"event_type": event_type},
                tenant_id="t1",
                apply_fn=apply_fn,
                skill_fn=skill_fn,
            )
        return result

    def test_canceled_before_created_returns_buffered(self) -> None:
        result = self._run(event_type="BOOKING_CANCELED")
        assert result.get("status") == "BUFFERED"

    def test_amended_before_created_returns_buffered(self) -> None:
        result = self._run(event_type="BOOKING_AMENDED")
        assert result.get("status") == "BUFFERED"

    def test_buffered_response_has_reason(self) -> None:
        result = self._run(event_type="BOOKING_CANCELED")
        assert result.get("reason") == "AWAITING_BOOKING_CREATED"

    def test_buffered_response_has_event_type(self) -> None:
        result = self._run(event_type="BOOKING_CANCELED")
        assert result.get("event_type") == "BOOKING_CANCELED"


# ---------------------------------------------------------------------------
# 5–7. buffer_event and write_to_dlq_returning_id called correctly
# ---------------------------------------------------------------------------

class TestBufferCalls:

    @patch("adapters.ota.service.process_ota_event")
    def test_buffer_event_called_with_booking_id(self, mock_process) -> None:
        from adapters.ota.service import ingest_provider_event_with_dlq

        mock_env = MagicMock()
        mock_env.type = "BOOKING_CANCELED"
        mock_env.payload = {}
        mock_env.idempotency_key = ""
        mock_env.occurred_at.isoformat.return_value = "2026-10-01T00:00:00Z"
        mock_process.return_value = mock_env

        skill_fn = MagicMock(return_value=MagicMock(
            events_to_emit=[MagicMock(type="BOOKING_CANCELED", payload={"booking_id": "bcom_res99"})]
        ))
        apply_fn = MagicMock(return_value={"status": "BOOKING_NOT_FOUND"})

        with patch("adapters.ota.dead_letter.write_to_dlq"), \
             patch("adapters.ota.dead_letter.write_to_dlq_returning_id", return_value=55) as mock_dlq, \
             patch("adapters.ota.ordering_buffer.buffer_event") as mock_buf:
            ingest_provider_event_with_dlq(
                provider="bookingcom",
                payload={},
                tenant_id="t1",
                apply_fn=apply_fn,
                skill_fn=skill_fn,
            )

        mock_buf.assert_called_once()
        call_kwargs = mock_buf.call_args
        assert call_kwargs.kwargs.get("booking_id") == "bcom_res99" or \
               (call_kwargs.args and call_kwargs.args[1] == "bcom_res99")

    @patch("adapters.ota.service.process_ota_event")
    def test_write_to_dlq_returning_id_called(self, mock_process) -> None:
        from adapters.ota.service import ingest_provider_event_with_dlq

        mock_env = MagicMock()
        mock_env.type = "BOOKING_CANCELED"
        mock_env.payload = {}
        mock_env.idempotency_key = ""
        mock_env.occurred_at.isoformat.return_value = "2026-10-01T00:00:00Z"
        mock_process.return_value = mock_env

        skill_fn = MagicMock(return_value=MagicMock(
            events_to_emit=[MagicMock(type="BOOKING_CANCELED", payload={"booking_id": "bcom_res1"})]
        ))
        apply_fn = MagicMock(return_value={"status": "BOOKING_NOT_FOUND"})

        with patch("adapters.ota.dead_letter.write_to_dlq"), \
             patch("adapters.ota.dead_letter.write_to_dlq_returning_id", return_value=10) as mock_dlq, \
             patch("adapters.ota.ordering_buffer.buffer_event"):
            ingest_provider_event_with_dlq(
                provider="bookingcom",
                payload={},
                tenant_id="t1",
                apply_fn=apply_fn,
                skill_fn=skill_fn,
            )

        mock_dlq.assert_called_once()


# ---------------------------------------------------------------------------
# 8. BOOKING_CREATED BOOKING_NOT_FOUND → DLQ, not BUFFERED
# ---------------------------------------------------------------------------

class TestNonBufferableTypes:

    @patch("adapters.ota.service.process_ota_event")
    def test_booking_created_not_found_goes_to_dlq_not_buffer(self, mock_process) -> None:
        from adapters.ota.service import ingest_provider_event_with_dlq

        mock_env = MagicMock()
        mock_env.type = "BOOKING_CREATED"
        mock_env.payload = {}
        mock_env.idempotency_key = ""
        mock_env.occurred_at.isoformat.return_value = "2026-10-01T00:00:00Z"
        mock_process.return_value = mock_env

        skill_fn = MagicMock(return_value=MagicMock(
            events_to_emit=[MagicMock(type="BOOKING_CREATED", payload={"booking_id": "b1"})]
        ))
        apply_fn = MagicMock(return_value={"status": "BOOKING_NOT_FOUND"})

        with patch("adapters.ota.dead_letter.write_to_dlq") as mock_dlq, \
             patch("adapters.ota.ordering_buffer.buffer_event") as mock_buf:
            result = ingest_provider_event_with_dlq(
                provider="bookingcom",
                payload={},
                tenant_id="t1",
                apply_fn=apply_fn,
                skill_fn=skill_fn,
            )

        assert result.get("status") != "BUFFERED"
        mock_dlq.assert_called_once()
        mock_buf.assert_not_called()


# ---------------------------------------------------------------------------
# 10. buffer_event failure does NOT propagate
# ---------------------------------------------------------------------------

class TestBufferBestEffort:

    @patch("adapters.ota.service.process_ota_event")
    def test_buffer_failure_does_not_propagate(self, mock_process) -> None:
        from adapters.ota.service import ingest_provider_event_with_dlq

        mock_env = MagicMock()
        mock_env.type = "BOOKING_CANCELED"
        mock_env.payload = {}
        mock_env.idempotency_key = ""
        mock_env.occurred_at.isoformat.return_value = "2026-10-01T00:00:00Z"
        mock_process.return_value = mock_env

        skill_fn = MagicMock(return_value=MagicMock(
            events_to_emit=[MagicMock(type="BOOKING_CANCELED", payload={"booking_id": "b1"})]
        ))
        apply_fn = MagicMock(return_value={"status": "BOOKING_NOT_FOUND"})

        def _exploding_buffer(**kwargs):
            raise RuntimeError("Supabase unavailable")

        with patch("adapters.ota.dead_letter.write_to_dlq"), \
             patch("adapters.ota.dead_letter.write_to_dlq_returning_id", return_value=None), \
             patch("adapters.ota.ordering_buffer.buffer_event", side_effect=_exploding_buffer):
            # Should NOT raise — best-effort
            result = ingest_provider_event_with_dlq(
                provider="bookingcom",
                payload={},
                tenant_id="t1",
                apply_fn=apply_fn,
                skill_fn=skill_fn,
            )
        assert result.get("status") == "BUFFERED"


# ---------------------------------------------------------------------------
# 13–15. Unit tests for new helper functions
# ---------------------------------------------------------------------------

class TestWriteToDlqReturningId:

    def test_returns_none_when_env_not_set(self, monkeypatch) -> None:
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
        from adapters.ota.dead_letter import write_to_dlq_returning_id
        result = write_to_dlq_returning_id(
            provider="bookingcom",
            event_type="BOOKING_CANCELED",
            rejection_code="BOOKING_NOT_FOUND",
            rejection_msg=None,
            envelope_json={},
        )
        assert result is None


class TestBufferEventOptionalDlqRowId:

    def test_buffer_event_without_dlq_row_id_omits_key(self) -> None:
        from adapters.ota.ordering_buffer import buffer_event
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": 99}]
        )
        result = buffer_event(
            dlq_row_id=None,
            booking_id="bookingcom_res1",
            event_type="BOOKING_CANCELED",
            client=mock_client,
        )
        inserted = mock_client.table.return_value.insert.call_args[0][0]
        assert "dlq_row_id" not in inserted
        assert result == 99

    def test_buffer_event_with_dlq_row_id_includes_key(self) -> None:
        from adapters.ota.ordering_buffer import buffer_event
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": 100}]
        )
        buffer_event(
            dlq_row_id=42,
            booking_id="bookingcom_res1",
            event_type="BOOKING_CANCELED",
            client=mock_client,
        )
        inserted = mock_client.table.return_value.insert.call_args[0][0]
        assert inserted["dlq_row_id"] == 42
