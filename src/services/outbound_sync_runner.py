"""
Phase 492 — Outbound Sync Real Execution Runner

Orchestrates real outbound sync: reads pending sync_jobs from outbound_sync_log,
dispatches them via the provider adapter (Airbnb, Booking.com, etc.),
and updates status.

Currently outbound_sync_log = 0 rows. This runner scans booking_state
for recent modifications and creates sync jobs + executes them.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ihouse.outbound_sync_runner")


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _dispatch_sync(
    provider: str,
    action: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Dispatch a sync action to a provider.

    In dry-run / no-credentials mode, returns a dry_run result.
    When real credentials are configured, calls the provider API.
    """
    # Check if provider credentials are set
    cred_key = f"IHOUSE_{provider.upper()}_API_KEY"
    has_creds = bool(os.environ.get(cred_key, ""))

    if not has_creds:
        return {
            "status": "dry_run",
            "provider": provider,
            "action": action,
            "message": f"No credentials for {provider} ({cred_key} not set)",
        }

    # Real dispatch would go here per-provider
    # For now, all providers use the same pattern
    try:
        # Import provider-specific adapter
        adapter_module = f"adapters.outbound.{provider}_adapter"
        import importlib
        adapter = importlib.import_module(adapter_module)
        result = adapter.execute_sync(action, payload)
        return {"status": "sent", "provider": provider, "action": action, **result}
    except ImportError:
        return {
            "status": "dry_run",
            "provider": provider,
            "action": action,
            "message": f"Adapter module {adapter_module} not found",
        }
    except Exception as exc:
        return {
            "status": "failed",
            "provider": provider,
            "action": action,
            "error": str(exc),
        }


def run_outbound_sync(
    *,
    tenant_id: Optional[str] = None,
    dry_run: bool = False,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Scan for bookings needing outbound sync and execute dispatch.

    This checks booking_state for bookings modified since their last sync
    and creates sync jobs in outbound_sync_log.

    Args:
        tenant_id: Optional tenant filter.
        dry_run: If True, detect pending syncs without dispatching.
        limit: Max bookings to process.

    Returns:
        Summary dict.
    """
    db = _get_db()

    # Get bookings with channel_property_map entries (mapped to OTAs)
    query = db.table("channel_property_map").select(
        "property_id, channel, external_property_id"
    )
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    map_result = query.execute()
    channel_maps = map_result.data or []

    # Get recent booking modifications
    booking_query = db.table("booking_state").select(
        "booking_id, property_id, tenant_id, status, provider, check_in, check_out"
    ).limit(limit).order("updated_at", desc=True)
    if tenant_id:
        booking_query = booking_query.eq("tenant_id", tenant_id)
    bookings_result = booking_query.execute()
    bookings = bookings_result.data or []

    # Get already-synced booking IDs
    synced_query = db.table("outbound_sync_log").select("booking_id, status")
    if tenant_id:
        synced_query = synced_query.eq("tenant_id", tenant_id)
    synced_result = synced_query.execute()
    synced_bookings = {
        r["booking_id"] for r in (synced_result.data or [])
        if r.get("status") == "sent"
    }

    # Build property → channels map
    prop_channels: Dict[str, List[Dict]] = {}
    for m in channel_maps:
        pid = m.get("property_id", "")
        if pid:
            prop_channels.setdefault(pid, []).append(m)

    stats = {
        "total_bookings": len(bookings),
        "channel_mappings": len(channel_maps),
        "pending_sync": 0,
        "dispatched": 0,
        "dry_run_count": 0,
        "already_synced": 0,
        "no_channel_map": 0,
        "errors": 0,
        "dry_run": dry_run,
    }

    now = datetime.now(timezone.utc).isoformat()

    for booking in bookings:
        bid = booking.get("booking_id", "")
        pid = booking.get("property_id", "")
        b_tenant = booking.get("tenant_id", tenant_id or "")

        if bid in synced_bookings:
            stats["already_synced"] += 1
            continue

        channels = prop_channels.get(pid, [])
        if not channels:
            stats["no_channel_map"] += 1
            continue

        stats["pending_sync"] += 1

        for channel in channels:
            provider = channel.get("channel", "")
            ext_id = channel.get("external_property_id", "")

            sync_payload = {
                "booking_id": bid,
                "property_id": pid,
                "external_property_id": ext_id,
                "check_in": booking.get("check_in"),
                "check_out": booking.get("check_out"),
                "status": booking.get("status"),
            }

            if dry_run:
                stats["dry_run_count"] += 1
                continue

            # Dispatch sync
            result = _dispatch_sync(provider, "booking_update", sync_payload)

            # Log to outbound_sync_log
            try:
                db.table("outbound_sync_log").insert({
                    "tenant_id": b_tenant,
                    "booking_id": bid,
                    "property_id": pid,
                    "channel": provider,
                    "action": "booking_update",
                    "status": result.get("status", "unknown"),
                    "payload_json": sync_payload,
                    "dispatched_at": now,
                }).execute()

                if result["status"] == "sent":
                    stats["dispatched"] += 1
                elif result["status"] == "dry_run":
                    stats["dry_run_count"] += 1
                else:
                    stats["errors"] += 1
            except Exception as exc:
                logger.warning("outbound_sync_log insert error: %s", exc)
                stats["errors"] += 1

    logger.info("Outbound sync complete: %s", stats)
    return stats
