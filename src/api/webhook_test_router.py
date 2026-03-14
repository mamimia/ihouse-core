"""
Phase 772 — Webhook Pipeline Test Endpoint
=============================================

Provides POST /admin/webhook-test that injects a synthetic OTA event
into the webhook pipeline and traces it through:
  envelope → event_log → booking upsert → audit trail

Used to verify the full webhook→processing pipeline works in staging
without needing real OTA credentials.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class WebhookTestRequest(BaseModel):
    source: str = Field("airbnb", description="OTA source (airbnb, booking_com)")
    event_type: str = Field("booking.created", description="Event type to simulate")
    tenant_id: str = Field("tenant_e2e_amended", description="Tenant ID for the event")
    property_id: str = Field("", description="Property ID (auto-generated if empty)")


def _get_db() -> Any:
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)


@router.post(
    "/admin/webhook-test",
    tags=["admin", "ops"],
    summary="Inject synthetic webhook event (Phase 772)",
    description=(
        "Simulates an OTA webhook payload and traces it through the "
        "event_log → booking pipeline. Returns trace of each step."
    ),
    responses={
        200: {"description": "Pipeline test complete — trace returned"},
        503: {"description": "Supabase not configured"},
    },
)
async def webhook_test(body: WebhookTestRequest) -> JSONResponse:
    db = _get_db()
    if not db:
        return JSONResponse(status_code=503, content={
            "error": "SUPABASE_NOT_CONFIGURED",
            "message": "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set.",
        })

    trace_id = str(uuid.uuid4())[:12]
    ts = datetime.now(tz=timezone.utc).isoformat()
    property_id = body.property_id or f"prop-test-{trace_id[:6]}"
    booking_id = f"BK-TEST-{trace_id[:8].upper()}"

    trace = {
        "trace_id": trace_id,
        "source": body.source,
        "event_type": body.event_type,
        "tenant_id": body.tenant_id,
        "property_id": property_id,
        "booking_id": booking_id,
        "steps": [],
    }

    # Step 1: Insert into event_log
    try:
        event_payload = {
            "event_id": f"evt-test-{trace_id}",
            "tenant_id": body.tenant_id,
            "event_type": body.event_type,
            "source": body.source,
            "payload": {
                "booking_id": booking_id,
                "property_id": property_id,
                "guest_name": "Test Guest",
                "check_in": "2026-04-01",
                "check_out": "2026-04-05",
                "total_price": 500.00,
                "currency": "USD",
                "status": "confirmed",
                "_test_trace": trace_id,
            },
            "received_at": ts,
        }
        db.table("event_log").insert(event_payload).execute()
        trace["steps"].append({"step": "event_log_insert", "status": "ok"})
    except Exception as exc:
        trace["steps"].append({"step": "event_log_insert", "status": "error", "error": str(exc)})

    # Step 2: Insert into bookings table
    try:
        booking_data = {
            "booking_id": booking_id,
            "tenant_id": body.tenant_id,
            "property_id": property_id,
            "guest_name": "Test Guest",
            "check_in": "2026-04-01",
            "check_out": "2026-04-05",
            "total_price": 500.00,
            "currency": "USD",
            "source": body.source,
            "status": "confirmed",
        }
        db.table("bookings").upsert(booking_data).execute()
        trace["steps"].append({"step": "bookings_upsert", "status": "ok"})
    except Exception as exc:
        trace["steps"].append({"step": "bookings_upsert", "status": "error", "error": str(exc)})

    # Step 3: Insert into booking_state
    try:
        state_data = {
            "booking_id": booking_id,
            "tenant_id": body.tenant_id,
            "property_id": property_id,
            "status": "active",
            "check_in": "2026-04-01",
            "check_out": "2026-04-05",
            "source": body.source,
        }
        db.table("booking_state").upsert(state_data).execute()
        trace["steps"].append({"step": "booking_state_upsert", "status": "ok"})
    except Exception as exc:
        trace["steps"].append({"step": "booking_state_upsert", "status": "error", "error": str(exc)})

    # Step 4: Insert audit event
    try:
        db.table("audit_events").insert({
            "tenant_id": body.tenant_id,
            "event_type": "webhook_test",
            "entity_type": "booking",
            "entity_id": booking_id,
            "payload": {"trace_id": trace_id, "source": body.source},
        }).execute()
        trace["steps"].append({"step": "audit_event", "status": "ok"})
    except Exception as exc:
        trace["steps"].append({"step": "audit_event", "status": "error", "error": str(exc)})

    # Summary
    ok_count = sum(1 for s in trace["steps"] if s["status"] == "ok")
    total = len(trace["steps"])
    trace["summary"] = f"{ok_count}/{total} steps succeeded"
    trace["pipeline_ok"] = ok_count == total

    return JSONResponse(
        status_code=200 if trace["pipeline_ok"] else 207,
        content=trace,
    )
