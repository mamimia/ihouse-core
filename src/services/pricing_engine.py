"""
Phase 251 — Dynamic Pricing Suggestion Engine

Pure-function service that computes suggested nightly rates for a property
for the next N days (default 30), based on:

    1. Base rate from rate_cards table (Phase 246)
    2. Seasonality multiplier  — high/low season
    3. Occupancy pressure       — higher neighbour occupancy → higher price
    4. Lead-time discount       — short-notice bookings get a discount

No ML, no external APIs. Fully deterministic and testable offline.

---

Factors and multipliers
-----------------------

Seasonality (SEASONALITY_MULTIPLIER):
    high  (Nov–Mar):  +20%   → ×1.20
    low   (Apr–Oct):  -10%   → ×0.90

Occupancy pressure (OCCUPANCY_MULTIPLIER):
    ≥80%  full booked:  +25%  → ×1.25
    60–79%:             +10%  → ×1.10
    40–59%:              0%   → ×1.00
    <40%  low demand:  -10%  → ×0.90

Lead-time discount (LEAD_TIME_MULTIPLIER):
    0–2 days out (flash deal):         -15%  → ×0.85
    3–6 days out (last minute):        -10%  → ×0.90
    7–13 days out (short booking):      0%   → ×1.00
    ≥14 days out (advance):             +5%  → ×1.05

Final price:
    suggested = base_rate × seasonality × occupancy × lead_time
    Rounded to nearest 100 (for clean display in THB).

Invariants:
    - No DB reads inside this module — caller passes base_rate and occupancy
    - Returns a list of PriceSuggestion objects (one per day)
    - Never raises — returns zero suggestions if base_rate is invalid
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

# ---------------------------------------------------------------------------
# Multiplier tables
# ---------------------------------------------------------------------------

_HIGH_SEASON_MONTHS = {11, 12, 1, 2, 3}  # Nov–Mar


def _seasonality_multiplier(d: date) -> float:
    return 1.20 if d.month in _HIGH_SEASON_MONTHS else 0.90


def _occupancy_multiplier(occupancy_pct: Optional[float]) -> float:
    if occupancy_pct is None:
        return 1.00
    if occupancy_pct >= 80:
        return 1.25
    if occupancy_pct >= 60:
        return 1.10
    if occupancy_pct >= 40:
        return 1.00
    return 0.90


def _lead_time_multiplier(days_out: int) -> float:
    if days_out <= 2:
        return 0.85
    if days_out <= 6:
        return 0.90
    if days_out <= 13:
        return 1.00
    return 1.05


def _season_label(d: date) -> str:
    return "high" if d.month in _HIGH_SEASON_MONTHS else "low"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PriceSuggestion:
    """One day's pricing suggestion."""
    date: str             # ISO date "YYYY-MM-DD"
    day_of_week: str      # "Mon", "Tue", etc.
    season: str           # "high" or "low"
    base_rate: float
    occupancy_pct: Optional[float]
    seasonality_mult: float
    occupancy_mult: float
    lead_time_mult: float
    suggested_rate: float  # Rounded to nearest 100
    currency: str


# ---------------------------------------------------------------------------
# Main engine function
# ---------------------------------------------------------------------------

def suggest_prices(
    base_rate: float,
    currency: str = "THB",
    occupancy_pct: Optional[float] = None,
    days: int = 30,
    from_date: Optional[date] = None,
) -> List[PriceSuggestion]:
    """
    Compute suggested nightly rates for the next `days` calendar days.

    Args:
        base_rate:      Base nightly rate (from rate card). Must be > 0.
        currency:       ISO currency code. Default "THB".
        occupancy_pct:  Current overall property occupancy (0–100).
                        If None, occupancy pressure is neutral (×1.00).
        days:           Number of days to project. Default 30. Max 90.
        from_date:      Starting date. Default today (UTC).

    Returns:
        List of PriceSuggestion, one per day, sorted ascending by date.
        Empty list if base_rate <= 0 or days <= 0.
    """
    if base_rate <= 0 or days <= 0:
        return []

    days = min(days, 90)
    start = from_date or date.today()
    today = date.today()

    suggestions: List[PriceSuggestion] = []
    occ_mult = _occupancy_multiplier(occupancy_pct)

    for i in range(days):
        d = start + timedelta(days=i)
        days_out = max(0, (d - today).days)

        s_mult = _seasonality_multiplier(d)
        lt_mult = _lead_time_multiplier(days_out)

        raw = base_rate * s_mult * occ_mult * lt_mult
        # Round to nearest 100 for clean display
        suggested = round(raw / 100) * 100

        suggestions.append(
            PriceSuggestion(
                date=d.isoformat(),
                day_of_week=d.strftime("%a"),
                season=_season_label(d),
                base_rate=base_rate,
                occupancy_pct=occupancy_pct,
                seasonality_mult=s_mult,
                occupancy_mult=occ_mult,
                lead_time_mult=lt_mult,
                suggested_rate=float(suggested),
                currency=currency,
            )
        )

    return suggestions


def summary_stats(suggestions: List[PriceSuggestion]) -> dict:
    """
    Compute summary statistics over a list of suggestions.
    Returns min, max, avg suggested_rate.
    """
    if not suggestions:
        return {"min": None, "max": None, "avg": None, "count": 0}
    rates = [s.suggested_rate for s in suggestions]
    return {
        "count": len(rates),
        "min": min(rates),
        "max": max(rates),
        "avg": round(sum(rates) / len(rates), 2),
    }
