"""
Phase 223 — LLM Client (Provider-Agnostic Wrapper)

Thin abstraction over the OpenAI completions API.
Designed to be swappable — configure via env vars.

Environment variables:
    OPENAI_API_KEY          — OpenAI API key. Required for live calls.
    IHOUSE_LLM_PROVIDER     — 'openai' (default). Future: 'google', 'anthropic'
    IHOUSE_LLM_MODEL        — Default: 'gpt-4o-mini' (cheapest capable model)
    IHOUSE_LLM_MAX_TOKENS   — Max response tokens (default: 600)
    IHOUSE_LLM_TEMPERATURE  — Sampling temperature (default: 0.3, low = consistent)
    IHOUSE_LLM_TIMEOUT_S    — Request timeout in seconds (default: 30)

Fallback:
    If OPENAI_API_KEY is not set, `generate()` returns None.
    Callers should implement graceful degradation (e.g. static briefing).

Design:
    - Synchronous (not async) to keep the interface simple and testable.
      FastAPI endpoint wraps it in `run_in_executor` if needed.
    - Never raises — returns None on error.
    - All errors logged at WARNING.
    - Does not buffer or cache responses — stateless per call.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _str_env(key: str, default: str) -> str:
    return os.environ.get(key, default).strip() or default


def _int_env(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def _float_env(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(
    system_prompt: str,
    user_prompt: str,
    *,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> Optional[str]:
    """
    Send a chat completion request and return the response text.

    Returns None if:
      - OPENAI_API_KEY is not set (unconfigured deployment)
      - Any API/network error occurs
      - The provider is unsupported

    Never raises.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.info("llm_client.generate: OPENAI_API_KEY not set — returning None")
        return None

    provider = _str_env("IHOUSE_LLM_PROVIDER", "openai").lower()
    if provider != "openai":
        logger.warning("llm_client.generate: Provider '%s' not supported — returning None", provider)
        return None

    resolved_model = model or _str_env("IHOUSE_LLM_MODEL", "gpt-4o-mini")
    resolved_max_tokens = max_tokens or _int_env("IHOUSE_LLM_MAX_TOKENS", 600)
    resolved_temperature = temperature if temperature is not None else _float_env("IHOUSE_LLM_TEMPERATURE", 0.3)
    timeout_s = _int_env("IHOUSE_LLM_TIMEOUT_S", 30)

    try:
        import openai  # type: ignore[import]

        client = openai.OpenAI(api_key=api_key, timeout=float(timeout_s))
        response = client.chat.completions.create(
            model=resolved_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=resolved_max_tokens,
            temperature=resolved_temperature,
        )
        text = response.choices[0].message.content or ""
        logger.info(
            "llm_client.generate: OK model=%s tokens_used=%s",
            resolved_model,
            response.usage.total_tokens if response.usage else "?",
        )
        return text.strip()

    except Exception as exc:  # noqa: BLE001
        logger.warning("llm_client.generate: Error — %s", exc)
        return None


def is_configured() -> bool:
    """Returns True if a valid API key is set for the configured provider."""
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())
