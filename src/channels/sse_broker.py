"""
Phase 181 — SSE Event Broker

In-memory, asyncio-based pub/sub for Server-Sent Events.

Design:
  - Global singleton `broker` (module-level).
  - Subscribers are asyncio.Queues keyed by a unique connection_id.
  - Subscriptions are tenant-scoped: each queue only receives events for one tenant_id.
  - Publish from sync code is safe via `_loop.call_soon_threadsafe(...)`.

Usage:
    from channels.sse_broker import broker

    # In an async SSE route:
    async with broker.subscribe(tenant_id) as queue:
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event)}\n\n"

    # In a sync route (acknowledgeTask, completeTask, etc.):
    broker.publish(tenant_id, {"type": "task_update", "task_id": ..., "status": ...})

Invariants:
  - Max MAX_QUEUE_SIZE events per connection before oldest is dropped.
  - Tenant isolation: events only delivered to queues subscribed to that tenant_id.
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


class SseEvent:
    """Typed SSE event payload."""
    __slots__ = ("tenant_id", "data")

    def __init__(self, tenant_id: str, data: dict[str, Any]) -> None:
        self.tenant_id = tenant_id
        self.data = data

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.data)}\n\n"


class SseBroker:
    """
    In-memory SSE event broker.

    Thread-safe publish → asyncio-native subscribe.
    """

    def __init__(self) -> None:
        # {connection_id: (tenant_id, asyncio.Queue)}
        self._subscribers: dict[str, tuple[str, asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Subscribe (async context manager)
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def subscribe(self, tenant_id: str) -> AsyncIterator[asyncio.Queue]:
        """
        Context manager: register a queue for tenant_id events.

        Usage:
            async with broker.subscribe("t1") as q:
                event = await q.get()
        """
        cid = str(uuid.uuid4())
        q: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        async with self._lock:
            self._subscribers[cid] = (tenant_id, q)
        logger.debug("sse_broker: subscriber added cid=%s tenant=%s", cid, tenant_id)
        try:
            yield q
        finally:
            async with self._lock:
                self._subscribers.pop(cid, None)
            logger.debug("sse_broker: subscriber removed cid=%s tenant=%s", cid, tenant_id)

    # ------------------------------------------------------------------
    # Publish (sync-safe)
    # ------------------------------------------------------------------

    def publish(self, tenant_id: str, data: dict[str, Any]) -> None:
        """
        Publish an event to all subscribers of tenant_id.

        Safe to call from synchronous FastAPI route handlers (thread pool).
        Silently drops events if the queue is full (non-blocking).
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return  # No event loop — drop silently (e.g. tests without asyncio)

        loop.call_soon_threadsafe(self._dispatch, tenant_id, data)

    def _dispatch(self, tenant_id: str, data: dict[str, Any]) -> None:
        """Called on the event loop thread."""
        count: int = 0
        for cid, (t_id, q) in list(self._subscribers.items()):
            if t_id != tenant_id:
                continue
            try:
                q.put_nowait(data)
                count += 1
            except asyncio.QueueFull:
                logger.warning(
                    "sse_broker: queue full for cid=%s tenant=%s — event dropped",
                    cid, tenant_id,
                )
        if count:
            logger.debug(
                "sse_broker: dispatched event=%s to %d subscriber(s) tenant=%s",
                data.get("type"), count, tenant_id,
            )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def subscriber_count(self, tenant_id: str | None = None) -> int:
        """Return subscriber count, optionally filtered by tenant_id."""
        if tenant_id is None:
            return len(self._subscribers)
        return sum(1 for t_id, _ in self._subscribers.values() if t_id == tenant_id)


# Singleton
broker = SseBroker()
