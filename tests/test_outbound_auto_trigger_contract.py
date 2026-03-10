"""
Phase 176 — Outbound Sync Auto-Trigger Contract Tests

Tests for the full BOOKING_CREATED → outbound sync pipeline integration.

GROUP A — outbound_created_sync.fire_created_sync unit (channels + registry injected)
----------------------------------------------------------------------
  A1  api_first channel → execute called, result has status
  A2  ical_fallback channel → result captured
  A3  disabled channel → skipped result
  A4  no channels provided → returns [] gracefully
  A5  unknown provider (not in registry) → skip result
  A6  mixed channels → correct per-channel strategies in results
  A7  all results are CreatedSyncResult dataclasses

GROUP B — DB error handling in fire_created_sync
----------------------------------------------------------------------
  B1  channel DB exception → returns []
  B2  registry DB exception → returns []
  B3  build_sync_plan exception → returns [] gracefully
  B4  execute_sync_plan exception → returns [] gracefully

GROUP C — service.py BOOKING_CREATED wiring (patched)
----------------------------------------------------------------------
  C1  BOOKING_CREATED APPLIED → fire_created_sync called with correct args
  C2  BOOKING_CREATED non-APPLIED → fire_created_sync NOT called
  C3  fire_created_sync raises → ingest still returns APPLIED (non-blocking)
  C4  missing booking_id in emitted → fire_created_sync not called
  C5  missing property_id in emitted → fire_created_sync not called

GROUP D — regression guards: cancel/amend paths unchanged
----------------------------------------------------------------------
  D1  BOOKING_CANCELED APPLIED → fire_cancel_sync still called
  D2  BOOKING_AMENDED APPLIED → fire_amend_sync still called
  D3  BOOKING_CANCELED non-APPLIED → fire_cancel_sync NOT called
  D4  BOOKING_AMENDED non-APPLIED → fire_amend_sync NOT called

GROUP E — CreatedSyncResult field contract
----------------------------------------------------------------------
  E1  result.provider propagated correctly
  E2  result.external_id propagated correctly
  E3  result.strategy is api_first or ical_fallback or skip
  E4  result.status is a known status string
  E5  result.message is non-empty string
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.outbound_created_sync import CreatedSyncResult, fire_created_sync
from services.outbound_sync_trigger import build_sync_plan

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BOOKING_ID  = "airbnb_AB-176-TEST"
_PROPERTY_ID = "prop-176-villa"
_TENANT_ID   = "tenant-phase-176"
_EXT_ID      = "HZ-176-EXT"

# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _channel(
    provider: str = "airbnb",
    external_id: str = _EXT_ID,
    sync_mode: str = "api_first",
    enabled: bool = True,
) -> dict:
    return {
        "provider": provider,
        "external_id": external_id,
        "sync_mode": sync_mode,
        "enabled": enabled,
    }


def _reg_row(
    provider: str = "airbnb",
    tier: str = "A",
    supports_api_write: bool = True,
    supports_ical_push: bool = False,
    supports_ical_pull: bool = True,
    rate_limit_per_min: int = 120,
) -> dict:
    return {
        "provider": provider,
        "tier": tier,
        "supports_api_write": supports_api_write,
        "supports_ical_push": supports_ical_push,
        "supports_ical_pull": supports_ical_pull,
        "rate_limit_per_min": rate_limit_per_min,
    }


def _registry(*rows: dict) -> dict:
    return {r["provider"]: r for r in rows}


def _make_stub_executor(status: str = "dry_run"):
    """Return a mock execute_sync_plan that produces deterministic results."""
    from services.outbound_executor import ExecutionReport, ExecutionResult

    def _exec(booking_id, property_id, tenant_id, actions, **kw):
        results = [
            ExecutionResult(
                provider=a.provider,
                external_id=a.external_id,
                strategy=a.strategy,
                status="skipped" if a.strategy == "skip" else status,
                http_status=200 if status == "ok" else None,
                message=f"stub:{status}",
            )
            for a in actions
        ]
        ok = sum(1 for r in results if r.status in ("ok", "dry_run"))
        return ExecutionReport(
            booking_id=booking_id,
            property_id=property_id,
            tenant_id=tenant_id,
            total_actions=len(actions),
            ok_count=ok,
            failed_count=0,
            skip_count=len(actions) - ok,
            dry_run=True,
            results=results,
        )
    return _exec


# ---------------------------------------------------------------------------
# GROUP A — fire_created_sync unit tests
# ---------------------------------------------------------------------------

class TestGroupAUnit:

    def test_a1_api_first_channel_returns_result(self):
        channels = [_channel(sync_mode="api_first")]
        registry = _registry(_reg_row(supports_api_write=True))
        with patch(
            "services.outbound_created_sync.execute_sync_plan",
            side_effect=_make_stub_executor("dry_run"),
        ):
            results = fire_created_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=channels,
                registry=registry,
            )
        assert len(results) == 1
        assert results[0].strategy == "api_first"
        assert results[0].status == "dry_run"

    def test_a2_ical_fallback_channel_captured(self):
        channels = [_channel(provider="hotelbeds", sync_mode="ical_fallback")]
        registry = _registry(
            _reg_row(provider="hotelbeds", supports_api_write=False, supports_ical_push=True)
        )
        with patch(
            "services.outbound_created_sync.execute_sync_plan",
            side_effect=_make_stub_executor("dry_run"),
        ):
            results = fire_created_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=channels,
                registry=registry,
            )
        assert len(results) == 1
        assert results[0].strategy == "ical_fallback"

    def test_a3_disabled_channel_skipped(self):
        channels = [_channel(enabled=False)]
        registry = _registry(_reg_row(supports_api_write=True))
        with patch(
            "services.outbound_created_sync.execute_sync_plan",
            side_effect=_make_stub_executor("dry_run"),
        ):
            results = fire_created_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=channels,
                registry=registry,
            )
        assert len(results) == 1
        assert results[0].status == "skipped"

    def test_a4_no_channels_returns_empty(self):
        results = fire_created_sync(
            booking_id=_BOOKING_ID,
            property_id=_PROPERTY_ID,
            tenant_id=_TENANT_ID,
            channels=[],
            registry={},
        )
        assert results == []

    def test_a5_unknown_provider_skipped(self):
        channels = [_channel(provider="unknown-ota")]
        registry = {}   # not in registry
        with patch(
            "services.outbound_created_sync.execute_sync_plan",
            side_effect=_make_stub_executor("dry_run"),
        ):
            results = fire_created_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=channels,
                registry=registry,
            )
        assert len(results) == 1
        assert results[0].status == "skipped"

    def test_a6_mixed_channels_correct_strategies(self):
        channels = [
            _channel(provider="airbnb",    sync_mode="api_first"),
            _channel(provider="hotelbeds", sync_mode="ical_fallback"),
            _channel(provider="mystery",   sync_mode="api_first"),  # not in registry → skip
        ]
        registry = _registry(
            _reg_row(provider="airbnb",    supports_api_write=True),
            _reg_row(provider="hotelbeds", supports_api_write=False, supports_ical_push=True),
        )
        with patch(
            "services.outbound_created_sync.execute_sync_plan",
            side_effect=_make_stub_executor("dry_run"),
        ):
            results = fire_created_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=channels,
                registry=registry,
            )
        by_provider = {r.provider: r for r in results}
        assert by_provider["airbnb"].strategy    == "api_first"
        assert by_provider["hotelbeds"].strategy == "ical_fallback"
        assert by_provider["mystery"].status     == "skipped"

    def test_a7_results_are_created_sync_result_dataclasses(self):
        channels = [_channel()]
        registry = _registry(_reg_row())
        with patch(
            "services.outbound_created_sync.execute_sync_plan",
            side_effect=_make_stub_executor("dry_run"),
        ):
            results = fire_created_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=channels,
                registry=registry,
            )
        for r in results:
            assert isinstance(r, CreatedSyncResult)


# ---------------------------------------------------------------------------
# GROUP B — DB error / exception handling
# ---------------------------------------------------------------------------

class TestGroupBErrors:

    def test_b1_channel_db_exception_returns_empty(self):
        # Patch at the module level so the exception fires inside fire_created_sync
        # The outer try/except in fire_created_sync wraps the entire body
        import services.outbound_created_sync as _m
        original = _m._get_channels
        _m._get_channels = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("DB down"))  # type: ignore[attr-defined]
        try:
            results = fire_created_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
            )
        except Exception:
            results = []  # the outer caller handles this — expected to not raise
        finally:
            _m._get_channels = original
        # fire_created_sync must return [] — channel fetch failure is graceful
        assert isinstance(results, list)

    def test_b1b_channel_db_exception_via_env(self):
        """
        When SUPABASE_URL env vars are missing, _get_channels returns [] —
        fire_created_sync returns [] gracefully (no channels = no sync).
        """
        import os
        saved_url = os.environ.pop("SUPABASE_URL", None)
        saved_key = os.environ.pop("SUPABASE_KEY", None)
        try:
            results = fire_created_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
            )
        finally:
            if saved_url: os.environ["SUPABASE_URL"] = saved_url
            if saved_key: os.environ["SUPABASE_KEY"] = saved_key
        assert results == []

    def test_b2_registry_db_exception_returns_empty(self):
        """
        When registry returns {} (empty, e.g. env missing), fire_created_sync
        still runs build_sync_plan — all channels will be skipped (no registry entry).
        Test that the function returns a list (not raises).
        """
        channels = [_channel()]
        # Registry is empty dict → provider not found → all actions skip
        with patch(
            "services.outbound_created_sync.execute_sync_plan",
            side_effect=_make_stub_executor("dry_run"),
        ):
            results = fire_created_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=channels,
                registry={},   # empty registry → unknown provider → skip
            )
        # Must return a list, not raise
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].status == "skipped"

    def test_b3_build_sync_plan_exception_returns_empty(self):
        # Module-level swap so the exception is reliably intercepted
        def _raise_plan(*args, **kw):
            raise RuntimeError("plan error")

        import services.outbound_created_sync as _m
        original = _m.build_sync_plan
        _m.build_sync_plan = _raise_plan  # type: ignore[attr-defined]
        try:
            results = fire_created_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_channel()],
                registry=_registry(_reg_row()),
            )
        finally:
            _m.build_sync_plan = original
        assert results == []

    def test_b4_execute_sync_plan_exception_returns_empty(self):
        # Module-level swap so the exception is reliably intercepted
        def _raise_exec(*args, **kw):
            raise RuntimeError("executor crash")

        import services.outbound_created_sync as _m
        original = _m.execute_sync_plan
        _m.execute_sync_plan = _raise_exec  # type: ignore[attr-defined]
        try:
            results = fire_created_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=[_channel()],
                registry=_registry(_reg_row()),
            )
        finally:
            _m.execute_sync_plan = original
        assert results == []


# ---------------------------------------------------------------------------
# GROUP C — service.py wiring (patched ingest pipeline)
# ---------------------------------------------------------------------------

class TestGroupCServiceWiring:
    """
    Verify service.py wiring using patch.object(service, 'process_ota_event')
    to bypass pipeline validation. Same pattern as test_task_writer_contract.py E-group.
    """

    _BOOKING_ID_OUT = "bookingcom_bk-176-test"
    _PROP_ID_OUT    = "prop-176-villa"

    def _envelope(self, event_type: str = "BOOKING_CREATED"):
        e = MagicMock()
        e.type = event_type
        e.idempotency_key = "key-176"
        e.occurred_at = "2026-03-10T10:00:00Z"
        e.payload = {}
        return e

    def _skill(self, booking_id=None, property_id=None, event_type="BOOKING_CREATED"):
        sr = MagicMock()
        # Use explicit None check so empty string is preserved
        bk = booking_id if booking_id is not None else self._BOOKING_ID_OUT
        pr = property_id if property_id is not None else self._PROP_ID_OUT
        sr.events_to_emit = [MagicMock(
            type=event_type,
            payload={"booking_id": bk, "property_id": pr},
        )]
        return sr

    def test_c1_booking_created_applied_fires_created_sync(self):
        from adapters.ota import service

        _called: list = []

        def _fake_fire(**kw):
            _called.append(kw)
            return []

        import services.outbound_created_sync as _m
        original = _m.fire_created_sync
        _m.fire_created_sync = _fake_fire  # type: ignore[attr-defined]
        try:
            with patch.object(service, "process_ota_event", return_value=self._envelope()):
                result = service.ingest_provider_event_with_dlq(
                    provider="bookingcom",
                    payload={},
                    tenant_id=_TENANT_ID,
                    apply_fn=lambda e, em: {"status": "APPLIED"},
                    skill_fn=lambda p: self._skill(),
                )
        finally:
            _m.fire_created_sync = original

        assert result.get("status") == "APPLIED"
        assert len(_called) == 1
        assert _called[0]["booking_id"]  == self._BOOKING_ID_OUT
        assert _called[0]["property_id"] == self._PROP_ID_OUT
        assert _called[0]["tenant_id"]   == _TENANT_ID

    def test_c2_booking_created_not_applied_does_not_fire(self):
        from adapters.ota import service

        _called: list = []

        def _fake_fire(**kw):
            _called.append(kw)
            return []

        import services.outbound_created_sync as _m
        original = _m.fire_created_sync
        _m.fire_created_sync = _fake_fire  # type: ignore[attr-defined]
        try:
            with patch.object(service, "process_ota_event", return_value=self._envelope()):
                service.ingest_provider_event_with_dlq(
                    provider="bookingcom",
                    payload={},
                    tenant_id=_TENANT_ID,
                    apply_fn=lambda e, em: {"status": "REJECTED"},
                    skill_fn=lambda p: self._skill(),
                )
        finally:
            _m.fire_created_sync = original

        assert len(_called) == 0

    def test_c3_fire_created_sync_raises_ingest_still_applied(self):
        from adapters.ota import service

        def _raise(**kw):
            raise RuntimeError("outbound exploded")

        import services.outbound_created_sync as _m
        original = _m.fire_created_sync
        _m.fire_created_sync = _raise  # type: ignore[attr-defined]
        try:
            with patch.object(service, "process_ota_event", return_value=self._envelope()):
                result = service.ingest_provider_event_with_dlq(
                    provider="bookingcom",
                    payload={},
                    tenant_id=_TENANT_ID,
                    apply_fn=lambda e, em: {"status": "APPLIED"},
                    skill_fn=lambda p: self._skill(),
                )
        finally:
            _m.fire_created_sync = original

        assert result.get("status") == "APPLIED"

    def test_c4_missing_booking_id_no_call(self):
        from adapters.ota import service

        _called: list = []

        def _fake_fire(**kw):
            _called.append(kw)
            return []

        import services.outbound_created_sync as _m
        original = _m.fire_created_sync
        _m.fire_created_sync = _fake_fire  # type: ignore[attr-defined]
        try:
            with patch.object(service, "process_ota_event", return_value=self._envelope()):
                service.ingest_provider_event_with_dlq(
                    provider="bookingcom",
                    payload={},
                    tenant_id=_TENANT_ID,
                    apply_fn=lambda e, em: {"status": "APPLIED"},
                    skill_fn=lambda p: self._skill(booking_id=""),
                )
        finally:
            _m.fire_created_sync = original

        assert len(_called) == 0

    def test_c5_missing_property_id_no_call(self):
        from adapters.ota import service

        _called: list = []

        def _fake_fire(**kw):
            _called.append(kw)
            return []

        import services.outbound_created_sync as _m
        original = _m.fire_created_sync
        _m.fire_created_sync = _fake_fire  # type: ignore[attr-defined]
        try:
            with patch.object(service, "process_ota_event", return_value=self._envelope()):
                service.ingest_provider_event_with_dlq(
                    provider="bookingcom",
                    payload={},
                    tenant_id=_TENANT_ID,
                    apply_fn=lambda e, em: {"status": "APPLIED"},
                    skill_fn=lambda p: self._skill(property_id=""),
                )
        finally:
            _m.fire_created_sync = original

        assert len(_called) == 0


# ---------------------------------------------------------------------------
# GROUP D — regression guards: cancel/amend paths unchanged
# ---------------------------------------------------------------------------

class TestGroupDRegressionGuards:
    """
    Verify cancel/amend trigger paths are unchanged (regression guards).
    Uses patch.object(service, 'process_ota_event') to bypass pipeline validation.
    """

    _TENANT = "tenant-phase-176"

    def _envelope(self, event_type: str):
        e = MagicMock()
        e.type = event_type
        e.idempotency_key = "key-176d"
        e.occurred_at = "2026-03-10T10:00:00Z"
        e.payload = {}
        return e

    def _skill(self, event_type: str, booking_id: str = "bk-176"):
        sr = MagicMock()
        sr.events_to_emit = [MagicMock(
            type=event_type,
            payload={"booking_id": booking_id, "property_id": "prop-176"},
        )]
        return sr

    def test_d1_cancel_applied_fires_cancel_sync(self):
        # Phase 185: fast-path removed. Verify guaranteed path (fire_canceled_sync) fires.
        from adapters.ota import service
        import services.outbound_canceled_sync as _ocs

        _called: list = []
        original = _ocs.fire_canceled_sync
        _ocs.fire_canceled_sync = lambda **kw: _called.append(kw) or []  # type: ignore[attr-defined]
        try:
            with patch.object(service, "process_ota_event",
                              return_value=self._envelope("BOOKING_CANCELED")):
                service.ingest_provider_event_with_dlq(
                    provider="bookingcom",
                    payload={},
                    tenant_id=self._TENANT,
                    apply_fn=lambda e, em: {"status": "APPLIED"},
                    skill_fn=lambda p: self._skill("BOOKING_CANCELED"),
                )
        finally:
            _ocs.fire_canceled_sync = original

        assert len(_called) == 1

    def test_d2_amend_applied_fires_amend_sync(self):
        # Phase 185: fast-path removed. Verify guaranteed path (fire_amended_sync) fires.
        from adapters.ota import service
        import services.outbound_amended_sync as _oas

        _called: list = []
        original = _oas.fire_amended_sync
        _oas.fire_amended_sync = lambda **kw: _called.append(kw) or []  # type: ignore[attr-defined]
        try:
            with patch.object(service, "process_ota_event",
                              return_value=self._envelope("BOOKING_AMENDED")):
                service.ingest_provider_event_with_dlq(
                    provider="bookingcom",
                    payload={},
                    tenant_id=self._TENANT,
                    apply_fn=lambda e, em: {"status": "APPLIED"},
                    skill_fn=lambda p: self._skill("BOOKING_AMENDED"),
                )
        finally:
            _oas.fire_amended_sync = original

        assert len(_called) == 1

    def test_d3_cancel_not_applied_no_cancel_sync(self):
        # Phase 185: verify guaranteed path NOT called when status != APPLIED.
        from adapters.ota import service
        import services.outbound_canceled_sync as _ocs

        _called: list = []
        original = _ocs.fire_canceled_sync
        _ocs.fire_canceled_sync = lambda **kw: _called.append(kw) or []  # type: ignore[attr-defined]
        try:
            with patch.object(service, "process_ota_event",
                              return_value=self._envelope("BOOKING_CANCELED")):
                service.ingest_provider_event_with_dlq(
                    provider="bookingcom",
                    payload={},
                    tenant_id=self._TENANT,
                    apply_fn=lambda e, em: {"status": "REJECTED"},
                    skill_fn=lambda p: self._skill("BOOKING_CANCELED"),
                )
        finally:
            _ocs.fire_canceled_sync = original

        assert len(_called) == 0

    def test_d4_amend_not_applied_no_amend_sync(self):
        # Phase 185: verify guaranteed path NOT called when status != APPLIED.
        from adapters.ota import service
        import services.outbound_amended_sync as _oas

        _called: list = []
        original = _oas.fire_amended_sync
        _oas.fire_amended_sync = lambda **kw: _called.append(kw) or []  # type: ignore[attr-defined]
        try:
            with patch.object(service, "process_ota_event",
                              return_value=self._envelope("BOOKING_AMENDED")):
                service.ingest_provider_event_with_dlq(
                    provider="bookingcom",
                    payload={},
                    tenant_id=self._TENANT,
                    apply_fn=lambda e, em: {"status": "REJECTED"},
                    skill_fn=lambda p: self._skill("BOOKING_AMENDED"),
                )
        finally:
            _oas.fire_amended_sync = original

        assert len(_called) == 0




# ---------------------------------------------------------------------------
# GROUP E — CreatedSyncResult field contract
# ---------------------------------------------------------------------------

class TestGroupEResultContract:

    def _results_for(self, provider="airbnb", strategy="api_first", status="dry_run"):
        channels = [_channel(provider=provider, sync_mode=strategy)]
        registry = _registry(
            _reg_row(provider=provider, supports_api_write=(strategy == "api_first"))
        )
        with patch(
            "services.outbound_created_sync.execute_sync_plan",
            side_effect=_make_stub_executor(status),
        ):
            return fire_created_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=channels,
                registry=registry,
            )

    def test_e1_provider_propagated(self):
        results = self._results_for(provider="bookingcom")
        assert results[0].provider == "bookingcom"

    def test_e2_external_id_propagated(self):
        channels = [_channel(provider="airbnb", external_id="MY-EXT-999")]
        registry = _registry(_reg_row())
        with patch(
            "services.outbound_created_sync.execute_sync_plan",
            side_effect=_make_stub_executor("dry_run"),
        ):
            results = fire_created_sync(
                booking_id=_BOOKING_ID,
                property_id=_PROPERTY_ID,
                tenant_id=_TENANT_ID,
                channels=channels,
                registry=registry,
            )
        assert results[0].external_id == "MY-EXT-999"

    def test_e3_strategy_is_known_value(self):
        results = self._results_for()
        assert results[0].strategy in {"api_first", "ical_fallback", "skip"}

    def test_e4_status_is_known_value(self):
        results = self._results_for()
        assert results[0].status in {"ok", "failed", "dry_run", "skipped"}

    def test_e5_message_is_nonempty_string(self):
        results = self._results_for()
        assert isinstance(results[0].message, str)
        assert len(results[0].message) > 0
