"""
Phase 182 — Contract tests for outbound sync auto-triggers

Tests for:
  src/services/outbound_canceled_sync.py  (fire_canceled_sync)
  src/services/outbound_amended_sync.py   (fire_amended_sync)

Groups:
    A — fire_canceled_sync: happy path (channels + registry injected)
    B — fire_canceled_sync: edge cases (no channels, bad build_sync_plan, bad execute)
    C — fire_amended_sync: happy path (channels + registry injected)
    D — fire_amended_sync: edge cases (no channels, optional check_in/check_out)
    E — service.py wiring: BOOKING_CANCELED block imports fire_canceled_sync
    F — service.py wiring: BOOKING_AMENDED block imports fire_amended_sync
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.outbound_canceled_sync import fire_canceled_sync, CanceledSyncResult
from services.outbound_amended_sync import fire_amended_sync, AmendedSyncResult


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_CHANNEL = {
    "provider": "airbnb",
    "external_id": "EXT-99",
    "sync_strategy": "api_first",
    "sync_mode": "push",
    "enabled": True,
    "timezone": "UTC",
}

_REGISTRY = {
    "airbnb": {
        "provider": "airbnb",
        "tier": 1,
        "supports_api_write": True,
        "supports_ical_push": False,
        "supports_ical_pull": False,
        "rate_limit_per_min": 60,
    }
}

_BOOKING_ID = "airbnb_ABC123"
_PROPERTY_ID = "prop-1"
_TENANT_ID = "t-1"


def _make_report(status: str = "ok") -> MagicMock:
    result = MagicMock()
    result.provider = "airbnb"
    result.external_id = "EXT-99"
    result.strategy = "api_first"
    result.status = status
    result.message = f"mock {status}"
    report = MagicMock()
    report.results = [result]
    return report


# ---------------------------------------------------------------------------
# Group A — fire_canceled_sync: happy path
# ---------------------------------------------------------------------------

class TestGroupACanceledHappyPath:

    def test_a1_returns_canceled_sync_result_list(self):
        with patch("services.outbound_canceled_sync.build_sync_plan") as mock_build, \
             patch("services.outbound_canceled_sync.execute_sync_plan") as mock_exec:
            mock_build.return_value = [MagicMock()]
            mock_exec.return_value = _make_report("ok")

            results = fire_canceled_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )

        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], CanceledSyncResult)

    def test_a2_result_fields_correct(self):
        with patch("services.outbound_canceled_sync.build_sync_plan") as mock_build, \
             patch("services.outbound_canceled_sync.execute_sync_plan") as mock_exec:
            mock_build.return_value = [MagicMock()]
            mock_exec.return_value = _make_report("ok")

            results = fire_canceled_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )

        r = results[0]
        assert r.provider == "airbnb"
        assert r.external_id == "EXT-99"
        assert r.strategy == "api_first"
        assert r.status == "ok"

    def test_a3_build_sync_plan_called_with_correct_args(self):
        with patch("services.outbound_canceled_sync.build_sync_plan") as mock_build, \
             patch("services.outbound_canceled_sync.execute_sync_plan") as mock_exec:
            mock_build.return_value = [MagicMock()]
            mock_exec.return_value = _make_report()

            fire_canceled_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )

        mock_build.assert_called_once_with(
            booking_id=_BOOKING_ID,
            property_id=_PROPERTY_ID,
            channels=[_CHANNEL],
            registry=_REGISTRY,
        )

    def test_a4_execute_sync_plan_called_with_correct_args(self):
        fake_actions = [MagicMock()]
        with patch("services.outbound_canceled_sync.build_sync_plan") as mock_build, \
             patch("services.outbound_canceled_sync.execute_sync_plan") as mock_exec:
            mock_build.return_value = fake_actions
            mock_exec.return_value = _make_report()

            fire_canceled_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )

        mock_exec.assert_called_once_with(
            booking_id=_BOOKING_ID,
            property_id=_PROPERTY_ID,
            tenant_id=_TENANT_ID,
            actions=fake_actions,
            event_type="BOOKING_CANCELED",  # Phase 185
        )

    def test_a5_failed_status_propagated(self):
        with patch("services.outbound_canceled_sync.build_sync_plan") as mock_build, \
             patch("services.outbound_canceled_sync.execute_sync_plan") as mock_exec:
            mock_build.return_value = [MagicMock()]
            mock_exec.return_value = _make_report("failed")

            results = fire_canceled_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )

        assert results[0].status == "failed"


# ---------------------------------------------------------------------------
# Group B — fire_canceled_sync: edge cases
# ---------------------------------------------------------------------------

class TestGroupBCanceledEdgeCases:

    def test_b1_no_channels_returns_empty_list(self):
        results = fire_canceled_sync(
            booking_id=_BOOKING_ID,
            property_id=_PROPERTY_ID,
            tenant_id=_TENANT_ID,
            channels=[],
            registry=_REGISTRY,
        )
        assert results == []

    def test_b2_build_sync_plan_raises_returns_empty_list(self):
        with patch("services.outbound_canceled_sync.build_sync_plan") as mock_build:
            mock_build.side_effect = RuntimeError("DB timeout")

            results = fire_canceled_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )

        assert results == []

    def test_b3_execute_sync_plan_raises_returns_empty_list(self):
        with patch("services.outbound_canceled_sync.build_sync_plan") as mock_build, \
             patch("services.outbound_canceled_sync.execute_sync_plan") as mock_exec:
            mock_build.return_value = [MagicMock()]
            mock_exec.side_effect = RuntimeError("Network error")

            results = fire_canceled_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )

        assert results == []

    def test_b4_never_raises_on_any_exception(self):
        with patch("services.outbound_canceled_sync.build_sync_plan") as mock_build:
            mock_build.side_effect = Exception("Unexpected")
            # Must not raise
            result = fire_canceled_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )
        assert result == []

    def test_b5_multiple_results(self):
        """Multiple channels → multiple results."""
        result1 = MagicMock(provider="airbnb", external_id="A", strategy="api_first", status="ok", message="ok")
        result2 = MagicMock(provider="booking_com", external_id="B", strategy="api_first", status="failed", message="err")
        report = MagicMock()
        report.results = [result1, result2]

        with patch("services.outbound_canceled_sync.build_sync_plan") as mock_build, \
             patch("services.outbound_canceled_sync.execute_sync_plan") as mock_exec:
            mock_build.return_value = [MagicMock(), MagicMock()]
            mock_exec.return_value = report

            results = fire_canceled_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL, {**_CHANNEL, "provider": "booking_com"}],
                registry=_REGISTRY,
            )

        assert len(results) == 2
        assert results[0].provider == "airbnb"
        assert results[1].provider == "booking_com"


# ---------------------------------------------------------------------------
# Group C — fire_amended_sync: happy path
# ---------------------------------------------------------------------------

class TestGroupCAmendedHappyPath:

    def test_c1_returns_amended_sync_result_list(self):
        with patch("services.outbound_amended_sync.build_sync_plan") as mock_build, \
             patch("services.outbound_amended_sync.execute_sync_plan") as mock_exec:
            mock_build.return_value = [MagicMock()]
            r = MagicMock(provider="airbnb", external_id="X", strategy="api_first", status="ok", message="ok")
            mock_exec.return_value = MagicMock(results=[r])

            results = fire_amended_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                check_in="2025-05-10",
                check_out="2025-05-14",
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )

        assert isinstance(results, list)
        assert len(results) == 1
        assert isinstance(results[0], AmendedSyncResult)

    def test_c2_result_fields_correct(self):
        with patch("services.outbound_amended_sync.build_sync_plan") as mock_build, \
             patch("services.outbound_amended_sync.execute_sync_plan") as mock_exec:
            mock_build.return_value = [MagicMock()]
            r = MagicMock(provider="airbnb", external_id="X", strategy="api_first", status="ok", message="ok")
            mock_exec.return_value = MagicMock(results=[r])

            results = fire_amended_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )

        assert results[0].provider == "airbnb"
        assert results[0].status == "ok"

    def test_c3_check_in_check_out_are_optional(self):
        """fire_amended_sync must not raise if check_in / check_out are None."""
        with patch("services.outbound_amended_sync.build_sync_plan") as mock_build, \
             patch("services.outbound_amended_sync.execute_sync_plan") as mock_exec:
            mock_build.return_value = [MagicMock()]
            r = MagicMock(provider="airbnb", external_id="X", strategy="api_first", status="ok", message="ok")
            mock_exec.return_value = MagicMock(results=[r])

            results = fire_amended_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                # No check_in / check_out
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )

        assert len(results) == 1

    def test_c4_build_sync_plan_called_with_booking_args(self):
        with patch("services.outbound_amended_sync.build_sync_plan") as mock_build, \
             patch("services.outbound_amended_sync.execute_sync_plan") as mock_exec:
            mock_build.return_value = [MagicMock()]
            r = MagicMock(provider="airbnb", external_id="X", strategy="api_first", status="ok", message="ok")
            mock_exec.return_value = MagicMock(results=[r])

            fire_amended_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )

        mock_build.assert_called_once_with(
            booking_id=_BOOKING_ID,
            property_id=_PROPERTY_ID,
            channels=[_CHANNEL],
            registry=_REGISTRY,
        )


# ---------------------------------------------------------------------------
# Group D — fire_amended_sync: edge cases
# ---------------------------------------------------------------------------

class TestGroupDAmendedEdgeCases:

    def test_d1_no_channels_returns_empty(self):
        results = fire_amended_sync(
            booking_id=_BOOKING_ID,
            property_id=_PROPERTY_ID,
            tenant_id=_TENANT_ID,
            channels=[],
            registry=_REGISTRY,
        )
        assert results == []

    def test_d2_build_raises_swallowed(self):
        with patch("services.outbound_amended_sync.build_sync_plan") as mock_build:
            mock_build.side_effect = RuntimeError("build failed")
            results = fire_amended_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )
        assert results == []

    def test_d3_execute_raises_swallowed(self):
        with patch("services.outbound_amended_sync.build_sync_plan") as mock_build, \
             patch("services.outbound_amended_sync.execute_sync_plan") as mock_exec:
            mock_build.return_value = [MagicMock()]
            mock_exec.side_effect = RuntimeError("exec failed")
            results = fire_amended_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )
        assert results == []

    def test_d4_never_raises_on_any_exception(self):
        with patch("services.outbound_amended_sync.build_sync_plan") as mock_build:
            mock_build.side_effect = Exception("anything")
            result = fire_amended_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )
        assert result == []


# ---------------------------------------------------------------------------
# Group E — service.py wiring: BOOKING_CANCELED
# ---------------------------------------------------------------------------

class TestGroupEServiceWiringCanceled:

    def test_e1_fire_canceled_sync_is_importable(self):
        from services.outbound_canceled_sync import fire_canceled_sync as _f
        assert callable(_f)

    def test_e2_canceled_sync_result_is_dataclass(self):
        import dataclasses
        assert dataclasses.is_dataclass(CanceledSyncResult)

    def test_e3_canceled_result_has_required_fields(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(CanceledSyncResult)}
        assert {"provider", "external_id", "strategy", "status", "message"} <= fields

    def test_e4_service_module_has_canceled_block(self):
        """Smoke-assert that service.py includes outbound_canceled_sync reference."""
        import inspect
        from adapters.ota import service as svc
        src = inspect.getsource(svc)
        assert "outbound_canceled_sync" in src

    def test_e5_service_module_has_amended_block(self):
        """Smoke-assert that service.py includes outbound_amended_sync reference."""
        import inspect
        from adapters.ota import service as svc
        src = inspect.getsource(svc)
        assert "outbound_amended_sync" in src


# ---------------------------------------------------------------------------
# Group F — service.py wiring: BOOKING_AMENDED
# ---------------------------------------------------------------------------

class TestGroupFServiceWiringAmended:

    def test_f1_fire_amended_sync_is_importable(self):
        from services.outbound_amended_sync import fire_amended_sync as _f
        assert callable(_f)

    def test_f2_amended_sync_result_is_dataclass(self):
        import dataclasses
        assert dataclasses.is_dataclass(AmendedSyncResult)

    def test_f3_amended_result_has_required_fields(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(AmendedSyncResult)}
        assert {"provider", "external_id", "strategy", "status", "message"} <= fields

    def test_f4_amended_accepts_none_dates(self):
        """fire_amended_sync signature must accept None for check_in/check_out."""
        import inspect
        sig = inspect.signature(fire_amended_sync)
        assert "check_in" in sig.parameters
        assert "check_out" in sig.parameters
        assert sig.parameters["check_in"].default is None
        assert sig.parameters["check_out"].default is None

    def test_f5_amended_accepts_iso_date_string(self):
        """Passing ISO date strings must not type-error (accepted as Optional[str])."""
        with patch("services.outbound_amended_sync.build_sync_plan") as mock_build, \
             patch("services.outbound_amended_sync.execute_sync_plan") as mock_exec:
            mock_build.return_value = []
            mock_exec.return_value = MagicMock(results=[])

            result = fire_amended_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                check_in="2025-06-01",
                check_out="2025-06-07",
                channels=[_CHANNEL],
                registry=_REGISTRY,
            )
        assert isinstance(result, list)
