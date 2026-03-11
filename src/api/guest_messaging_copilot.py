"""
Phase 227 — Guest Messaging Copilot v1

POST /ai/copilot/guest-message-draft

Generates a context-aware, polished draft message to send to a guest,
based on the booking, property, and guest profile data.

Use cases (controlled by `intent` field):
    check_in_instructions — check-in details, access codes, house rules
    booking_confirmation  — confirm the reservation + personalised welcome
    pre_arrival_info      — area tips, arrival preparation, weather note
    check_out_reminder    — check-out time, key return, feedback request
    issue_apology         — apologise for an issue + next steps
    custom               — free-form, user provides `custom_prompt`

Design (ai-strategy.md):
    - LLM composes the message (polished, personalised). Heuristic template fallback.
    - All context fetched deterministically from booking_state + booking_financial_facts
      + guest_profiles. No external calls. Reading only.
    - JWT required. Tenant isolation enforced at DB.
    - Response is a DRAFT — the calling system or manager decides whether to send it.
    - No write operations in this endpoint.

Request body:
    {
        "booking_id": "booking.com_RES123456",   // required
        "intent": "check_in_instructions",        // required, one of the 6 intents
        "language": "en",                          // optional, default en. 5 langs.
        "tone": "friendly",                        // optional: friendly|professional|brief
        "custom_prompt": "...",                    // required only when intent=custom
        "include_financial_summary": false         // optional, default false
    }

Response:
    {
        "tenant_id": "...",
        "booking_id": "...",
        "generated_by": "heuristic" | "llm",
        "intent": "check_in_instructions",
        "language": "en",
        "tone": "friendly",
        "draft": "Dear ..., ...",
        "subject": "Your stay at ...",   // email-ready subject line
        "character_count": 342,
        "context_used": {
            "property_name": "...",
            "guest_name": "...",
            "check_in": "2026-03-20",
            "check_out": "2026-03-25"
        },
        "generated_at": "..."
    }
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_INTENTS = {
    "check_in_instructions",
    "booking_confirmation",
    "pre_arrival_info",
    "check_out_reminder",
    "issue_apology",
    "custom",
}

_VALID_TONES = {"friendly", "professional", "brief"}
_DEFAULT_TONE = "friendly"
_DEFAULT_LANGUAGE = "en"
_SUPPORTED_LANGUAGES = {"en", "th", "ja", "es", "ko"}

_INTENT_LABELS = {
    "check_in_instructions": "Check-In Instructions",
    "booking_confirmation": "Booking Confirmation",
    "pre_arrival_info": "Pre-Arrival Information",
    "check_out_reminder": "Check-Out Reminder",
    "issue_apology": "Apology",
    "custom": "Message",
}

_SYSTEM_PROMPT = """\
You are a professional hospitality guest communication assistant for iHouse Core.
Your role: write polished, warm, and helpful messages to guests on behalf of the property manager.

Rules:
- Use the tone and language specified.
- Be concise but complete. Never overpromise.
- Do NOT include placeholders like [NAME] — use the actual data provided.
- Do NOT mention AI or automated systems.
- Respond with ONLY the message body text — no labels, no markdown, no email headers.
- Max 250 words.
"""


# ---------------------------------------------------------------------------
# Supabase helper
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Context fetcher
# ---------------------------------------------------------------------------

def _fetch_context(db: Any, tenant_id: str, booking_id: str) -> Dict:
    """
    Fetches booking + property + guest context for the messaging draft.
    Returns a dict with all relevant fields; empty/None for missing data.
    """
    ctx: Dict = {
        "booking_id": booking_id,
        "property_name": None,
        "property_address": None,
        "property_wifi": None,
        "property_checkin_time": None,
        "property_checkout_time": None,
        "property_access_code": None,
        "guest_name": None,
        "guest_email": None,
        "check_in": None,
        "check_out": None,
        "provider": None,
        "lifecycle_status": None,
        "total_nights": None,
    }

    # ---------- booking_state ----------
    try:
        result = (
            db.table("booking_state")
            .select("booking_id,provider,guest_name,guest_email,check_in,check_out,lifecycle_status,property_id,source_confidence")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_context booking_state: %s", exc)
        rows = []

    if not rows:
        return ctx

    booking = rows[0]
    ctx["provider"] = booking.get("provider")
    ctx["guest_name"] = booking.get("guest_name") or "Guest"
    ctx["guest_email"] = booking.get("guest_email")
    ctx["check_in"] = booking.get("check_in")
    ctx["check_out"] = booking.get("check_out")
    ctx["lifecycle_status"] = booking.get("lifecycle_status")
    property_id = booking.get("property_id")

    # Calculate total nights
    if ctx["check_in"] and ctx["check_out"]:
        try:
            ci = datetime.fromisoformat(ctx["check_in"])
            co = datetime.fromisoformat(ctx["check_out"])
            ctx["total_nights"] = max(0, (co - ci).days)
        except (ValueError, TypeError):
            pass

    # ---------- properties ----------
    if property_id:
        try:
            result = (
                db.table("properties")
                .select("property_id,name,address,wifi_password,checkin_time,checkout_time,access_code")
                .eq("tenant_id", tenant_id)
                .eq("property_id", property_id)
                .limit(1)
                .execute()
            )
            prop_rows = result.data or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("_fetch_context properties: %s", exc)
            prop_rows = []

        if prop_rows:
            p = prop_rows[0]
            ctx["property_name"] = p.get("name") or property_id
            ctx["property_address"] = p.get("address")
            ctx["property_wifi"] = p.get("wifi_password")
            ctx["property_checkin_time"] = p.get("checkin_time") or "15:00"
            ctx["property_checkout_time"] = p.get("checkout_time") or "11:00"
            ctx["property_access_code"] = p.get("access_code")

    return ctx


# ---------------------------------------------------------------------------
# Template engine (heuristic fallback)
# ---------------------------------------------------------------------------

_SALUTATIONS = {
    "en": "Dear {guest_name}",
    "th": "เรียน คุณ{guest_name}",
    "ja": "{guest_name}様",
    "es": "Estimado/a {guest_name}",
    "ko": "{guest_name}님",
}

_CLOSINGS = {
    "friendly": {
        "en": "Warm regards,\nYour Host",
        "th": "ขอบคุณครับ/ค่ะ\nทีมงานของเรา",
        "ja": "よろしくお願いします。\nホスト",
        "es": "Atentamente,\nSu Anfitrión",
        "ko": "감사합니다.\n호스트 드림",
    },
    "professional": {
        "en": "Kind regards,\nProperty Management",
        "th": "ขอบคุณ\nฝ่ายจัดการทรัพย์สิน",
        "ja": "敬具\n不動産管理部門",
        "es": "Respetuosamente,\nAdministración de Propiedades",
        "ko": "감사합니다.\n부동산 관리팀",
    },
    "brief": {
        "en": "Thanks,\nHost",
        "th": "ขอบคุณ\nโฮสต์",
        "ja": "よろしく。\nホスト",
        "es": "Gracias,\nAnfitrión",
        "ko": "감사합니다.\n호스트",
    },
}


def _build_heuristic_draft(
    intent: str,
    ctx: Dict,
    language: str,
    tone: str,
    custom_prompt: Optional[str],
) -> str:
    """Build a template-driven draft message for the given intent."""
    lang = language if language in _SUPPORTED_LANGUAGES else "en"
    tone = tone if tone in _VALID_TONES else _DEFAULT_TONE

    guest = ctx.get("guest_name") or "Guest"
    prop = ctx.get("property_name") or "our property"
    check_in = ctx.get("check_in") or "your check-in date"
    check_out = ctx.get("check_out") or "your check-out date"
    ci_time = ctx.get("property_checkin_time") or "15:00"
    co_time = ctx.get("property_checkout_time") or "11:00"
    wifi = ctx.get("property_wifi") or "(provided at property)"
    code = ctx.get("property_access_code") or "(provided separately)"
    nights = ctx.get("total_nights")
    nights_str = f"{nights} night{'s' if nights != 1 else ''}" if nights else "your stay"

    salutation = _SALUTATIONS.get(lang, _SALUTATIONS["en"]).format(guest_name=guest)
    closing = _CLOSINGS.get(tone, _CLOSINGS["friendly"]).get(lang, _CLOSINGS["friendly"]["en"])

    if intent == "check_in_instructions":
        body = (
            f"We are delighted to welcome you to {prop}!\n\n"
            f"Check-in is from {ci_time} on {check_in}.\n"
            f"Entry code: {code}\n"
            f"Wi-Fi password: {wifi}\n\n"
            f"Please do not hesitate to contact us if you need anything."
        )
    elif intent == "booking_confirmation":
        body = (
            f"Thank you for choosing {prop}. "
            f"Your booking for {nights_str} is confirmed.\n\n"
            f"Check-in: {check_in} from {ci_time}\n"
            f"Check-out: {check_out} by {co_time}\n\n"
            f"We look forward to hosting you!"
        )
    elif intent == "pre_arrival_info":
        body = (
            f"Your stay at {prop} is coming up on {check_in}!\n\n"
            f"Check-in begins at {ci_time}. We recommend arriving well-rested. "
            f"Please let us know your estimated arrival time and we will ensure everything is ready.\n\n"
            f"If you have any questions before your arrival, do not hesitate to reach out."
        )
    elif intent == "check_out_reminder":
        body = (
            f"We hope you have had a wonderful stay at {prop}!\n\n"
            f"A friendly reminder that check-out is by {co_time} on {check_out}. "
            f"Please leave the key at the designated spot upon departure.\n\n"
            f"We would love to hear your feedback — a short review means the world to us. "
            f"Thank you for staying with us!"
        )
    elif intent == "issue_apology":
        body = (
            f"We sincerely apologise for the inconvenience you have experienced during your stay at {prop}.\n\n"
            f"We take guest satisfaction very seriously and are working to resolve the matter immediately. "
            f"Please let us know how we can make this right for you.\n\n"
            f"Thank you for your patience and understanding."
        )
    elif intent == "custom":
        # Best-effort using the custom_prompt as the body hint
        body = custom_prompt or "Thank you for your message. We will be in touch shortly."
    else:
        body = "Thank you for your message. We will be in touch shortly."

    return f"{salutation},\n\n{body}\n\n{closing}"


def _build_subject(intent: str, ctx: Dict, language: str) -> str:
    """Generate an email-ready subject line."""
    prop = ctx.get("property_name") or "your stay"
    check_in = ctx.get("check_in") or ""
    subjects = {
        "check_in_instructions": f"Your Check-In Details for {prop}",
        "booking_confirmation": f"Booking Confirmed — {prop}",
        "pre_arrival_info": f"Preparing for Your Stay at {prop}" + (f" · {check_in}" if check_in else ""),
        "check_out_reminder": f"Check-Out Reminder — {prop}",
        "issue_apology": f"We Apologise — {prop}",
        "custom": f"Message from {prop}",
    }
    return subjects.get(intent, f"Message from {prop}")


# ---------------------------------------------------------------------------
# POST /ai/copilot/guest-message-draft
# ---------------------------------------------------------------------------

@router.post(
    "/ai/copilot/guest-message-draft",
    tags=["copilot"],
    summary="Guest Messaging Copilot — context-aware draft message (Phase 227)",
    description=(
        "Generates a polished draft message for a guest based on booking and property context.\\n\\n"
        "**Intents:** check_in_instructions · booking_confirmation · pre_arrival_info · "
        "check_out_reminder · issue_apology · custom\\n\\n"
        "**LLM path:** personalised, contextual prose. "
        "**Heuristic fallback:** deterministic template — always available.\\n\\n"
        "**Zero-risk:** Draft only — no messages sent. JWT required."
    ),
    responses={
        200: {"description": "Draft message generated"},
        400: {"description": "Invalid request body"},
        404: {"description": "Booking not found"},
        401: {"description": "Missing or invalid JWT"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def post_guest_message_draft(
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    # Validate required fields
    booking_id = (body.get("booking_id") or "").strip()
    if not booking_id:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "'booking_id' is required.")

    intent = (body.get("intent") or "").strip()
    if not intent:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "'intent' is required.")
    if intent not in _VALID_INTENTS:
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR,
            f"Invalid intent '{intent}'. Allowed: {', '.join(sorted(_VALID_INTENTS))}.",
        )

    if intent == "custom" and not body.get("custom_prompt"):
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR,
            "'custom_prompt' is required when intent is 'custom'.",
        )

    language = (body.get("language") or _DEFAULT_LANGUAGE).strip().lower()
    if language not in _SUPPORTED_LANGUAGES:
        language = _DEFAULT_LANGUAGE

    tone = (body.get("tone") or _DEFAULT_TONE).strip().lower()
    if tone not in _VALID_TONES:
        tone = _DEFAULT_TONE

    custom_prompt = (body.get("custom_prompt") or "").strip() or None

    try:
        db = client if client is not None else _get_db()
    except Exception as exc:  # noqa: BLE001
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, str(exc))

    # Fetch context
    ctx = _fetch_context(db, tenant_id, booking_id)

    # Verify booking exists
    if ctx.get("lifecycle_status") is None and ctx.get("check_in") is None:
        return make_error_response(404, ErrorCode.NOT_FOUND, f"Booking '{booking_id}' not found.")

    # Build heuristic draft first (always available)
    draft = _build_heuristic_draft(intent, ctx, language, tone, custom_prompt)
    subject = _build_subject(intent, ctx, language)
    generated_by = "heuristic"
    now = datetime.now(tz=timezone.utc)

    # LLM overlay attempt
    from services import llm_client
    if llm_client.is_configured():
        intent_label = _INTENT_LABELS.get(intent, intent.replace("_", " ").title())
        user_prompt_parts = [
            f"Booking ID: {booking_id}",
            f"Guest name: {ctx.get('guest_name') or 'Guest'}",
            f"Property: {ctx.get('property_name') or 'the property'}",
            f"Check-in: {ctx.get('check_in') or 'N/A'}",
            f"Check-out: {ctx.get('check_out') or 'N/A'}",
            f"Nights: {ctx.get('total_nights') or 'N/A'}",
        ]
        if ctx.get("property_checkin_time"):
            user_prompt_parts.append(f"Check-in time: {ctx['property_checkin_time']}")
        if ctx.get("property_checkout_time"):
            user_prompt_parts.append(f"Check-out time: {ctx['property_checkout_time']}")
        if ctx.get("property_access_code"):
            user_prompt_parts.append(f"Door access code: {ctx['property_access_code']}")
        if ctx.get("property_wifi"):
            user_prompt_parts.append(f"Wi-Fi password: {ctx['property_wifi']}")
        if custom_prompt:
            user_prompt_parts.append(f"Special instruction: {custom_prompt}")

        user_prompt = (
            "\n".join(user_prompt_parts)
            + f"\n\nPlease write a {tone} {intent_label.lower()} message in {language}."
        )

        llm_raw = llm_client.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
        if llm_raw and len(llm_raw) > 20:
            draft = llm_raw
            generated_by = "llm"

    return JSONResponse(
        status_code=200,
        content={
            "tenant_id": tenant_id,
            "booking_id": booking_id,
            "generated_by": generated_by,
            "intent": intent,
            "language": language,
            "tone": tone,
            "draft": draft,
            "subject": subject,
            "character_count": len(draft),
            "context_used": {
                "property_name": ctx.get("property_name"),
                "guest_name": ctx.get("guest_name"),
                "check_in": ctx.get("check_in"),
                "check_out": ctx.get("check_out"),
                "total_nights": ctx.get("total_nights"),
            },
            "generated_at": now.isoformat(),
        },
    )
