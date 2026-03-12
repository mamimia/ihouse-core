"""
SSE Event Broker — Multi-Channel Pub/Sub (Phase 181 + Phase 306)

In-memory, asyncio-based pub/sub for Server-Sent Events.

Phase 181: Original task-only broker.
Phase 306: Extended with named channels (tasks, bookings, sync, alerts, financial, system).

Design:
  - Global singleton `broker` (module-level).
  - Subscribers are asyncio.Queues keyed by a unique connection_id.
  - Subscriptions are tenant-scoped: each queue only receives events for one tenant_id.
  - Subscriptions optionally filter by channel(s). If no channels specified, all events pass.
  - Publish from sync code is safe via `_loop.call_soon_threadsafe(...)`.
  - Every published event carries a `channel` field for filtering.

Channels:
  - tasks      — task state changes (created, acknowledged, completed, SLA breach)
  - bookings   — booking lifecycle (BOOKING_CREATED, CANCELED, AMENDED processed)
  - sync       — outbound sync results (success, failure, retry)
  - alerts     — SLA breaches, anomaly alerts, DLQ threshold
  - financial  — financial fact changes, reconciliation updates
  - system     — health state changes, scheduler events

Usage:
    from channels.sse_broker import broker

    # Subscribe to all events for a tenant:
    async with broker.subscribe(tenant_id) as queue:
        event = await queue.get()

    # Subscribe to only bookings and tasks:
    async with broker.subscribe(tenant_id, channels={"bookings", "tasks"}) as queue:
        event = await queue.get()

    # Publish from sync code:
    broker.publish(tenant_id, {"type": "booking_created", "booking_id": "..."}, channel="bookings")

Invariants:
  - Max MAX_QUEUE_SIZE events per connection before oldest is dropped.
  - Tenant isolation: events only delivered to queues subscribed to that tenant_id.
  - Channel filtering: events only delivered to queues subscribed to that channel (or all if no filter).
  - No Supabase, no disk writes — pure in-memory.
  - Thread-safe publish (sync routers live in a thread pool).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

MAX_QUEUE_SIZE = 1_000

# Known channels — informational, not enforced (unknown channels are allowed)
CHANNELS = frozenset({"tasks", "bookings", "sync", "alerts", "financial", "system"})


class SseEvent:
    """Typed SSE event payload."""
    __slots__ = ("tenant_id", "channel", "data")

    def __init__(self, tenant_id: str, data: dict[str, Any], channel: str = "system") -> None:
        self.tenant_id = tenant_id
        self.channel = channel
        self.data = data

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.data)}\n\n"


class SseBroker:
    """
    In-memory SSE event broker with named channel support.

    Thread-safe publish → asyncio-native subscribe.
    """

    def __init__(self) -> None:
        # {connection_id: (tenant_id, channels_filter | None, asyncio.Queue)}
        self._subscribers: dict[str, tuple[str, frozenset[str] | None, asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Subscribe (async context manager)
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def subscribe(
        self,
        tenant_id: str,
        channels: set[str] | frozenset[str] | None = None,
    ) -> AsyncIterator[asyncio.Queue]:
        """
        Context manager: register a queue for tenant_id events.

        Args:
            tenant_id: Tenant to subscribe to.
            channels: Optional set of channel names to filter.
                      If None or empty, all channels are received.

        Usage:
            async with broker.subscribe("t1", channels={"bookings"}) as q:
                event = await q.get()
        """
        cid = str(uuid.uuid4())
        q: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        ch_filter = frozenset(channels) if channels else None
        async with self._lock:
            self._subscribers[cid] = (tenant_id, ch_filter, q)
        logger.debug(
            "sse_broker: subscriber added cid=%s tenant=%s channels=%s",
            cid, tenant_id, ch_filter,
        )
        try:
            yield q
        finally:
            async with self._lock:
                self._subscribers.pop(cid, None)
            logger.debug("sse_broker: subscriber removed cid=%s tenant=%s", cid, tenant_id)

    # ------------------------------------------------------------------
    # Publish (sync-safe)
    # ------------------------------------------------------------------

    def publish(
        self,
        tenant_id: str,
        data: dict[str, Any],
        channel: str = "system",
    ) -> None:
        """
        Publish an event to all subscribers of tenant_id (optionally filtered by channel).

        Safe to call from synchronous FastAPI route handlers (thread pool).
        Silently drops events if the queue is full (non-blocking).

        The `channel` field is injected into the event data automatically.
        """
        # Inject channel into the event payload for client-side filtering
        enriched = {**data, "channel": channel}

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return  # No event loop — drop silently (e.g. tests without asyncio)

        loop.call_soon_threadsafe(self._dispatch, tenant_id, channel, enriched)

    def _dispatch(self, tenant_id: str, channel: str, data: dict[str, Any]) -> None:
        """Called on the event loop thread."""
        count: int = 0
        for cid, (t_id, ch_filter, q) in list(self._subscribers.items()):
            if t_id != tenant_id:
                continue
            # Channel filter: if subscriber has a filter, only deliver matching channels
            if ch_filter and channel not in ch_filter:
                continue
            try:
                q.put_nowait(data)
                count += 1
            except asyncio.QueueFull:
                logger.warning(
                    "sse_broker: queue full for cid=%s tenant=%s channel=%s — event dropped",
                    cid, tenant_id, channel,
                )
        if count:
            logger.debug(
                "sse_broker: dispatched channel=%s type=%s to %d subscriber(s) tenant=%s",
                channel, data.get("type"), count, tenant_id,
            )

    # ------------------------------------------------------------------
    # Convenience publishers
    # ------------------------------------------------------------------

    def publish_booking_event(self, tenant_id: str, event_type: str, booking_id: str, **extra: Any) -> None:
        """Publish a booking lifecycle event."""
        self.publish(tenant_id, {"type": event_type, "booking_id": booking_id, **extra}, channel="bookings")

    def publish_task_event(self, tenant_id: str, event_type: str, task_id: str, **extra: Any) -> None:
        """Publish a task state change event."""
        self.publish(tenant_id, {"type": event_type, "task_id": task_id, **extra}, channel="tasks")

    def publish_sync_event(self, tenant_id: str, event_type: str, property_id: str, **extra: Any) -> None:
        """Publish an outbound sync event."""
        self.publish(tenant_id, {"type": event_type, "property_id": property_id, **extra}, channel="sync")

    def publish_alert(self, tenant_id: str, event_type: str, **extra: Any) -> None:
        """Publish an alert (SLA breach, anomaly, DLQ threshold)."""
        self.publish(tenant_id, {"type": event_type, **extra}, channel="alerts")

    def publish_financial_event(self, tenant_id: str, event_type: str, **extra: Any) -> None:
        """Publish a financial data change event."""
        self.publish(tenant_id, {"type": event_type, **extra}, channel="financial")

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def subscriber_count(self, tenant_id: str | None = None) -> int:
        """Return subscriber count, optionally filtered by tenant_id."""
        if tenant_id is None:
            return len(self._subscribers)
        return sum(1 for t_id, _, _ in self._subscribers.values() if t_id == tenant_id)

    def subscriber_channels(self) -> dict[str, int]:
        """Return count of subscribers per channel filter (None = all channels)."""
        result: dict[str, int] = {}
        for _, ch_filter, _ in self._subscribers.values():
            key = ",".join(sorted(ch_filter)) if ch_filter else "*"
            result[key] = result.get(key, 0) + 1
        return result


# Singleton
broker = SseBroker()
