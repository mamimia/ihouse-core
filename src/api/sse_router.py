"""
Phase 181 — SSE Router

GET /events/stream — Server-Sent Events endpoint.

Contract:
  - Response: text/event-stream (persistent connection)
  - Auth: Bearer JWT (same as all other endpoints; dev-mode bypass if no secret)
  - Events: JSON payloads in data: {...}\n\n format
  - Keep-alive: :ping comment every 20 seconds
  - Tenant isolation: client only receives events for their tenant_id
  - Max duration: unlimited (connection held until client disconnects)
  - Disconnect: when client closes connection, FastAPI cancels the generator

Event format:
  data: {"type": "task_update", "task_id": "T-001", "status": "acknowledged"}\n\n
  data: {"type": "task_created", "task_id": "T-002"}\n\n
  :ping\n\n   (keep-alive comment, RFC 6202)

Frontend usage (EventSource):
  const es = new EventSource(`${API_BASE}/events/stream`, {
      headers: { Authorization: `Bearer ${token}` }
  });
  es.onmessage = (e) => { const evt = JSON.parse(e.data); ... };

Note: EventSource in browsers does not support custom headers.
  → The token should be passed as a query param: /events/stream?token=<jwt>
  → The endpoint reads token from query OR Authorization header.

  This is a known trade-off with browser EventSource. The token is NOT secret
  once in URL, but is short-lived (24h) and HTTPS-only in production.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import AsyncIterator

import jwt as pyjwt
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from channels.sse_broker import broker

logger = logging.getLogger(__name__)

router = APIRouter()

_PING_INTERVAL = 20  # seconds between keep-alive pings
_ALGORITHM = "HS256"
_DEV_TENANT = "dev-tenant"


def _resolve_tenant(token: str | None) -> str:
    """
    Resolve tenant_id from JWT token string.
    Returns 'dev-tenant' if IHOUSE_JWT_SECRET not set (dev mode).
    Returns 'unknown' on any parse failure in production.
    """
    secret = os.environ.get("IHOUSE_JWT_SECRET", "")
    if not secret:
        return _DEV_TENANT
    if not token:
        return "unknown"
    try:
        payload = pyjwt.decode(token, secret, algorithms=[_ALGORITHM])
        return str(payload.get("sub", "unknown")).strip() or "unknown"
    except pyjwt.InvalidTokenError:
        return "unknown"


async def _event_stream(tenant_id: str, request: Request) -> AsyncIterator[str]:
    """
    Async generator: yield SSE events for tenant_id until client disconnects.
    """
    async with broker.subscribe(tenant_id) as queue:
        logger.info("sse: client connected tenant=%s", tenant_id)
        try:
            while True:
                # Check if client has disconnected
                if await request.is_disconnected():
                    logger.info("sse: client disconnected tenant=%s", tenant_id)
                    break

                try:
                    # Wait for an event, with timeout for keep-alive ping
                    event = await asyncio.wait_for(queue.get(), timeout=_PING_INTERVAL)
                    event_data = event if isinstance(event, str) else json.dumps(event)
                    yield f"data: {event_data}\n\n"
                except asyncio.TimeoutError:
                    # Send RFC 6202 keep-alive comment
                    yield ":ping\n\n"

        except asyncio.CancelledError:
            logger.info("sse: stream cancelled tenant=%s", tenant_id)


@router.get(
    "/events/stream",
    tags=["events"],
    summary="Server-Sent Events live feed (Phase 181)",
    responses={
        200: {"description": "Persistent SSE stream", "content": {"text/event-stream": {}}},
    },
)
async def events_stream(
    request: Request,
    token: str | None = Query(default=None, description="JWT Bearer token (query param for EventSource)"),
) -> StreamingResponse:
    """
    Real-time Server-Sent Events stream for the authenticated tenant.

    **Connect:**
    ```
    GET /events/stream?token=<jwt>
    ```

    **Event types:**
    - `task_update` — status change on an existing task
    - `task_created` — new task assigned to this tenant
    - `ping` — keep-alive (sent every 20s of silence)

    **Event format:**
    ```
    data: {"type": "task_update", "task_id": "T-001", "status": "acknowledged"}
    ```

    Clients should reconnect on dropped connections (EventSource does this automatically).
    """
    # Resolve tenant from query param token (EventSource cannot set headers in browsers)
    # Fall back to Authorization header if no query param
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    tenant_id = _resolve_tenant(token)

    logger.info("sse: new stream tenant=%s", tenant_id)

    return StreamingResponse(
        _event_stream(tenant_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )
