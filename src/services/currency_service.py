"""
Phase 501 — Multi-Currency Real Exchange Rates

Fetches real exchange rates from a public API and caches them
in Supabase. Provides currency conversion utilities for the
financial system.

Supports THB, USD, EUR, GBP, JPY, AUD, and other major currencies.
Falls back to hardcoded rates when API is unavailable.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("ihouse.currency")

_EXCHANGE_API_URL = "https://api.exchangerate-api.com/v4/latest/{base}"

# Fallback rates (THB-based, approximate)
FALLBACK_RATES: Dict[str, float] = {
    "THB": 1.0,
    "USD": 0.028,
    "EUR": 0.026,
    "GBP": 0.023,
    "JPY": 4.35,
    "AUD": 0.044,
    "SGD": 0.039,
    "CNY": 0.205,
}


def _get_db():
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def fetch_live_rates(base: str = "THB") -> Dict[str, float]:
    """
    Fetch live exchange rates from an API.
    Returns rates dict {currency: rate_from_base}.
    Falls back to hardcoded rates on error.
    """
    try:
        import requests
        response = requests.get(
            _EXCHANGE_API_URL.format(base=base),
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("rates", FALLBACK_RATES)
    except Exception as exc:
        logger.warning("fetch_live_rates failed: %s", exc)

    return FALLBACK_RATES


def update_cached_rates(
    *,
    base: str = "THB",
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Fetch live rates and cache in Supabase exchange_rates table.
    """
    if db is None:
        db = _get_db()

    rates = fetch_live_rates(base)
    now = datetime.now(timezone.utc).isoformat()

    cached = 0
    for currency, rate in rates.items():
        try:
            db.table("exchange_rates").upsert(
                {
                    "base_currency": base,
                    "target_currency": currency,
                    "rate": rate,
                    "fetched_at": now,
                },
                on_conflict="base_currency,target_currency",
            ).execute()
            cached += 1
        except Exception as exc:
            logger.warning("cache rate %s/%s failed: %s", base, currency, exc)

    return {
        "base": base,
        "currencies_cached": cached,
        "fetched_at": now,
        "source": "live" if cached > len(FALLBACK_RATES) else "fallback",
    }


def convert(
    amount: float,
    from_currency: str,
    to_currency: str,
    rates: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Convert an amount between currencies.

    Uses provided rates or fallback.
    """
    if from_currency == to_currency:
        return {"amount": amount, "currency": to_currency, "rate": 1.0}

    if rates is None:
        rates = FALLBACK_RATES

    # Convert via THB as base
    from_rate = rates.get(from_currency, 1.0)
    to_rate = rates.get(to_currency, 1.0)

    if from_rate == 0:
        return {"error": f"No rate for {from_currency}"}

    # amount_in_base = amount / from_rate  (if rates are from THB)
    # amount_in_target = amount_in_base * to_rate
    converted = amount * to_rate / from_rate
    rate = to_rate / from_rate

    return {
        "original_amount": amount,
        "original_currency": from_currency,
        "converted_amount": round(converted, 2),
        "target_currency": to_currency,
        "rate": round(rate, 6),
    }
