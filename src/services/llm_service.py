"""
Phase 498 — Real LLM Integration Service

Provides a unified interface for LLM calls used by copilots:
- Guest Messaging Copilot (draft messages)
- Operational Copilot (suggest resolutions)

Supports OpenAI and falls back to template-based responses
when API key is not configured (dry-run mode).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ihouse.llm_service")

_OPENAI_KEY_ENV = "IHOUSE_OPENAI_API_KEY"
_DEFAULT_MODEL = "gpt-4o-mini"


def _has_openai_key() -> bool:
    return bool(os.environ.get(_OPENAI_KEY_ENV, ""))


def _call_openai(
    messages: List[Dict[str, str]],
    model: str = _DEFAULT_MODEL,
    max_tokens: int = 500,
    temperature: float = 0.7,
) -> Dict[str, Any]:
    """
    Call OpenAI Chat Completions API.

    Returns:
        Response dict with content and usage.
    """
    try:
        import openai
        client = openai.OpenAI(api_key=os.environ[_OPENAI_KEY_ENV])
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return {
            "status": "ok",
            "content": response.choices[0].message.content,
            "model": model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            },
        }
    except Exception as exc:
        logger.warning("OpenAI call failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def generate_guest_message(
    intent: str,
    context: Dict[str, Any],
    language: str = "en",
) -> Dict[str, Any]:
    """
    Generate a guest-facing message using LLM or template fallback.

    Args:
        intent: Message type (check_in_instructions, welcome, pre_arrival, etc.)
        context: Booking/property context dict.
        language: Target language code.

    Returns:
        Dict with generated message text.
    """
    property_name = context.get("property_name", "your property")
    guest_name = context.get("guest_name", "Guest")
    check_in = context.get("check_in", "")
    check_out = context.get("check_out", "")

    if _has_openai_key():
        system = (
            f"You are a professional hospitality assistant for {property_name}. "
            f"Write a {intent.replace('_', ' ')} message for a guest. "
            f"Be warm, professional, and concise. Language: {language}."
        )
        user_msg = (
            f"Guest: {guest_name}\n"
            f"Check-in: {check_in}\n"
            f"Check-out: {check_out}\n"
            f"Property: {property_name}\n"
            f"Intent: {intent}"
        )
        result = _call_openai([
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ])
        if result["status"] == "ok":
            return {
                "message": result["content"],
                "source": "llm",
                "model": result.get("model", _DEFAULT_MODEL),
            }

    # Template fallback
    templates = {
        "check_in_instructions": (
            f"Hi {guest_name}! Welcome to {property_name}. "
            f"Your check-in is on {check_in}. Please arrive after 15:00. "
            f"We look forward to hosting you!"
        ),
        "welcome": (
            f"Welcome to {property_name}, {guest_name}! "
            f"We hope you enjoy your stay from {check_in} to {check_out}. "
            f"Don't hesitate to reach out if you need anything."
        ),
        "pre_arrival_info": (
            f"Hi {guest_name}, your stay at {property_name} is coming up on {check_in}. "
            f"Here's what you need to know..."
        ),
        "checkout_reminder": (
            f"Hi {guest_name}, your checkout from {property_name} is on {check_out}. "
            f"Please check out by 11:00. Thank you for staying with us!"
        ),
    }

    template = templates.get(intent, f"Message for {guest_name} regarding {intent}")

    return {
        "message": template,
        "source": "template",
        "model": None,
    }


def generate_operational_suggestion(
    issue_type: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate an operational suggestion for property managers.

    Args:
        issue_type: 'conflict_resolution' | 'maintenance_priority' | 'staffing'
        context: Issue context dict.

    Returns:
        Dict with suggestion text.
    """
    if _has_openai_key():
        system = (
            "You are an experienced property management operations assistant. "
            "Provide concise, actionable suggestions."
        )
        user_msg = f"Issue type: {issue_type}\nContext: {context}"
        result = _call_openai([
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ], max_tokens=300)
        if result["status"] == "ok":
            return {
                "suggestion": result["content"],
                "source": "llm",
            }

    # Fallback suggestions
    fallbacks = {
        "conflict_resolution": "Contact both guests immediately. Offer relocation or date change to the later booking.",
        "maintenance_priority": "Address safety issues first, then guest-impacting items, then cosmetic issues.",
        "staffing": "Schedule additional cleaning staff for peak turnover days (Friday-Sunday).",
    }

    return {
        "suggestion": fallbacks.get(issue_type, f"Review the {issue_type} and take appropriate action."),
        "source": "template",
    }
