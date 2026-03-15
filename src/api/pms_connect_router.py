"""
Phases 808-811 — PMS Connect Router
=====================================

POST /integrations/pms/connect       — connect a PMS provider
GET  /integrations/pms/{id}/discover — list discovered properties
POST /integrations/pms/{id}/map      — map PMS property → Domaniqo property
POST /integrations/pms/{id}/sync     — trigger immediate sync
GET  /integrations/pms               — list PMS connections

All endpoints require JWT auth (admin or manager role).
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.envelope import ok, err

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_db() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _get_adapter(provider: str):
    """Return the correct PMS adapter for a provider."""
    if provider == "guesty":
        from adapters.pms.guesty import GuestyAdapter
        return GuestyAdapter()
    elif provider == "hostaway":
        from adapters.pms.hostaway import HostawayAdapter
        return HostawayAdapter()
    else:
        return None


# ---------------------------------------------------------------------------
# POST /integrations/pms/connect
# ---------------------------------------------------------------------------

@router.post(
    "/integrations/pms/connect",
    tags=["integrations", "pms"],
    summary="Connect a PMS / Channel Manager (Phase 808)",
)
async def connect_pms(
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Connect a PMS provider by validating credentials and creating a connection.

    Body:
      provider: "guesty" | "hostaway"
      credentials: { client_id, client_secret } (Guesty) or { api_key, account_id } (Hostaway)
      display_name: optional user-given name
    """
    provider = (body.get("provider") or "").lower().strip()
    credentials = body.get("credentials", {})
    display_name = body.get("display_name", "")

    if provider not in ("guesty", "hostaway"):
        return err("VALIDATION_ERROR", "provider must be 'guesty' or 'hostaway'", status=400)

    adapter = _get_adapter(provider)
    if not adapter:
        return err("PROVIDER_ERROR", f"Adapter not available for {provider}", status=400)

    # Validate credential format
    if not adapter.validate_credentials(credentials):
        return err("VALIDATION_ERROR", "Invalid credential format for this provider", status=400)

    # Authenticate with PMS
    auth_result = adapter.authenticate(credentials)
    if not auth_result.success:
        return err("AUTH_FAILED", f"PMS authentication failed: {auth_result.error}", status=401)

    # Create connection record
    db = client if client is not None else _get_db()
    conn_id = hashlib.sha256(
        f"{tenant_id}:{provider}:{time.time()}".encode()
    ).hexdigest()[:16]

    now = datetime.now(tz=timezone.utc)
    token_expires = None
    if auth_result.expires_in_seconds:
        token_expires = (now + timedelta(seconds=auth_result.expires_in_seconds)).isoformat()

    auth_method = "oauth2_client_credentials" if provider == "guesty" else "api_key"

    try:
        db.table("pms_connections").insert({
            "id": conn_id,
            "tenant_id": tenant_id,
            "provider": provider,
            "display_name": display_name or f"{provider.title()} Connection",
            "auth_method": auth_method,
            "credentials": credentials,
            "access_token": auth_result.access_token,
            "token_expires_at": token_expires,
            "status": "active",
        }).execute()
    except Exception as exc:
        logger.exception("PMS connect failed: %s", exc)
        return err("DB_ERROR", "Failed to save connection", status=500)

    # Auto-discover properties
    properties = []
    try:
        discovered = adapter.discover_properties(auth_result.access_token)
        properties = [
            {
                "external_id": p.external_id,
                "name": p.name,
                "city": p.city,
                "country": p.country,
                "bedrooms": p.bedrooms,
                "max_guests": p.max_guests,
            }
            for p in discovered
        ]
        # Update discovered count
        db.table("pms_connections").update({
            "properties_discovered": len(discovered),
            "updated_at": now.isoformat(),
        }).eq("id", conn_id).execute()
    except Exception as exc:
        logger.warning("PMS property discovery failed: %s", exc)

    return ok({
        "connection_id": conn_id,
        "provider": provider,
        "status": "active",
        "properties_discovered": len(properties),
        "properties": properties,
    })


# ---------------------------------------------------------------------------
# GET /integrations/pms/{connection_id}/discover
# ---------------------------------------------------------------------------

@router.get(
    "/integrations/pms/{connection_id}/discover",
    tags=["integrations", "pms"],
    summary="List discovered properties from PMS (Phase 809)",
)
async def discover_properties(
    connection_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """Fetch properties from PMS using stored credentials."""
    db = client if client is not None else _get_db()

    conn = (db.table("pms_connections")
            .select("*")
            .eq("id", connection_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute())

    if not conn.data:
        return err("NOT_FOUND", "PMS connection not found", status=404)

    row = conn.data[0]
    adapter = _get_adapter(row["provider"])
    if not adapter:
        return err("PROVIDER_ERROR", "Adapter not available", status=500)

    token = row.get("access_token")
    if not token:
        return err("AUTH_EXPIRED", "No valid access token — reconnect required", status=401)

    discovered = adapter.discover_properties(token)

    # Check which are already mapped
    mapped = (db.table("property_channel_map")
              .select("external_id")
              .eq("tenant_id", tenant_id)
              .eq("provider", row["provider"])
              .execute())
    mapped_ids = {r["external_id"] for r in (mapped.data or [])}

    properties = [
        {
            "external_id": p.external_id,
            "name": p.name,
            "city": p.city,
            "country": p.country,
            "bedrooms": p.bedrooms,
            "max_guests": p.max_guests,
            "already_mapped": p.external_id in mapped_ids,
        }
        for p in discovered
    ]

    return ok({
        "connection_id": connection_id,
        "provider": row["provider"],
        "count": len(properties),
        "properties": properties,
    })


# ---------------------------------------------------------------------------
# POST /integrations/pms/{connection_id}/map
# ---------------------------------------------------------------------------

@router.post(
    "/integrations/pms/{connection_id}/map",
    tags=["integrations", "pms"],
    summary="Map a PMS property to a Domaniqo property (Phase 809)",
)
async def map_property(
    connection_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Map a discovered PMS property to a Domaniqo property.

    Body:
      external_property_id: PMS property ID
      domaniqo_property_id: existing Domaniqo property_id (or "create_new")
      property_name: name if creating new
    """
    db = client if client is not None else _get_db()

    conn = (db.table("pms_connections")
            .select("provider, tenant_id")
            .eq("id", connection_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute())

    if not conn.data:
        return err("NOT_FOUND", "PMS connection not found", status=404)

    provider = conn.data[0]["provider"]
    ext_id = body.get("external_property_id", "")
    dom_id = body.get("domaniqo_property_id", "")

    if not ext_id:
        return err("VALIDATION_ERROR", "external_property_id required", status=400)

    # Create new Domaniqo property if requested
    if dom_id == "create_new":
        prop_name = body.get("property_name", f"PMS Property {ext_id[:8]}")
        dom_id = f"pms-{provider}-{ext_id[:12]}"
        try:
            db.table("properties").insert({
                "tenant_id": tenant_id,
                "property_id": dom_id,
                "display_name": prop_name,
                "source_platform": provider,
                "status": "approved",
            }).execute()
        except Exception as exc:
            logger.warning("Property create failed (may already exist): %s", exc)

    if not dom_id:
        return err("VALIDATION_ERROR", "domaniqo_property_id required", status=400)

    # Write to property_channel_map
    try:
        db.table("property_channel_map").upsert({
            "tenant_id": tenant_id,
            "property_id": dom_id,
            "provider": provider,
            "external_id": ext_id,
            "sync_mode": "api_first",
            "sync_strategy": "poll",
            "enabled": True,
        }, on_conflict="tenant_id,property_id,provider").execute()
    except Exception as exc:
        logger.exception("Property map failed: %s", exc)
        return err("DB_ERROR", "Failed to save mapping", status=500)

    return ok({
        "connection_id": connection_id,
        "provider": provider,
        "external_property_id": ext_id,
        "domaniqo_property_id": dom_id,
        "mapped": True,
    })


# ---------------------------------------------------------------------------
# POST /integrations/pms/{connection_id}/sync
# ---------------------------------------------------------------------------

@router.post(
    "/integrations/pms/{connection_id}/sync",
    tags=["integrations", "pms"],
    summary="Trigger immediate PMS booking sync (Phase 811)",
)
async def sync_bookings(
    connection_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Trigger an immediate booking sync for a PMS connection.
    Fetches all bookings, normalizes, writes to booking_state + event_log.
    """
    db = client if client is not None else _get_db()

    conn = (db.table("pms_connections")
            .select("*")
            .eq("id", connection_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute())

    if not conn.data:
        return err("NOT_FOUND", "PMS connection not found", status=404)

    row = conn.data[0]
    provider = row["provider"]
    adapter = _get_adapter(provider)

    if not adapter:
        return err("PROVIDER_ERROR", "Adapter not available", status=500)

    token = row.get("access_token")
    if not token:
        return err("AUTH_EXPIRED", "No valid access token", status=401)

    # Build property map: external_id → domaniqo property_id
    maps = (db.table("property_channel_map")
            .select("property_id, external_id")
            .eq("tenant_id", tenant_id)
            .eq("provider", provider)
            .eq("enabled", True)
            .execute())
    property_map = {r["external_id"]: r["property_id"] for r in (maps.data or [])}

    if not property_map:
        return err("NO_MAPPINGS", "No properties mapped for this connection. Use /discover and /map first.", status=400)

    # Fetch bookings from PMS
    since = row.get("last_sync_at")
    raw_bookings = adapter.fetch_bookings(token, since=since)

    # Normalize and write
    from adapters.pms.normalizer import normalize_pms_bookings
    sync_result = normalize_pms_bookings(
        bookings=raw_bookings,
        tenant_id=tenant_id,
        provider=provider,
        property_map=property_map,
        db=db,
    )

    # Update connection sync status
    now = datetime.now(tz=timezone.utc).isoformat()
    status = "ok" if sync_result.errors == 0 else "partial"
    db.table("pms_connections").update({
        "last_sync_at": now,
        "last_sync_status": status,
        "last_error": sync_result.error_details[0] if sync_result.error_details else None,
        "updated_at": now,
    }).eq("id", connection_id).execute()

    return ok({
        "connection_id": connection_id,
        "provider": provider,
        "sync_status": status,
        "bookings_fetched": sync_result.bookings_fetched,
        "bookings_new": sync_result.bookings_new,
        "bookings_updated": sync_result.bookings_updated,
        "bookings_canceled": sync_result.bookings_canceled,
        "errors": sync_result.errors,
    })


# ---------------------------------------------------------------------------
# GET /integrations/pms
# ---------------------------------------------------------------------------

@router.get(
    "/integrations/pms",
    tags=["integrations", "pms"],
    summary="List PMS connections (Phase 808)",
)
async def list_pms_connections(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """List all PMS connections for the authenticated tenant."""
    db = client if client is not None else _get_db()

    result = (db.table("pms_connections")
              .select("id, provider, display_name, status, last_sync_at, last_sync_status, properties_discovered, created_at")
              .eq("tenant_id", tenant_id)
              .order("created_at", desc=True)
              .execute())

    return ok({
        "count": len(result.data or []),
        "connections": result.data or [],
    })
