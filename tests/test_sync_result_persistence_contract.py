"""
Phase 144 — Contract Tests: Outbound Sync Result Persistence

Groups:
  A — sync_log_writer.write_sync_result() unit tests (client injection)
  B — outbound_executor calls _write_sync_result for every non-skip result
  C — best-effort: writer failure does NOT propagate (executor still succeeds)
  D — IHOUSE_SYNC_LOG_DISABLED=true opt-out (no Supabase call)
  E — skipped actions are NOT persisted
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BOOKING_ID  = "airbnb_ABC123"
PROPERTY_ID = "prop-1"
TENANT_ID   = "tenant-42"
PROVIDER    = "airbnb"
EXTERNAL_ID = "EXT-1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(error=None) -> MagicMock:
    resp = MagicMock()
    resp.error = error
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = resp
    return client


def _make_action(**overrides):
    from services.outbound_sync_trigger import SyncAction
    defaults = dict(
        booking_id=BOOKING_ID, property_id=PROPERTY_ID,
        provider=PROVIDER, external_id=EXTERNAL_ID,
        strategy="api_first", reason="test",
        tier="A", rate_limit=60,
    )
    defaults.update(overrides)
    return SyncAction(**defaults)


def _env_rt(monkeypatch, extra: dict | None = None):
    monkeypatch.setenv("IHOUSE_THROTTLE_DISABLED", "true")
    monkeypatch.setenv("IHOUSE_RETRY_DISABLED",    "true")
    monkeypatch.setenv("IHOUSE_DRY_RUN",           "false")
    monkeypatch.setenv("IHOUSE_SYNC_LOG_DISABLED", "false")
    for k, v in (extra or {}).items():
        monkeypatch.setenv(k, v)


# ===========================================================================
# Group A — sync_log_writer unit tests
# ===========================================================================

class TestSyncLogWriterUnit:

    def _call(self, monkeypatch, client, **kwargs):
        from services import sync_log_writer as mod
        defaults = dict(
            booking_id=BOOKING_ID, tenant_id=TENANT_ID,
            provider=PROVIDER, external_id=EXTERNAL_ID,
            strategy="api_first", status="ok",
            http_status=200, message="done",
            client=client,
        )
        defaults.update(kwargs)
        return mod.write_sync_result(**defaults)

    def test_returns_true_on_success(self, monkeypatch):
        _env_rt(monkeypatch)
        client = _make_client()
        result = self._call(monkeypatch, client)
        assert result is True

    def test_inserts_correct_row(self, monkeypatch):
        _env_rt(monkeypatch)
        client = _make_client()
        self._call(monkeypatch, client, message="Airbnb block sent.")

        inserted = client.table.return_value.insert.call_args[0][0]
        assert inserted["booking_id"]  == BOOKING_ID
        assert inserted["tenant_id"]   == TENANT_ID
        assert inserted["provider"]    == PROVIDER
        assert inserted["external_id"] == EXTERNAL_ID
        assert inserted["strategy"]    == "api_first"
        assert inserted["status"]      == "ok"
        assert inserted["http_status"] == 200
        assert inserted["message"]     == "Airbnb block sent."

    def test_table_name_is_outbound_sync_log(self, monkeypatch):
        _env_rt(monkeypatch)
        client = _make_client()
        self._call(monkeypatch, client)
        client.table.assert_called_once_with("outbound_sync_log")

    def test_returns_false_when_client_raises(self, monkeypatch):
        _env_rt(monkeypatch)
        client = MagicMock()
        client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("db down")
        result = self._call(monkeypatch, client, status="failed", http_status=503, message="err")
        assert result is False

    def test_long_message_truncated_to_2000_chars(self, monkeypatch):
        _env_rt(monkeypatch)
        client = _make_client()
        long_msg = "x" * 5000
        self._call(monkeypatch, client, status="failed", http_status=500, message=long_msg)

        inserted = client.table.return_value.insert.call_args[0][0]
        assert len(inserted["message"]) == 2000

    def test_disabled_returns_true_without_client_call(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_SYNC_LOG_DISABLED", "true")
        client = _make_client()
        from services import sync_log_writer as mod
        result = mod.write_sync_result(
            booking_id=BOOKING_ID, tenant_id=TENANT_ID,
            provider=PROVIDER, external_id=EXTERNAL_ID,
            strategy="api_first", status="ok",
            http_status=200, message="", client=client,
        )
        assert result is True
        client.table.assert_not_called()

    def test_http_status_none_inserted_as_none(self, monkeypatch):
        _env_rt(monkeypatch)
        client = _make_client()
        self._call(monkeypatch, client, status="dry_run", http_status=None, message="dry")

        inserted = client.table.return_value.insert.call_args[0][0]
        assert inserted["http_status"] is None
        assert inserted["status"] == "dry_run"


# ===========================================================================
# Group B — executor calls _write_sync_result for every non-skip result
# ===========================================================================

class TestExecutorWritesPersistence:

    def _stub_adapter(self, provider=PROVIDER, status="ok", http_status=200) -> MagicMock:
        from adapters.outbound import AdapterResult
        result = AdapterResult(
            provider=provider, external_id=EXTERNAL_ID,
            strategy="api_first", status=status,
            http_status=http_status, message="stub",
        )
        adapter = MagicMock()
        adapter.send.return_value = result
        adapter.push.return_value = result
        return adapter

    def test_write_called_once_per_ok_result(self, monkeypatch):
        _env_rt(monkeypatch)
        import services.outbound_executor as mod

        written: list = []
        monkeypatch.setattr(mod, "_write_sync_result", lambda **kw: written.append(kw) or True)
        monkeypatch.setattr(mod, "_SYNC_LOG_AVAILABLE", True)

        registry = {PROVIDER: self._stub_adapter()}
        with patch.object(mod, "_build_registry", return_value=registry), \
             patch.object(mod, "_ADAPTER_REGISTRY_AVAILABLE", True):
            report = mod.execute_sync_plan(
                booking_id=BOOKING_ID, property_id=PROPERTY_ID,
                tenant_id=TENANT_ID, actions=[_make_action()],
            )

        assert report.ok_count == 1
        assert len(written) == 1
        assert written[0]["booking_id"] == BOOKING_ID
        assert written[0]["tenant_id"]  == TENANT_ID
        assert written[0]["status"]     == "ok"

    def test_write_called_for_each_of_three_actions(self, monkeypatch):
        _env_rt(monkeypatch)
        import services.outbound_executor as mod

        written: list = []
        monkeypatch.setattr(mod, "_write_sync_result", lambda **kw: written.append(kw) or True)
        monkeypatch.setattr(mod, "_SYNC_LOG_AVAILABLE", True)

        registry = {
            "airbnb":     self._stub_adapter("airbnb"),
            "bookingcom": self._stub_adapter("bookingcom"),
            "expedia":    self._stub_adapter("expedia"),
        }
        actions = [
            _make_action(provider="airbnb"),
            _make_action(provider="bookingcom"),
            _make_action(provider="expedia"),
        ]
        with patch.object(mod, "_build_registry", return_value=registry), \
             patch.object(mod, "_ADAPTER_REGISTRY_AVAILABLE", True):
            mod.execute_sync_plan(
                booking_id=BOOKING_ID, property_id=PROPERTY_ID,
                tenant_id=TENANT_ID, actions=actions,
            )

        assert len(written) == 3

    def test_failed_result_persisted_with_correct_fields(self, monkeypatch):
        _env_rt(monkeypatch)
        import services.outbound_executor as mod

        written: list = []
        monkeypatch.setattr(mod, "_write_sync_result", lambda **kw: written.append(kw) or True)
        monkeypatch.setattr(mod, "_SYNC_LOG_AVAILABLE", True)

        stub = self._stub_adapter(status="failed", http_status=503)
        with patch.object(mod, "_build_registry", return_value={PROVIDER: stub}), \
             patch.object(mod, "_ADAPTER_REGISTRY_AVAILABLE", True):
            report = mod.execute_sync_plan(
                booking_id=BOOKING_ID, property_id=PROPERTY_ID,
                tenant_id=TENANT_ID, actions=[_make_action()],
            )

        assert report.failed_count == 1
        assert written[0]["status"]     == "failed"
        assert written[0]["http_status"] == 503


# ===========================================================================
# Group C — writer failure must be swallowed (executor not blocked)
# ===========================================================================

class TestWriterFailureIsSwallowed:

    def test_executor_succeeds_when_write_raises(self, monkeypatch):
        _env_rt(monkeypatch)
        import services.outbound_executor as mod

        def _always_raise(**_):
            raise RuntimeError("Supabase dead")

        monkeypatch.setattr(mod, "_write_sync_result", _always_raise)
        monkeypatch.setattr(mod, "_SYNC_LOG_AVAILABLE", True)

        from adapters.outbound import AdapterResult
        ok_r = AdapterResult(
            provider=PROVIDER, external_id=EXTERNAL_ID,
            strategy="api_first", status="ok",
            http_status=200, message="ok",
        )
        stub = MagicMock(); stub.send.return_value = ok_r

        with patch.object(mod, "_build_registry", return_value={PROVIDER: stub}), \
             patch.object(mod, "_ADAPTER_REGISTRY_AVAILABLE", True):
            report = mod.execute_sync_plan(
                booking_id=BOOKING_ID, property_id=PROPERTY_ID,
                tenant_id=TENANT_ID, actions=[_make_action()],
            )

        # Writer exception MUST NOT propagate
        assert report.ok_count == 1
        assert report.failed_count == 0


# ===========================================================================
# Group D — IHOUSE_SYNC_LOG_DISABLED opt-out
# ===========================================================================

class TestSyncLogDisabledOptOut:

    def test_disabled_no_client_call(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_SYNC_LOG_DISABLED", "true")
        from services import sync_log_writer as mod

        client = _make_client()
        result = mod.write_sync_result(
            booking_id="bk-1", tenant_id="t-1",
            provider="airbnb", external_id="EXT",
            strategy="api_first", status="ok",
            http_status=200, message="", client=client,
        )

        assert result is True
        client.table.assert_not_called()


# ===========================================================================
# Group E — skipped actions are NOT persisted
# ===========================================================================

class TestSkippedActionsNotPersisted:

    def test_skip_not_written_to_log(self, monkeypatch):
        _env_rt(monkeypatch)
        import services.outbound_executor as mod

        written: list = []
        monkeypatch.setattr(mod, "_write_sync_result", lambda **kw: written.append(kw) or True)
        monkeypatch.setattr(mod, "_SYNC_LOG_AVAILABLE", True)

        with patch.object(mod, "_ADAPTER_REGISTRY_AVAILABLE", False):
            report = mod.execute_sync_plan(
                booking_id=BOOKING_ID, property_id=PROPERTY_ID,
                tenant_id=TENANT_ID,
                actions=[_make_action(strategy="skip", reason="No channel map entry")],
            )

        assert report.skip_count == 1
        assert len(written) == 0   # skip actions must NOT be persisted
