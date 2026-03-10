"""
Phase 181 — Contract tests for SSE Broker + endpoint

Groups:
    A — broker: subscribe + publish + tenant isolation
    B — broker: diagnostics (subscriber_count)
    C — broker: queue full guard (eviction)
    D — broker: _resolve_tenant (sse_router)
    E — endpoint: smoke test (response headers, media type)
"""
from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from main import app  # PYTHONPATH=src

from channels.sse_broker import SseBroker
from api.sse_router import _resolve_tenant

client = TestClient(app)


# ---------------------------------------------------------------------------
# Group A — Broker: subscribe + publish + tenant isolation
# ---------------------------------------------------------------------------

class TestGroupABroker:

    def test_a1_publish_delivers_to_subscriber(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1") as q:
                b._dispatch("t1", {"type": "task_update", "task_id": "T-1"})
                evt = await asyncio.wait_for(q.get(), timeout=1.0)
                received.append(evt)
            assert len(received) == 1
            assert received[0]["type"] == "task_update"
        asyncio.run(run())

    def test_a2_tenant_isolation_different_tenant_not_received(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1") as q:
                b._dispatch("t2", {"type": "task_update"})
                try:
                    await asyncio.wait_for(q.get(), timeout=0.1)
                    received.append("got_event")
                except asyncio.TimeoutError:
                    received.append("timeout")
            assert received == ["timeout"]
        asyncio.run(run())

    def test_a3_multiple_subscribers_same_tenant_all_receive(self):
        async def run():
            b = SseBroker()
            results = []

            async def subscriber(name: str):
                async with b.subscribe("t1") as q:
                    evt = await asyncio.wait_for(q.get(), timeout=1.0)
                    results.append((name, evt["type"]))

            async def publisher():
                await asyncio.sleep(0.05)
                b._dispatch("t1", {"type": "ping"})

            await asyncio.gather(subscriber("s1"), subscriber("s2"), publisher())
            assert len(results) == 2
            assert all(e == "ping" for _, e in results)
        asyncio.run(run())

    def test_a4_events_are_dicts(self):
        async def run():
            b = SseBroker()
            async with b.subscribe("t1") as q:
                b._dispatch("t1", {"type": "task_created", "task_id": "T-99"})
                evt = await asyncio.wait_for(q.get(), timeout=1.0)
            assert isinstance(evt, dict)
            assert evt["task_id"] == "T-99"
        asyncio.run(run())

    def test_a5_subscriber_removed_after_context_exit(self):
        async def run():
            b = SseBroker()
            assert b.subscriber_count() == 0
            async with b.subscribe("t1"):
                assert b.subscriber_count() == 1
            assert b.subscriber_count() == 0
        asyncio.run(run())


# ---------------------------------------------------------------------------
# Group B — Broker: diagnostics
# ---------------------------------------------------------------------------

class TestGroupBDiagnostics:

    def test_b1_subscriber_count_all(self):
        async def run():
            b = SseBroker()
            assert b.subscriber_count() == 0
            async with b.subscribe("t1"):
                async with b.subscribe("t2"):
                    assert b.subscriber_count() == 2
            assert b.subscriber_count() == 0
        asyncio.run(run())

    def test_b2_subscriber_count_by_tenant(self):
        async def run():
            b = SseBroker()
            async with b.subscribe("t1"):
                async with b.subscribe("t1"):
                    async with b.subscribe("t2"):
                        assert b.subscriber_count("t1") == 2
                        assert b.subscriber_count("t2") == 1
        asyncio.run(run())

    def test_b3_zero_count_for_unknown_tenant(self):
        b = SseBroker()
        assert b.subscriber_count("nonexistent") == 0


# ---------------------------------------------------------------------------
# Group C — Broker: queue full guard
# ---------------------------------------------------------------------------

class TestGroupCQueueFull:

    def test_c1_full_queue_does_not_raise(self):
        """Publishing to a full queue must not raise — silently drops."""
        async def run():
            b = SseBroker()
            async with b.subscribe("t1") as q:
                for _ in range(q.maxsize):
                    q.put_nowait({"type": "fill"})
                b._dispatch("t1", {"type": "overflow"})
                assert q.qsize() == q.maxsize
        asyncio.run(run())

    def test_c2_queue_maxsize_is_1000(self):
        from channels.sse_broker import MAX_QUEUE_SIZE
        assert MAX_QUEUE_SIZE == 1_000


# ---------------------------------------------------------------------------
# Group D — _resolve_tenant (sse_router)
# ---------------------------------------------------------------------------

class TestGroupDResolveTenant:

    def test_d1_no_secret_returns_dev_tenant(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", "")
        assert _resolve_tenant("anything") == "dev-tenant"

    def test_d2_no_token_with_secret_returns_unknown(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", "a-very-long-secret-123456789")
        assert _resolve_tenant(None) == "unknown"

    def test_d3_invalid_token_returns_unknown(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", "a-very-long-secret-123456789")
        assert _resolve_tenant("not.a.jwt") == "unknown"

    def test_d4_valid_token_returns_sub(self, monkeypatch):
        import jwt as pyjwt
        import time
        secret = "a-very-long-secret-for-testing-12345"
        monkeypatch.setenv("IHOUSE_JWT_SECRET", secret)
        token = pyjwt.encode(
            {"sub": "tenant-xyz", "exp": int(time.time()) + 3600},
            secret, algorithm="HS256",
        )
        assert _resolve_tenant(token) == "tenant-xyz"

    def test_d5_no_secret_with_none_token_returns_dev_tenant(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_JWT_SECRET", "")
        assert _resolve_tenant(None) == "dev-tenant"


# ---------------------------------------------------------------------------
# Group E — Endpoint smoke test
# ---------------------------------------------------------------------------

class TestGroupEEndpoint:
    """
    SSE endpoint smoke tests.
    We use the OpenAPI schema to verify the endpoint is registered,
    rather than opening the stream directly (streaming responses hang in TestClient).
    """

    def test_e1_stream_endpoint_registered_in_openapi(self):
        """Verify /events/stream is registered in the app routes."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json().get("paths", {})
        assert "/events/stream" in paths, (
            f"/events/stream not found in OpenAPI paths: {list(paths.keys())[:10]}"
        )

    def test_e2_stream_endpoint_has_get_method(self):
        resp = client.get("/openapi.json")
        schema = resp.json()
        assert "get" in schema["paths"]["/events/stream"]

    def test_e3_stream_endpoint_has_events_tag(self):
        resp = client.get("/openapi.json")
        schema = resp.json()
        tags = schema["paths"]["/events/stream"]["get"].get("tags", [])
        assert "events" in tags

    def test_e4_sse_router_imported_cleanly(self):
        """Import sse_router with no errors."""
        from api.sse_router import router as _r  # noqa: F401
        assert _r is not None

    def test_e5_sse_broker_singleton_exists(self):
        from channels.sse_broker import broker as _b
        assert _b is not None
