"""
Phase 490 — Guest Token Batch Issuance

Generates guest portal access tokens for all bookings that have
a guest profile (email/phone) but no existing token in guest_tokens.

This fills the gap: 1516 bookings, 0 guest_tokens.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("ihouse.guest_token_batch")


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def batch_issue_tokens(
    *,
    tenant_id: Optional[str] = None,
    dry_run: bool = False,
    ttl_seconds: int = 7 * 24 * 3600,
) -> Dict[str, Any]:
    """
    Issue guest tokens for bookings with guest profiles but no token.

    Args:
        tenant_id: Optional tenant filter.
        dry_run: If True, count eligible bookings without issuing.
        ttl_seconds: Token lifetime (default 7 days).

    Returns:
        Summary dict.
    """
    db = _get_db()

    # Get all guest profiles with email
    query = db.table("guest_profile").select(
        "booking_id, tenant_id, guest_email, guest_phone, guest_name"
    )
    if tenant_id:
        query = query.eq("tenant_id", tenant_id)
    profiles_result = query.execute()
    profiles = profiles_result.data or []

    # Get existing tokens
    token_query = db.table("guest_tokens").select("booking_ref")
    if tenant_id:
        token_query = token_query.eq("tenant_id", tenant_id)
    tokens_result = token_query.execute()
    existing_refs = {r["booking_ref"] for r in (tokens_result.data or [])}

    stats = {
        "total_profiles": len(profiles),
        "already_have_token": 0,
        "no_email": 0,
        "issued": 0,
        "notified": 0,
        "errors": 0,
        "dry_run": dry_run,
    }

    from services.guest_token import issue_guest_token, record_guest_token

    for profile in profiles:
        bid = profile.get("booking_id", "")
        email = profile.get("guest_email", "")
        p_tenant = profile.get("tenant_id", tenant_id or "")

        if bid in existing_refs:
            stats["already_have_token"] += 1
            continue

        if not email:
            stats["no_email"] += 1
            continue

        if dry_run:
            stats["issued"] += 1
            continue

        try:
            raw_token, exp = issue_guest_token(
                booking_ref=bid,
                guest_email=email,
                ttl_seconds=ttl_seconds,
            )

            record_guest_token(
                db=db,
                booking_ref=bid,
                tenant_id=p_tenant,
                raw_token=raw_token,
                exp=exp,
                guest_email=email,
            )
            stats["issued"] += 1

            # Best-effort: dispatch notification with portal link
            try:
                from services.notification_dispatcher import dispatch_guest_token_notification
                portal_base = os.environ.get("IHOUSE_PORTAL_BASE_URL", "https://app.domaniqo.com")
                dispatch_guest_token_notification(
                    db=db,
                    tenant_id=p_tenant,
                    booking_ref=bid,
                    raw_token=raw_token,
                    portal_base_url=portal_base,
                    to_email=email,
                    to_phone=profile.get("guest_phone"),
                    guest_name=profile.get("guest_name", "Guest"),
                )
                stats["notified"] += 1
            except Exception as notify_exc:
                logger.warning("Token notification failed for %s: %s", bid, notify_exc)

        except Exception as exc:
            logger.warning("Token issuance failed for %s: %s", bid, exc)
            stats["errors"] += 1

    logger.info("Batch token issuance complete: %s", stats)
    return stats
