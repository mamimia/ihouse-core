# Phase 303 — Booking State Seeder for Owner Portal

**Status:** Closed  
**Prerequisite:** Phase 301 (Owner Portal Data)  
**Date Closed:** 2026-03-12

## Goal

Create a deterministic seed script that populates `booking_state`, `booking_financial_facts`, and `owner_portal_access` with realistic sample data so the Owner Portal summary endpoint returns meaningful results.

## Files Added

| File | Description |
|------|-------------|
| `src/scripts/seed_owner_portal.py` | **NEW** — Seeder script (dry-run + live Supabase modes) |
| `tests/test_seed_owner_portal.py` | **NEW** — 14 contract tests |

## Seed Data Profile

- **3 properties**: Ocean Villa Koh Samui, Bangkok Riverside Condo, Chiang Mai Mountain House
- **2 owners**: owner-1 (2 properties), owner-2 (1 property)
- **20 bookings**: spread from -90 to +30 days, random nights 1-7
- **OTA distribution**: Airbnb 35%, Booking.com 30%, Agoda 20%, direct 10%, Expedia 5%
- **Financial facts**: for all non-cancelled bookings with commission rates per OTA + 15-20% management fee
- **Fixed seed** (42): fully deterministic and reproducible

## CLI

```bash
PYTHONPATH=src python -m scripts.seed_owner_portal --dry-run   # preview
PYTHONPATH=src python -m scripts.seed_owner_portal              # live write
```

## Result

**14 passed, 0 failed**
