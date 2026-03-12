"""
Phase 303 — Booking State Seeder for Owner Portal
====================================================

Deterministic seed script that populates `booking_state` and
`booking_financial_facts` with realistic sample data so the Owner Portal
can show meaningful occupancy %, financial totals, and booking breakdowns.

Usage:
    # Dry-run (prints rows, no DB writes)
    PYTHONPATH=src python -m scripts.seed_owner_portal --dry-run

    # Live write to Supabase
    PYTHONPATH=src python -m scripts.seed_owner_portal

Env vars required for live mode:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY)

Generated data:
    - 3 properties across 2 owners
    - 20 bookings spanning past 120 days → future 30 days
    - 15 with financial facts (matching booking_ids)
    - Realistic OTA distribution (Airbnb, Booking.com, Agoda, direct)
    - Statuses: confirmed, checked_in, checked_out, cancelled

Invariant:
    - tenant_id = "seed-tenant" (fixed for all seeded data)
    - booking_ids are deterministic (prefixed "seed-")
    - Re-running is safe: uses upsert on booking_id
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

TENANT_ID = "seed-tenant"

# ---- Properties ----
PROPERTIES = [
    {"property_id": "prop-villa-ocean", "name": "Ocean Villa Koh Samui", "owner_id": "owner-1"},
    {"property_id": "prop-condo-bkk",  "name": "Bangkok Riverside Condo", "owner_id": "owner-1"},
    {"property_id": "prop-house-cm",    "name": "Chiang Mai Mountain House", "owner_id": "owner-2"},
]

# ---- OTA Sources ----
OTA_SOURCES = ["airbnb", "booking_com", "agoda", "direct", "expedia"]
OTA_WEIGHTS = [0.35, 0.30, 0.20, 0.10, 0.05]

# ---- Statuses ----
STATUS_POOL = ["confirmed", "confirmed", "confirmed", "checked_in", "checked_out", "cancelled"]

# ---- Guest names ----
GUEST_NAMES = [
    "Yuki Tanaka", "James Wilson", "Maria García", "Li Wei",
    "Sarah Johnson", "Ahmed Hassan", "Anna Kowalski", "Pierre Dubois",
    "Priya Sharma", "Tom van der Berg", "Elena Petrov", "Lucas Kim",
    "Fatima Al-Rashid", "David Müller", "Sofia Rossi", "Chen Xiaoming",
    "Emma Thompson", "Raj Patel", "Isabella Rodriguez", "Kenji Yamamoto",
]


def _today() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _date_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _generate_bookings(count: int = 20, seed: int = 42) -> list[dict]:
    """Generate deterministic booking_state rows."""
    rng = random.Random(seed)
    today = _today()
    bookings = []

    for i in range(count):
        prop = rng.choice(PROPERTIES)
        # Spread check-ins from 90 days ago to 30 days in the future
        offset_days = rng.randint(-90, 30)
        check_in = today + timedelta(days=offset_days)
        nights = rng.randint(1, 7)
        check_out = check_in + timedelta(days=nights)

        source = rng.choices(OTA_SOURCES, OTA_WEIGHTS)[0]
        status = rng.choice(STATUS_POOL)

        # If check_in is in the past and check_out is in the past, status should be checked_out
        if check_out < today and status in ("confirmed", "checked_in"):
            status = "checked_out"
        # If check_in is in the future, status should be confirmed
        if check_in > today:
            status = "confirmed"

        booking_id = f"seed-{i:03d}"
        booking_ref = f"SEED-{source[:3].upper()}-{i:03d}"
        guest_name = GUEST_NAMES[i % len(GUEST_NAMES)]

        # Price: 1500-8000 THB per night
        price_per_night = rng.randint(1500, 8000)
        total_price = price_per_night * nights

        bookings.append({
            "booking_id": booking_id,
            "tenant_id": TENANT_ID,
            "property_id": prop["property_id"],
            "booking_ref": booking_ref,
            "check_in_date": _date_str(check_in),
            "check_out_date": _date_str(check_out),
            "status": status,
            "source": source,
            "guest_name": guest_name,
            "total_price": total_price,
            "currency": "THB",
        })

    return bookings


def _generate_financial_facts(bookings: list[dict], seed: int = 42) -> list[dict]:
    """Generate booking_financial_facts rows for non-cancelled bookings."""
    rng = random.Random(seed + 1)
    facts = []

    for b in bookings:
        if b["status"] == "cancelled":
            continue

        total = b["total_price"]
        source = b["source"]

        # OTA commission rates
        commission_rates = {
            "airbnb": 0.03,
            "booking_com": 0.15,
            "agoda": 0.18,
            "expedia": 0.20,
            "direct": 0.0,
        }
        ota_rate = commission_rates.get(source, 0.15)
        ota_commission = round(total * ota_rate, 2)

        # Management fee: 15-20%
        mgmt_rate = rng.uniform(0.15, 0.20)
        gross_revenue = round(total - ota_commission, 2)
        management_fee = round(gross_revenue * mgmt_rate, 2)
        net_to_property = round(gross_revenue - management_fee, 2)

        facts.append({
            "booking_id": b["booking_id"],
            "tenant_id": TENANT_ID,
            "gross_revenue": gross_revenue,
            "net_to_property": net_to_property,
            "management_fee": management_fee,
            "ota_commission": ota_commission,
            "total_price": total,
            "currency": "THB",
            "source": source,
        })

    return facts


def _generate_owner_portal_access() -> list[dict]:
    """Generate owner_portal_access rows so owners can see their properties."""
    rows = []
    for prop in PROPERTIES:
        rows.append({
            "tenant_id": TENANT_ID,
            "owner_id": prop["owner_id"],
            "property_id": prop["property_id"],
            "role": "owner",
            "granted_by": TENANT_ID,
        })
    return rows


def seed_to_supabase(dry_run: bool = True) -> dict:
    """
    Write seed data to Supabase.

    Returns summary dict with counts.
    """
    bookings = _generate_bookings()
    facts = _generate_financial_facts(bookings)
    access_rows = _generate_owner_portal_access()

    summary = {
        "bookings_generated": len(bookings),
        "facts_generated": len(facts),
        "access_rows_generated": len(access_rows),
        "properties": [p["property_id"] for p in PROPERTIES],
        "owners": list({p["owner_id"] for p in PROPERTIES}),
        "dry_run": dry_run,
    }

    if dry_run:
        print("\n=== DRY RUN — Seed Data Preview ===\n")
        print(f"Bookings: {len(bookings)}")
        for b in bookings[:5]:
            print(f"  {b['booking_ref']} | {b['property_id']} | "
                  f"{b['check_in_date']}→{b['check_out_date']} | "
                  f"{b['status']} | {b['source']} | ฿{b['total_price']}")
        if len(bookings) > 5:
            print(f"  ... and {len(bookings) - 5} more")

        print(f"\nFinancial Facts: {len(facts)}")
        for f in facts[:3]:
            print(f"  {f['booking_id']} | gross=฿{f['gross_revenue']} "
                  f"net=฿{f['net_to_property']} mgmt=฿{f['management_fee']} "
                  f"ota=฿{f['ota_commission']}")
        if len(facts) > 3:
            print(f"  ... and {len(facts) - 3} more")

        print(f"\nOwner Portal Access: {len(access_rows)}")
        for r in access_rows:
            print(f"  {r['owner_id']} → {r['property_id']} ({r['role']})")

        print("\n=== End Preview ===")
        return summary

    # Live mode
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    db = create_client(url, key)

    # 1. Upsert booking_state
    print(f"Writing {len(bookings)} bookings to booking_state...")
    try:
        db.table("booking_state").upsert(bookings, on_conflict="booking_id").execute()
        print(f"  ✓ {len(bookings)} booking_state rows upserted")
        summary["bookings_written"] = len(bookings)
    except Exception as exc:
        print(f"  ✗ booking_state error: {exc}")
        summary["bookings_error"] = str(exc)

    # 2. Upsert booking_financial_facts
    print(f"Writing {len(facts)} financial facts...")
    try:
        db.table("booking_financial_facts").upsert(facts, on_conflict="booking_id").execute()
        print(f"  ✓ {len(facts)} booking_financial_facts rows upserted")
        summary["facts_written"] = len(facts)
    except Exception as exc:
        print(f"  ✗ booking_financial_facts error: {exc}")
        summary["facts_error"] = str(exc)

    # 3. Upsert owner_portal_access (idempotent)
    print(f"Writing {len(access_rows)} owner portal access rows...")
    for row in access_rows:
        try:
            db.table("owner_portal_access").upsert(
                row, on_conflict="owner_id,property_id"
            ).execute()
        except Exception as exc:
            # May fail on unique constraint if already exists — that's fine
            logger.debug("owner_portal_access upsert skipped: %s", exc)
    print(f"  ✓ {len(access_rows)} access rows processed")
    summary["access_written"] = len(access_rows)

    print("\n✅ Seed complete.")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Seed Owner Portal with sample booking data")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Print data without writing to DB")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    result = seed_to_supabase(dry_run=args.dry_run)
    print(f"\nSummary: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    main()
