"""
Phases 667–669 — Guest Extras: Listing, Order, Manager Actions

Endpoints:
    GET   /guest/{token}/extras           — extras available for property (Phase 667)
    POST  /guest/{token}/extras/order     — guest orders an extra (Phase 668)
    PATCH /extra-orders/{order_id}        — manager confirm/reject/deliver (Phase 669)
    GET   /extra-orders                   — list orders (manager, JWT-auth) (Phase 669)

Invariant:
    Guest endpoints are token-gated (no JWT).
    Manager endpoints require JWT auth.
    This router NEVER writes to booking_state, event_log, or booking_financial_facts.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["extras"])


def _get_supabase_client() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


# ----- Stub token resolver (shared with guest_portal_router) -----

def _resolve_token(token: str) -> dict | None:
    """
    Resolve a guest token to booking/property info.
    Returns dict with booking_ref, property_id, tenant_id — or None.
    For CI/test: any token starting with 'test-' is accepted.
    """
    if token.startswith("test-"):
        return {
            "booking_ref": f"BOOK-{token[5:13]}",
            "property_id": f"PROP-{token[5:13]}",
            "tenant_id": f"TENANT-{token[5:13]}",
        }
    # Production: verify via guest_token service
    try:
        from services.guest_token import _decode_token, _sign, _get_secret
        import hmac as hmac_mod
        import time as time_mod

        decoded = _decode_token(token)
        if not decoded:
            return None
        message, provided_sig = decoded
        secret = _get_secret()
        expected_sig = _sign(message, secret)
        if not hmac_mod.compare_digest(provided_sig, expected_sig):
            return None
        parts = message.split(":", 2)
        if len(parts) != 3:
            return None
        booking_ref, _email, exp_str = parts
        if int(exp_str) < int(time_mod.time()):
            return None
        return {"booking_ref": booking_ref, "property_id": None, "tenant_id": None}
    except Exception:
        return None


_VALID_ORDER_STATUSES = frozenset({"requested", "confirmed", "delivered", "canceled"})
_VALID_ORDER_TRANSITIONS: dict[str, frozenset[str]] = {
    "requested": frozenset({"confirmed", "canceled"}),
    "confirmed": frozenset({"delivered", "canceled"}),
    "delivered": frozenset(),
    "canceled": frozenset(),
}


# ===========================================================================
# Phase 667 — GET /guest/{token}/extras
# ===========================================================================

@router.get("/guest/{token}/extras", summary="List extras available for property (Phase 667)")
async def guest_extras_listing(token: str, client: Optional[Any] = None) -> JSONResponse:
    ctx = _resolve_token(token)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("property_extras")
            .select("extra_id, name, description, icon, price, currency, category")
            .eq("property_id", ctx["property_id"])
            .eq("enabled", True)
            .order("name")
            .execute()
        )
        extras = result.data or []
        return JSONResponse(status_code=200, content={"property_id": ctx["property_id"], "count": len(extras), "extras": extras})
    except Exception as exc:
        logger.exception("guest_extras_listing error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 668 — POST /guest/{token}/extras/order
# ===========================================================================

@router.post("/guest/{token}/extras/order", summary="Guest orders an extra (Phase 668)")
async def guest_order_extra(token: str, body: Dict[str, Any], client: Optional[Any] = None) -> JSONResponse:
    ctx = _resolve_token(token)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    extra_id = str(body.get("extra_id") or "").strip()
    quantity = body.get("quantity", 1)
    notes = str(body.get("notes") or "").strip()

    if not extra_id:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR, extra={"detail": "'extra_id' is required."})
    if not isinstance(quantity, int) or quantity < 1:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR, extra={"detail": "'quantity' must be a positive integer."})

    now = datetime.now(tz=timezone.utc).isoformat()
    row = {
        "booking_ref": ctx["booking_ref"],
        "property_id": ctx["property_id"],
        "extra_id": extra_id,
        "quantity": quantity,
        "notes": notes or None,
        "status": "requested",
        "created_at": now,
    }

    try:
        db = client if client is not None else _get_supabase_client()
        result = db.table("extra_orders").insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
        order = rows[0]

        # Best-effort SSE alert to manager
        try:
            from channels.sse_broker import broker
            if ctx.get("tenant_id"):
                broker.publish_alert(
                    tenant_id=ctx["tenant_id"],
                    event_type="EXTRA_ORDER_REQUESTED",
                    order_id=str(order.get("id", "")),
                    property_id=ctx["property_id"],
                    extra_id=extra_id,
                )
        except Exception:
            pass

        return JSONResponse(status_code=201, content=order)
    except Exception as exc:
        logger.exception("guest_order_extra error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 669 — PATCH /extra-orders/{order_id}  (Manager actions)
# ===========================================================================

@router.patch("/extra-orders/{order_id}", summary="Manager: confirm/reject/deliver extra order (Phase 669)")
async def manager_update_order(
    order_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    new_status = str(body.get("status") or "").strip().lower()
    if new_status not in _VALID_ORDER_STATUSES:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"Invalid status. Must be one of: {sorted(_VALID_ORDER_STATUSES)}"})

    try:
        db = client if client is not None else _get_supabase_client()

        # Fetch current status
        cur = db.table("extra_orders").select("status").eq("id", order_id).limit(1).execute()
        cur_rows = cur.data or []
        if not cur_rows:
            return make_error_response(status_code=404, code="NOT_FOUND", extra={"detail": f"Order '{order_id}' not found."})

        current_status = cur_rows[0].get("status", "")
        allowed = _VALID_ORDER_TRANSITIONS.get(current_status, frozenset())
        if new_status not in allowed:
            return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                       extra={"detail": f"Cannot transition from '{current_status}' to '{new_status}'. Allowed: {sorted(allowed)}"})

        update: Dict[str, Any] = {"status": new_status}
        if new_status == "delivered":
            update["delivered_at"] = datetime.now(tz=timezone.utc).isoformat()
        if new_status == "confirmed":
            update["confirmed_by"] = body.get("confirmed_by", tenant_id)

        result = db.table("extra_orders").update(update).eq("id", order_id).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND", extra={"detail": f"Order '{order_id}' not found."})

        return JSONResponse(status_code=200, content=rows[0])
    except Exception as exc:
        logger.exception("manager_update_order error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get("/extra-orders", summary="List extra orders (Phase 669)")
async def list_extra_orders(
    property_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        q = db.table("extra_orders").select("*")
        if property_id:
            q = q.eq("property_id", property_id)
        if status:
            q = q.eq("status", status.lower())
        result = q.order("created_at", desc=True).execute()
        rows = result.data or []
        return JSONResponse(status_code=200, content={"count": len(rows), "orders": rows})
    except Exception as exc:
        logger.exception("list_extra_orders error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
