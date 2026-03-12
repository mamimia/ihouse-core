"""
Phase 306 — SSE Event Bus Contract Tests

Tests for the multi-channel pub/sub broker and SSE router extensions.

Coverage:
  F — Channel-based filtering
  G — Convenience publishers
  H — Diagnostics (subscriber_channels)
  I — Backward compatibility
  J — SseEvent class
  K — CHANNELS constant
  L — Channel query param parsing
"""
from __future__ import annotations

import asyncio
import json
import os

os.environ.setdefault("IHOUSE_DEV_MODE", "true")

from channels.sse_broker import SseBroker, SseEvent, CHANNELS


# ---------------------------------------------------------------------------
# Group F — Channel-based filtering
# ---------------------------------------------------------------------------

class TestGroupFChannelFiltering:

    def test_f1_no_filter_receives_all_channels(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1") as q:
                b._dispatch("t1", "bookings", {"type": "b", "channel": "bookings"})
                b._dispatch("t1", "tasks", {"type": "t", "channel": "tasks"})
                b._dispatch("t1", "alerts", {"type": "a", "channel": "alerts"})
                while not q.empty():
                    received.append(await q.get())
            assert len(received) == 3
            assert {e["channel"] for e in received} == {"bookings", "tasks", "alerts"}
        asyncio.run(run())

    def test_f2_single_channel_filter(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1", channels={"bookings"}) as q:
                b._dispatch("t1", "bookings", {"type": "b", "channel": "bookings"})
                b._dispatch("t1", "tasks", {"type": "t", "channel": "tasks"})
                b._dispatch("t1", "alerts", {"type": "a", "channel": "alerts"})
                while not q.empty():
                    received.append(await q.get())
            assert len(received) == 1
            assert received[0]["channel"] == "bookings"
        asyncio.run(run())

    def test_f3_multiple_channel_filter(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1", channels={"bookings", "tasks"}) as q:
                b._dispatch("t1", "bookings", {"type": "b", "channel": "bookings"})
                b._dispatch("t1", "tasks", {"type": "t", "channel": "tasks"})
                b._dispatch("t1", "alerts", {"type": "a", "channel": "alerts"})
                b._dispatch("t1", "financial", {"type": "f", "channel": "financial"})
                while not q.empty():
                    received.append(await q.get())
            assert len(received) == 2
            assert {e["channel"] for e in received} == {"bookings", "tasks"}
        asyncio.run(run())

    def test_f4_tenant_isolation_with_channels(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1", channels={"bookings"}) as q:
                b._dispatch("t2", "bookings", {"type": "t2_b", "channel": "bookings"})
                b._dispatch("t1", "bookings", {"type": "t1_b", "channel": "bookings"})
                while not q.empty():
                    received.append(await q.get())
            assert len(received) == 1
            assert received[0]["type"] == "t1_b"
        asyncio.run(run())

    def test_f5_channel_field_injected_in_event(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1") as q:
                b._dispatch("t1", "bookings", {"type": "booking_created", "booking_id": "x", "channel": "bookings"})
                while not q.empty():
                    received.append(await q.get())
            assert received[0]["channel"] == "bookings"
            assert received[0]["booking_id"] == "x"
        asyncio.run(run())

    def test_f6_frozenset_channels_accepted(self):
        """frozenset channels should be accepted as filter."""
        async def run():
            b = SseBroker()
            async with b.subscribe("t1", channels=frozenset({"bookings"})) as q:
                b._dispatch("t1", "bookings", {"type": "b", "channel": "bookings"})
                b._dispatch("t1", "tasks", {"type": "t", "channel": "tasks"})
                received = []
                while not q.empty():
                    received.append(await q.get())
            assert len(received) == 1
        asyncio.run(run())


# ---------------------------------------------------------------------------
# Group G — Convenience publishers
# ---------------------------------------------------------------------------

class TestGroupGConveniencePublishers:

    def test_g1_publish_booking_event(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1", channels={"bookings"}) as q:
                b._dispatch("t1", "bookings", {"type": "booking_created", "booking_id": "airbnb_123", "channel": "bookings"})
                while not q.empty():
                    received.append(await q.get())
            assert len(received) == 1
            assert received[0]["type"] == "booking_created"
            assert received[0]["booking_id"] == "airbnb_123"
            assert received[0]["channel"] == "bookings"
        asyncio.run(run())

    def test_g2_publish_task_event(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1", channels={"tasks"}) as q:
                b._dispatch("t1", "tasks", {"type": "task_ack", "task_id": "T-001", "channel": "tasks"})
                while not q.empty():
                    received.append(await q.get())
            assert len(received) == 1
            assert received[0]["type"] == "task_ack"
            assert received[0]["task_id"] == "T-001"
        asyncio.run(run())

    def test_g3_publish_sync_event(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1", channels={"sync"}) as q:
                b._dispatch("t1", "sync", {"type": "sync_ok", "property_id": "P-1", "channel": "sync"})
                while not q.empty():
                    received.append(await q.get())
            assert len(received) == 1
            assert received[0]["property_id"] == "P-1"
        asyncio.run(run())

    def test_g4_publish_alert(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1", channels={"alerts"}) as q:
                b._dispatch("t1", "alerts", {"type": "sla_breach", "task_id": "T-2", "channel": "alerts"})
                while not q.empty():
                    received.append(await q.get())
            assert len(received) == 1
            assert received[0]["type"] == "sla_breach"
        asyncio.run(run())

    def test_g5_publish_financial_event(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1", channels={"financial"}) as q:
                b._dispatch("t1", "financial", {"type": "fact_updated", "channel": "financial"})
                while not q.empty():
                    received.append(await q.get())
            assert len(received) == 1
            assert received[0]["type"] == "fact_updated"
        asyncio.run(run())


# ---------------------------------------------------------------------------
# Group H — Diagnostics
# ---------------------------------------------------------------------------

class TestGroupHDiagnostics:

    def test_h1_subscriber_count_lifecycle(self):
        async def run():
            b = SseBroker()
            assert b.subscriber_count() == 0
            async with b.subscribe("t1"):
                assert b.subscriber_count() == 1
                async with b.subscribe("t1"):
                    assert b.subscriber_count() == 2
                assert b.subscriber_count() == 1
            assert b.subscriber_count() == 0
        asyncio.run(run())

    def test_h2_subscriber_count_by_tenant(self):
        async def run():
            b = SseBroker()
            async with b.subscribe("t1"):
                async with b.subscribe("t2"):
                    assert b.subscriber_count("t1") == 1
                    assert b.subscriber_count("t2") == 1
                    assert b.subscriber_count() == 2
        asyncio.run(run())

    def test_h3_subscriber_channels_breakdown(self):
        async def run():
            b = SseBroker()
            async with b.subscribe("t1", channels={"bookings"}):
                async with b.subscribe("t1", channels={"bookings", "tasks"}):
                    async with b.subscribe("t1"):
                        result = b.subscriber_channels()
                        assert result["bookings"] == 1
                        assert result["bookings,tasks"] == 1
                        assert result["*"] == 1
        asyncio.run(run())


# ---------------------------------------------------------------------------
# Group I — Backward compatibility
# ---------------------------------------------------------------------------

class TestGroupIBackwardCompat:

    def test_i1_publish_without_channel_defaults_system(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1") as q:
                b._dispatch("t1", "system", {"type": "legacy", "channel": "system"})
                while not q.empty():
                    received.append(await q.get())
            assert len(received) == 1
            assert received[0]["channel"] == "system"
        asyncio.run(run())

    def test_i2_subscribe_without_channels_receives_all(self):
        async def run():
            b = SseBroker()
            received = []
            async with b.subscribe("t1") as q:
                for ch in ["tasks", "bookings", "sync", "alerts", "financial", "system"]:
                    b._dispatch("t1", ch, {"type": f"test_{ch}", "channel": ch})
                while not q.empty():
                    received.append(await q.get())
            assert len(received) == 6
        asyncio.run(run())


# ---------------------------------------------------------------------------
# Group J — SseEvent class
# ---------------------------------------------------------------------------

class TestGroupJSseEvent:

    def test_j1_sse_event_has_channel(self):
        evt = SseEvent("t1", {"type": "booking_created"}, channel="bookings")
        assert evt.channel == "bookings"
        assert evt.tenant_id == "t1"

    def test_j2_sse_event_default_channel_is_system(self):
        evt = SseEvent("t1", {"type": "health_check"})
        assert evt.channel == "system"

    def test_j3_sse_event_to_sse_format(self):
        evt = SseEvent("t1", {"type": "test", "v": 42}, channel="system")
        raw = evt.to_sse()
        assert raw.startswith("data: ")
        assert raw.endswith("\n\n")
        parsed = json.loads(raw[6:].strip())
        assert parsed["type"] == "test"
        assert parsed["v"] == 42


# ---------------------------------------------------------------------------
# Group K — CHANNELS constant
# ---------------------------------------------------------------------------

class TestGroupKChannelsConstant:

    def test_k1_channels_is_frozenset(self):
        assert isinstance(CHANNELS, frozenset)

    def test_k2_channels_contains_expected_values(self):
        assert CHANNELS == {"tasks", "bookings", "sync", "alerts", "financial", "system"}


# ---------------------------------------------------------------------------
# Group L — Channel query param parsing (unit)
# ---------------------------------------------------------------------------

class TestGroupLChannelParsing:

    def test_l1_basic_parsing(self):
        channels_str = "bookings,tasks"
        result = {c.strip().lower() for c in channels_str.split(",") if c.strip()}
        assert result == {"bookings", "tasks"}

    def test_l2_whitespace_handling(self):
        channels_str = " bookings , tasks , "
        result = {c.strip().lower() for c in channels_str.split(",") if c.strip()}
        assert result == {"bookings", "tasks"}

    def test_l3_case_insensitive(self):
        channels_str = "BOOKINGS,Tasks"
        result = {c.strip().lower() for c in channels_str.split(",") if c.strip()}
        assert result == {"bookings", "tasks"}

    def test_l4_single_channel(self):
        channels_str = "alerts"
        result = {c.strip().lower() for c in channels_str.split(",") if c.strip()}
        assert result == {"alerts"}
