"""
Notification Dispatcher — Phase 299
======================================

Outbound notification service for SMS (Twilio) and Email (SendGrid).
All dispatches are logged to the `notification_log` table.

Design philosophy:
    - Dispatch is BEST-EFFORT: failures are logged, never raised.
    - Dry-run mode when env vars absent (logs 'dry_run' status — no real send).
    - Every dispatch creates a notification_log row (pending → sent | failed | dry_run).
    - Never stores message body — only a 200-char preview for PII safety.
    - tenant_id (JWT sub) is always recorded as the issuing operator.

Providers:
    SMS:   Twilio — IHOUSE_TWILIO_SID + IHOUSE_TWILIO_TOKEN + IHOUSE_TWILIO_FROM
    Email: SendGrid — IHOUSE_SENDGRID_KEY + IHOUSE_SENDGRID_FROM

Env vars:
    IHOUSE_TWILIO_SID        — Twilio Account SID
    IHOUSE_TWILIO_TOKEN      — Twilio Auth Token
    IHOUSE_TWILIO_FROM       — Sending phone number (E.164)
    IHOUSE_SENDGRID_KEY      — SendGrid API key
    IHOUSE_SENDGRID_FROM     — Sending email address

Tables:
    notification_log — all dispatch history

Invariant:
    tenant_id (JWT sub) never changes — operator is always identified.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

try:
    from twilio.rest import Client  # type: ignore[import]
except ImportError:
    Client = None  # type: ignore[assignment,misc]

try:
    import sendgrid  # type: ignore[import]
    from sendgrid.helpers.mail import Mail  # type: ignore[import]
except ImportError:
    sendgrid = None  # type: ignore[assignment]
    Mail = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

_BODY_PREVIEW_MAX = 200


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _preview(body: str) -> str:
    """Return first _BODY_PREVIEW_MAX chars of body."""
    return body[:_BODY_PREVIEW_MAX] if body else ""


def _log_notification(
    db: Any,
    tenant_id: str,
    channel: str,
    recipient: str,
    notification_type: str,
    body_preview: str,
    subject: str | None = None,
    reference_id: str | None = None,
    status: str = "pending",
    provider_id: str | None = None,
    error_message: str | None = None,
) -> dict:
    """Insert a row into notification_log. Returns the row or {} on error."""
    payload: dict[str, Any] = {
        "tenant_id": tenant_id,
        "channel": channel,
        "recipient": recipient,
        "notification_type": notification_type,
        "body_preview": body_preview,
        "status": status,
    }
    if subject:
        payload["subject"] = subject
    if reference_id:
        payload["reference_id"] = reference_id
    if provider_id:
        payload["provider_id"] = provider_id
    if error_message:
        payload["error_message"] = error_message
    if status in ("sent", "dry_run"):
        payload["sent_at"] = _now_iso()

    try:
        res = db.table("notification_log").insert(payload).execute()
        return res.data[0] if res.data else {}
    except Exception as exc:
        logger.exception("notification_log insert failed: %s", exc)
        return {}


def _update_log_status(
    db: Any,
    notification_id: str,
    status: str,
    provider_id: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update an existing notification_log row after dispatch attempt."""
    update: dict[str, Any] = {"status": status}
    if status in ("sent", "dry_run"):
        update["sent_at"] = _now_iso()
    if provider_id:
        update["provider_id"] = provider_id
    if error_message:
        update["error_message"] = error_message
    try:
        db.table("notification_log").update(update).eq("notification_id", notification_id).execute()
    except Exception as exc:
        logger.warning("_update_log_status failed: %s", exc)


# ---------------------------------------------------------------------------
# SMS dispatch (Twilio)
# ---------------------------------------------------------------------------

def dispatch_sms(
    db: Any,
    tenant_id: str,
    to_number: str,
    body: str,
    notification_type: str = "generic",
    reference_id: str | None = None,
) -> dict:
    """
    Send an SMS via Twilio and log the dispatch.

    Returns:
        dict with notification_id, status ('sent' | 'failed' | 'dry_run'),
        and provider_id (Twilio SID) if sent.

    Args:
        db:                Supabase client (service role).
        tenant_id:         Operator's JWT sub.
        to_number:         Recipient phone in E.164 format (+66xxxxxxxxx).
        body:              SMS body text.
        notification_type: 'guest_token' | 'task_alert' | 'booking_confirm' | 'generic'
        reference_id:      booking_ref, task_id, token_id etc.

    DRY-RUN:
        If IHOUSE_TWILIO_SID / IHOUSE_TWILIO_TOKEN / IHOUSE_TWILIO_FROM are not set,
        logs status='dry_run' and returns without sending.
    """
    twilio_sid = os.environ.get("IHOUSE_TWILIO_SID", "")
    twilio_token = os.environ.get("IHOUSE_TWILIO_TOKEN", "")
    twilio_from = os.environ.get("IHOUSE_TWILIO_FROM", "")

    log_row = _log_notification(
        db=db,
        tenant_id=tenant_id,
        channel="sms",
        recipient=to_number,
        notification_type=notification_type,
        body_preview=_preview(body),
        reference_id=reference_id,
        status="pending",
    )
    notification_id = log_row.get("notification_id")

    if not all([twilio_sid, twilio_token, twilio_from]):
        logger.info(
            "dispatch_sms: dry_run (Twilio env vars not configured). to=%s type=%s",
            to_number, notification_type,
        )
        if notification_id:
            _update_log_status(db, notification_id, "dry_run")
        return {
            "notification_id": notification_id,
            "status": "dry_run",
            "channel": "sms",
            "recipient": to_number,
        }

    # Real Twilio dispatch
    provider_id = None
    try:
        if Client is None:
            raise RuntimeError("twilio package not installed")
        client = Client(twilio_sid, twilio_token)
        message = client.messages.create(
            body=body,
            from_=twilio_from,
            to=to_number,
        )
        provider_id = message.sid
        logger.info(
            "dispatch_sms: sent. to=%s sid=%s type=%s",
            to_number, provider_id, notification_type,
        )
        if notification_id:
            _update_log_status(db, notification_id, "sent", provider_id=provider_id)
        return {
            "notification_id": notification_id,
            "status": "sent",
            "channel": "sms",
            "recipient": to_number,
            "provider_id": provider_id,
        }
    except Exception as exc:
        err = str(exc)
        logger.warning("dispatch_sms: failed to=%s error=%s", to_number, err)
        if notification_id:
            _update_log_status(db, notification_id, "failed", error_message=err[:500])
        return {
            "notification_id": notification_id,
            "status": "failed",
            "channel": "sms",
            "recipient": to_number,
            "error": err,
        }


# ---------------------------------------------------------------------------
# Email dispatch (SendGrid)
# ---------------------------------------------------------------------------

def dispatch_email(
    db: Any,
    tenant_id: str,
    to_email: str,
    subject: str,
    body_html: str,
    notification_type: str = "generic",
    reference_id: str | None = None,
) -> dict:
    """
    Send an email via SendGrid and log the dispatch.

    Returns:
        dict with notification_id, status ('sent' | 'failed' | 'dry_run'),
        and provider_id if sent.

    Args:
        db:                Supabase client (service role).
        tenant_id:         Operator's JWT sub.
        to_email:          Recipient email address.
        subject:           Email subject line.
        body_html:         HTML body of the email.
        notification_type: 'guest_token' | 'task_alert' | 'booking_confirm' | 'generic'
        reference_id:      booking_ref, task_id, token_id etc.

    DRY-RUN:
        If IHOUSE_SENDGRID_KEY / IHOUSE_SENDGRID_FROM are not set,
        logs status='dry_run' and returns without sending.
    """
    sendgrid_key = os.environ.get("IHOUSE_SENDGRID_KEY", "")
    sendgrid_from = os.environ.get("IHOUSE_SENDGRID_FROM", "")

    log_row = _log_notification(
        db=db,
        tenant_id=tenant_id,
        channel="email",
        recipient=to_email,
        notification_type=notification_type,
        body_preview=_preview(body_html),
        subject=subject,
        reference_id=reference_id,
        status="pending",
    )
    notification_id = log_row.get("notification_id")

    if not all([sendgrid_key, sendgrid_from]):
        logger.info(
            "dispatch_email: dry_run (SendGrid env vars not configured). to=%s type=%s",
            to_email, notification_type,
        )
        if notification_id:
            _update_log_status(db, notification_id, "dry_run")
        return {
            "notification_id": notification_id,
            "status": "dry_run",
            "channel": "email",
            "recipient": to_email,
        }

    # Real SendGrid dispatch
    provider_id = None
    try:
        if sendgrid is None:
            raise RuntimeError("sendgrid package not installed")

        sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
        mail = Mail(
            from_email=sendgrid_from,
            to_emails=to_email,
            subject=subject,
            html_content=body_html,
        )
        response = sg.send(mail)
        provider_id = response.headers.get("X-Message-Id", "")
        logger.info(
            "dispatch_email: sent. to=%s type=%s provider_id=%s",
            to_email, notification_type, provider_id,
        )
        if notification_id:
            _update_log_status(db, notification_id, "sent", provider_id=provider_id)
        return {
            "notification_id": notification_id,
            "status": "sent",
            "channel": "email",
            "recipient": to_email,
            "provider_id": provider_id,
        }
    except Exception as exc:
        err = str(exc)
        logger.warning("dispatch_email: failed to=%s error=%s", to_email, err)
        if notification_id:
            _update_log_status(db, notification_id, "failed", error_message=err[:500])
        return {
            "notification_id": notification_id,
            "status": "failed",
            "channel": "email",
            "recipient": to_email,
            "error": err,
        }


# ---------------------------------------------------------------------------
# Compound: send guest token by SMS or email
# ---------------------------------------------------------------------------

def dispatch_guest_token_notification(
    db: Any,
    tenant_id: str,
    booking_ref: str,
    raw_token: str,
    portal_base_url: str,
    to_phone: str | None = None,
    to_email: str | None = None,
    guest_name: str = "Guest",
) -> list[dict]:
    """
    Send a guest portal access link via SMS and/or email.

    Constructs the portal URL:
        {portal_base_url}/guest/{booking_ref}?token={raw_token}

    At least one of to_phone or to_email must be provided.

    Returns:
        List of dispatch result dicts (one per channel used).
    """
    if not to_phone and not to_email:
        raise ValueError("At least one of to_phone or to_email must be provided.")

    portal_url = f"{portal_base_url.rstrip('/')}/guest/{booking_ref}?token={raw_token}"
    results = []

    if to_phone:
        sms_body = (
            f"Hi {guest_name}! Access your booking details for {booking_ref} here:\n"
            f"{portal_url}\n"
            f"Link valid for 7 days. - Domaniqo"
        )
        result = dispatch_sms(
            db=db,
            tenant_id=tenant_id,
            to_number=to_phone,
            body=sms_body,
            notification_type="guest_token",
            reference_id=booking_ref,
        )
        results.append(result)

    if to_email:
        subject = f"Your booking details — {booking_ref}"
        body_html = f"""
<html><body>
<h2>Hi {guest_name},</h2>
<p>Your booking <strong>{booking_ref}</strong> is confirmed! Access all your details below:</p>
<p><a href="{portal_url}" style="background:#1a1a2e;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;display:inline-block;">
  View Booking Details
</a></p>
<p style="color:#888;font-size:12px;">This link is valid for 7 days. If you didn't make this booking, please ignore this email.</p>
<p>— Domaniqo</p>
</body></html>
"""
        result = dispatch_email(
            db=db,
            tenant_id=tenant_id,
            to_email=to_email,
            subject=subject,
            body_html=body_html,
            notification_type="guest_token",
            reference_id=booking_ref,
        )
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Notification log queries
# ---------------------------------------------------------------------------

def list_notification_log(
    db: Any,
    tenant_id: str,
    limit: int = 50,
    reference_id: str | None = None,
) -> list[dict]:
    """
    Return notification_log entries for a tenant, newest first.
    Optionally filtered by reference_id (booking_ref, task_id etc).
    """
    try:
        q = (
            db.table("notification_log")
            .select(
                "notification_id, channel, recipient, notification_type, "
                "reference_id, status, provider_id, sent_at, created_at"
            )
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if reference_id:
            q = q.eq("reference_id", reference_id)
        res = q.execute()
        return res.data or []
    except Exception as exc:
        logger.exception("list_notification_log error: %s", exc)
        return []
