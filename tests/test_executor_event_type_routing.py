"""
Phase 185 — Contract tests for execute_sync_plan event_type routing

Verifies that event_type correctly routes to:
  api_first:     .cancel()  when BOOKING_CANCELED
  api_first:     .amend()   when BOOKING_AMENDED
  api_first:     .send()    when BOOKING_CREATED (default)
  ical_fallback: .cancel()  when BOOKING_CANCELED
  ical_fallback: .push()    when BOOKING_CREATED / BOOKING_AMENDED

Groups:
  A — api_first routing
  B — ical_fallback routing
  C — backward compat (default event_type stays BOOKING_CREATED behaviour)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.outbound_executor import execute_sync_plan
from services.outbound_sync_trigger import SyncAction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _action(strategy: str = "api_first") -> SyncAction:
    return SyncAction(
        booking_id="airbnb_ABC",
        property_id="prop-1",
        provider="airbnb",
        external_id="EXT-1",
        strategy=strategy,
        reason="test",
        tier=1,
        rate_limit=60,
    )


def _adapter_result(method_name: str) -> MagicMock:
    ar = MagicMock()
    ar.provider = "airbnb"
    ar.external_id = "EXT-1"
    ar.strategy = "api_first"
    ar.status = "ok"
    ar.http_status = 200
    ar.message = f"{method_name} mock"
    return ar


# ---------------------------------------------------------------------------
# Group A — api_first routing
# ---------------------------------------------------------------------------

class TestGroupAApiFirstRouting:

    def _run(self, event_type: str, adapter: MagicMock) -> None:
        registry = {"airbnb": adapter}
        with patch("services.outbound_executor._build_registry", return_value=registry), \
             patch("services.outbound_executor._ADAPTER_REGISTRY_AVAILABLE", True):
            execute_sync_plan(
                booking_id="airbnb_ABC",
                property_id="prop-1",
                tenant_id="t-1",
                actions=[_action("api_first")],
                event_type=event_type,
            )

    def test_a1_booking_created_calls_send(self):
        adapter = MagicMock()
        adapter.send.return_value = _adapter_result("send")
        self._run("BOOKING_CREATED", adapter)
        adapter.send.assert_called_once()
        adapter.cancel.assert_not_called()

    def test_a2_booking_canceled_calls_cancel(self):
        adapter = MagicMock()
        adapter.cancel.return_value = _adapter_result("cancel")
        self._run("BOOKING_CANCELED", adapter)
        adapter.cancel.assert_called_once()
        adapter.send.assert_not_called()

    def test_a3_booking_amended_calls_amend(self):
        adapter = MagicMock()
        adapter.amend.return_value = _adapter_result("amend")
        with patch("services.outbound_executor._build_registry", return_value={"airbnb": adapter}), \
             patch("services.outbound_executor._ADAPTER_REGISTRY_AVAILABLE", True):
            execute_sync_plan(
                booking_id="airbnb_ABC",
                property_id="prop-1",
                tenant_id="t-1",
                actions=[_action("api_first")],
                event_type="BOOKING_AMENDED",
                check_in="2025-06-01",
                check_out="2025-06-07",
            )
        adapter.amend.assert_called_once()
        adapter.send.assert_not_called()

    def test_a4_amend_passes_iso_dates_to_adapter(self):
        adapter = MagicMock()
        adapter.amend.return_value = _adapter_result("amend")
        with patch("services.outbound_executor._build_registry", return_value={"airbnb": adapter}), \
             patch("services.outbound_executor._ADAPTER_REGISTRY_AVAILABLE", True):
            execute_sync_plan(
                booking_id="airbnb_ABC",
                property_id="prop-1",
                tenant_id="t-1",
                actions=[_action("api_first")],
                event_type="BOOKING_AMENDED",
                check_in="20250601",     # compact input
                check_out="20250607",
            )
        call_kwargs = adapter.amend.call_args.kwargs
        assert call_kwargs["check_in"] == "2025-06-01"    # normalised to ISO
        assert call_kwargs["check_out"] == "2025-06-07"

    def test_a5_cancel_sends_booking_and_external_id(self):
        adapter = MagicMock()
        adapter.cancel.return_value = _adapter_result("cancel")
        self._run("BOOKING_CANCELED", adapter)
        call_kwargs = adapter.cancel.call_args.kwargs
        assert call_kwargs["booking_id"] == "airbnb_ABC"
        assert call_kwargs["external_id"] == "EXT-1"


# ---------------------------------------------------------------------------
# Group B — ical_fallback routing
# ---------------------------------------------------------------------------

class TestGroupBIcalFallbackRouting:

    def _run(self, event_type: str, adapter: MagicMock) -> None:
        registry = {"airbnb": adapter}
        with patch("services.outbound_executor._build_registry", return_value=registry), \
             patch("services.outbound_executor._ADAPTER_REGISTRY_AVAILABLE", True):
            execute_sync_plan(
                booking_id="airbnb_ABC",
                property_id="prop-1",
                tenant_id="t-1",
                actions=[_action("ical_fallback")],
                event_type=event_type,
            )

    def test_b1_booking_created_calls_push(self):
        adapter = MagicMock()
        adapter.push.return_value = _adapter_result("push")
        self._run("BOOKING_CREATED", adapter)
        adapter.push.assert_called_once()
        adapter.cancel.assert_not_called()

    def test_b2_booking_canceled_calls_cancel(self):
        adapter = MagicMock()
        adapter.cancel.return_value = _adapter_result("cancel")
        self._run("BOOKING_CANCELED", adapter)
        adapter.cancel.assert_called_once()
        adapter.push.assert_not_called()

    def test_b3_booking_amended_calls_push(self):
        """BOOKING_AMENDED on ical_fallback still uses push (iCal re-push with new dates)."""
        adapter = MagicMock()
        adapter.push.return_value = _adapter_result("push")
        self._run("BOOKING_AMENDED", adapter)
        adapter.push.assert_called_once()
        adapter.cancel.assert_not_called()


# ---------------------------------------------------------------------------
# Group C — backward compatibility
# ---------------------------------------------------------------------------

class TestGroupCBackwardCompat:

    def test_c1_default_event_type_is_booking_created(self):
        """execute_sync_plan with no event_type defaults to BOOKING_CREATED → .send()."""
        adapter = MagicMock()
        adapter.send.return_value = _adapter_result("send")
        registry = {"airbnb": adapter}
        with patch("services.outbound_executor._build_registry", return_value=registry), \
             patch("services.outbound_executor._ADAPTER_REGISTRY_AVAILABLE", True):
            # No event_type arg
            execute_sync_plan(
                booking_id="airbnb_ABC",
                property_id="prop-1",
                tenant_id="t-1",
                actions=[_action("api_first")],
            )
        adapter.send.assert_called_once()

    def test_c2_adapter_without_cancel_falls_back_to_send(self):
        """If adapter lacks .cancel(), hasattr check is False → falls back to .send()."""
        adapter = MagicMock(spec=["send"])   # no cancel attr
        adapter.send.return_value = _adapter_result("send")
        registry = {"airbnb": adapter}
        with patch("services.outbound_executor._build_registry", return_value=registry), \
             patch("services.outbound_executor._ADAPTER_REGISTRY_AVAILABLE", True):
            execute_sync_plan(
                booking_id="airbnb_ABC",
                property_id="prop-1",
                tenant_id="t-1",
                actions=[_action("api_first")],
                event_type="BOOKING_CANCELED",
            )
        adapter.send.assert_called_once()

    def test_c3_adapter_without_amend_falls_back_to_send(self):
        """If adapter lacks .amend(), hasattr check is False → falls back to .send()."""
        adapter = MagicMock(spec=["send"])   # no amend attr
        adapter.send.return_value = _adapter_result("send")
        registry = {"airbnb": adapter}
        with patch("services.outbound_executor._build_registry", return_value=registry), \
             patch("services.outbound_executor._ADAPTER_REGISTRY_AVAILABLE", True):
            execute_sync_plan(
                booking_id="airbnb_ABC",
                property_id="prop-1",
                tenant_id="t-1",
                actions=[_action("api_first")],
                event_type="BOOKING_AMENDED",
            )
        adapter.send.assert_called_once()
