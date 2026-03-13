"""
Phase 536 — Email Sender Service
===================================

Configurable email delivery backend.
Supports SMTP and SendGrid (via env vars).
Falls back to logging when unconfigured.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

logger = logging.getLogger(__name__)


def _get_config() -> dict[str, str]:
    """Read email config from environment."""
    return {
        "provider": os.getenv("IHOUSE_EMAIL_PROVIDER", "log"),  # "smtp" | "sendgrid" | "log"
        "smtp_host": os.getenv("IHOUSE_SMTP_HOST", ""),
        "smtp_port": os.getenv("IHOUSE_SMTP_PORT", "587"),
        "smtp_user": os.getenv("IHOUSE_SMTP_USER", ""),
        "smtp_pass": os.getenv("IHOUSE_SMTP_PASS", ""),
        "from_email": os.getenv("IHOUSE_FROM_EMAIL", "noreply@domaniqo.com"),
        "from_name": os.getenv("IHOUSE_FROM_NAME", "Domaniqo"),
        "sendgrid_api_key": os.getenv("IHOUSE_SENDGRID_API_KEY", ""),
    }


def send_email(
    to: str,
    subject: str,
    body_html: str,
    body_text: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> dict:
    """
    Send an email using the configured provider.

    Args:
        to: Recipient email address
        subject: Email subject line
        body_html: HTML body content
        body_text: Optional plain-text fallback
        attachments: Optional list of {filename, content_bytes, mime_type}

    Returns:
        {"status": "sent" | "logged" | "error", "detail": ...}
    """
    config = _get_config()
    provider = config["provider"].lower()

    if provider == "smtp":
        return _send_smtp(to, subject, body_html, body_text, config)
    elif provider == "sendgrid":
        return _send_sendgrid(to, subject, body_html, body_text, config)
    else:
        # Fallback: just log it
        logger.info(
            "EMAIL (log mode): to=%s subject=%s body_len=%d",
            to, subject, len(body_html),
        )
        return {"status": "logged", "detail": "Email logged (no provider configured)"}


def _send_smtp(
    to: str, subject: str, body_html: str, body_text: str | None,
    config: dict,
) -> dict:
    """Send email via SMTP."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{config['from_name']} <{config['from_email']}>"
        msg["To"] = to

        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP(config["smtp_host"], int(config["smtp_port"])) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if config["smtp_user"]:
                server.login(config["smtp_user"], config["smtp_pass"])
            server.sendmail(config["from_email"], [to], msg.as_string())

        logger.info("EMAIL sent via SMTP to %s", to)
        return {"status": "sent", "detail": f"Sent via SMTP to {to}"}

    except Exception as exc:
        logger.error("EMAIL SMTP error: %s", exc)
        return {"status": "error", "detail": str(exc)}


def _send_sendgrid(
    to: str, subject: str, body_html: str, body_text: str | None,
    config: dict,
) -> dict:
    """Send email via SendGrid API."""
    try:
        import urllib.request

        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": config["from_email"], "name": config["from_name"]},
            "subject": subject,
            "content": [
                {"type": "text/html", "value": body_html},
            ],
        }
        if body_text:
            payload["content"].insert(0, {"type": "text/plain", "value": body_text})

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=data,
            headers={
                "Authorization": f"Bearer {config['sendgrid_api_key']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status

        logger.info("EMAIL sent via SendGrid to %s (status=%d)", to, status)
        return {"status": "sent", "detail": f"Sent via SendGrid (HTTP {status})"}

    except Exception as exc:
        logger.error("EMAIL SendGrid error: %s", exc)
        return {"status": "error", "detail": str(exc)}


def send_owner_statement_email(
    to: str,
    property_id: str,
    month: str,
    statement_html: str,
) -> dict:
    """Convenience wrapper for owner statement emails."""
    subject = f"Owner Statement — {property_id} — {month}"
    return send_email(
        to=to,
        subject=subject,
        body_html=statement_html,
        body_text=f"Owner statement for {property_id}, {month}. View in your browser for best experience.",
    )
