"""
Phase 830 — Comprehensive Demo Data Seeder
============================================

Seeds ALL tables needed to prove operational flows end-to-end:
  - properties (2)
  - booking_state (6: today-arrival, checked-in, today-departure, upcoming, past, cancelled)
  - booking_financial_facts (5, matching non-cancelled bookings)
  - tasks (3: 1 CLEANING pending, 1 MAINTENANCE pending, 1 CLEANING completed)
  - guest_deposit_records (1: collected for the checked-in booking)
  - problem_reports (1: open issue on a property)
  - tenant_permissions (1: admin user)

Usage:
    cd src && python3 -m scripts.seed_demo --dry-run
    cd src && python3 -m scripts.seed_demo
    cd src && python3 -m scripts.seed_demo --clean

Env vars required for live mode:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY)

Invariant:
    - tenant_id = "demo-tenant" (fixed)
    - All IDs prefixed "demo-" for easy identification and cleanup
    - Re-running is safe: uses upsert on primary keys
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ============================================================
# Constants
# ============================================================

TENANT_ID = "demo-tenant"
ADMIN_USER_ID = "demo-admin-001"

_TODAY = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _ds(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


NOW_ISO = _iso(datetime.now(timezone.utc))
NOW_MS = _ms(datetime.now(timezone.utc))

# ============================================================
# Properties (matches actual schema: property_id, display_name,
#   status must be pending|approved|archived|rejected)
# ============================================================

PROPERTIES = [
    {
        "property_id": "demo-villa-samui",
        "tenant_id": TENANT_ID,
        "display_name": "Samui Sunset Villa",
        "address": "88/5 Moo 3, Bophut, Koh Samui, Surat Thani 84320",
        "property_type": "villa",
        "bedrooms": 3,
        "bathrooms": 2,
        "max_guests": 6,
        "status": "approved",
        "operational_status": "available",
        "latitude": 9.5312,
        "longitude": 100.0621,
        "city": "Koh Samui",
        "country": "Thailand",
        "checkin_time": "15:00",
        "checkout_time": "11:00",
        "deposit_required": True,
        "deposit_amount": 5000,
        "wifi_name": "SamuiVilla-5G",
        "wifi_password": "welcome2024",
        "created_at": NOW_ISO,
        "updated_at": NOW_ISO,
    },
    {
        "property_id": "demo-condo-bkk",
        "tenant_id": TENANT_ID,
        "display_name": "Riverside Bangkok Condo",
        "address": "41 Charoen Nakhon Rd, Khlong Ton Sai, Bangkok 10600",
        "property_type": "condo",
        "bedrooms": 1,
        "bathrooms": 1,
        "max_guests": 2,
        "status": "approved",
        "operational_status": "available",
        "latitude": 13.7173,
        "longitude": 100.4955,
        "city": "Bangkok",
        "country": "Thailand",
        "checkin_time": "14:00",
        "checkout_time": "12:00",
        "deposit_required": True,
        "deposit_amount": 3000,
        "wifi_name": "RiverCondo-WiFi",
        "wifi_password": "guest1234",
        "created_at": NOW_ISO,
        "updated_at": NOW_ISO,
    },
]

# ============================================================
# Bookings (matches actual: booking_id, version, state_json,
#   updated_at_ms, check_in/check_out as dates, reservation_ref)
# ============================================================

def _booking_state_json(b: dict) -> str:
    return json.dumps({
        "guest_name": b.get("guest_name", ""),
        "guest_email": b.get("guest_email", ""),
        "guest_phone": b.get("guest_phone", ""),
        "total_price": b.get("total_price", 0),
    })


_BOOKING_DEFS = [
    # 1. TODAY'S ARRIVAL
    {
        "booking_id": "demo-bk-arriving",
        "reservation_ref": "DEMO-AIR-001",
        "property_id": "demo-villa-samui",
        "check_in": _ds(_TODAY),
        "check_out": _ds(_TODAY + timedelta(days=3)),
        "status": "confirmed",
        "source": "airbnb",
        "guest_name": "Maria García",
        "guest_email": "maria@example.com",
        "guest_phone": "+66891234567",
        "total_price": 12000,
        "currency": "THB",
    },
    # 2. CHECKED IN
    {
        "booking_id": "demo-bk-instay",
        "reservation_ref": "DEMO-BKC-002",
        "property_id": "demo-condo-bkk",
        "check_in": _ds(_TODAY - timedelta(days=2)),
        "check_out": _ds(_TODAY + timedelta(days=1)),
        "status": "checked_in",
        "source": "booking_com",
        "guest_name": "James Wilson",
        "guest_email": "james@example.com",
        "guest_phone": "+66897654321",
        "total_price": 6000,
        "currency": "THB",
    },
    # 3. TODAY'S DEPARTURE
    {
        "booking_id": "demo-bk-departing",
        "reservation_ref": "DEMO-AGD-003",
        "property_id": "demo-villa-samui",
        "check_in": _ds(_TODAY - timedelta(days=4)),
        "check_out": _ds(_TODAY),
        "status": "checked_in",
        "source": "agoda",
        "guest_name": "Yuki Tanaka",
        "guest_email": "yuki@example.com",
        "guest_phone": "+66881112222",
        "total_price": 16000,
        "currency": "THB",
    },
    # 4. UPCOMING
    {
        "booking_id": "demo-bk-upcoming",
        "reservation_ref": "DEMO-DIR-004",
        "property_id": "demo-condo-bkk",
        "check_in": _ds(_TODAY + timedelta(days=7)),
        "check_out": _ds(_TODAY + timedelta(days=10)),
        "status": "confirmed",
        "source": "direct",
        "guest_name": "Pierre Dubois",
        "guest_email": "pierre@example.com",
        "guest_phone": "+33612345678",
        "total_price": 9000,
        "currency": "THB",
    },
    # 5. PAST
    {
        "booking_id": "demo-bk-past",
        "reservation_ref": "DEMO-AIR-005",
        "property_id": "demo-villa-samui",
        "check_in": _ds(_TODAY - timedelta(days=14)),
        "check_out": _ds(_TODAY - timedelta(days=10)),
        "status": "checked_out",
        "source": "airbnb",
        "guest_name": "Sarah Johnson",
        "guest_email": "sarah@example.com",
        "guest_phone": "+14155551234",
        "total_price": 20000,
        "currency": "THB",
    },
    # 6. CANCELLED
    {
        "booking_id": "demo-bk-cancelled",
        "reservation_ref": "DEMO-EXP-006",
        "property_id": "demo-condo-bkk",
        "check_in": _ds(_TODAY + timedelta(days=5)),
        "check_out": _ds(_TODAY + timedelta(days=8)),
        "status": "cancelled",
        "source": "expedia",
        "guest_name": "Ahmed Hassan",
        "total_price": 7500,
        "currency": "THB",
    },
]

BOOKINGS = []
for _i, _b in enumerate(_BOOKING_DEFS):
    BOOKINGS.append({
        "booking_id": _b["booking_id"],
        "tenant_id": TENANT_ID,
        "property_id": _b["property_id"],
        "reservation_ref": _b["reservation_ref"],
        "check_in": _b["check_in"],
        "check_out": _b["check_out"],
        "status": _b["status"],
        "source": _b["source"],
        "guest_name": _b.get("guest_name"),
        "total_price": _b["total_price"],
        "currency": _b.get("currency", "THB"),
        "version": 1,
        "updated_at_ms": NOW_MS,
        "state_json": _booking_state_json(_b),
        "booking_source": "ota" if _b["source"] != "direct" else "direct",
    })

# ============================================================
# Financial Facts (matches actual: provider, source_confidence,
#   event_kind, recorded_at — no "source" or "gross_revenue")
# ============================================================

FINANCIAL_FACTS = []
_COMMISSION_RATES = {"airbnb": 0.03, "booking_com": 0.15, "agoda": 0.18, "expedia": 0.20, "direct": 0.0}

for _b in _BOOKING_DEFS:
    if _b["status"] == "cancelled":
        continue
    _total = _b["total_price"]
    _ota = round(_total * _COMMISSION_RATES.get(_b["source"], 0.15), 2)
    _net = round(_total - _ota, 2)
    FINANCIAL_FACTS.append({
        "booking_id": _b["booking_id"],
        "tenant_id": TENANT_ID,
        "provider": _b["source"],
        "total_price": _total,
        "currency": _b.get("currency", "THB"),
        "ota_commission": _ota,
        "net_to_property": _net,
        "source_confidence": "high",
        "event_kind": "BOOKING_CREATED",
        "recorded_at": NOW_ISO,
    })

# ============================================================
# Tasks (matches actual: priority + urgency are NOT NULL)
# ============================================================

TASKS = [
    {
        "task_id": "demo-task-clean-villa",
        "tenant_id": TENANT_ID,
        "property_id": "demo-villa-samui",
        "booking_id": "demo-bk-departing",
        "kind": "CLEANING",
        "status": "PENDING",
        "priority": "normal",
        "urgency": "normal",
        "worker_role": "CLEANER",
        "ack_sla_minutes": 30,
        "title": "Turnover clean — Samui Sunset Villa",
        "description": "Deep clean after Yuki Tanaka checkout. Next guest arrives today.",
        "due_date": _ds(_TODAY),
        "created_at": NOW_ISO,
        "updated_at": NOW_ISO,
    },
    {
        "task_id": "demo-task-maint-condo",
        "tenant_id": TENANT_ID,
        "property_id": "demo-condo-bkk",
        "booking_id": "demo-bk-instay",
        "kind": "MAINTENANCE",
        "status": "PENDING",
        "priority": "high",
        "urgency": "high",
        "worker_role": "MAINTENANCE",
        "ack_sla_minutes": 5,
        "title": "Fix AC unit — Bangkok Condo",
        "description": "AC in bedroom not cooling. Guest reported temp stays at 28°C.",
        "due_date": _ds(_TODAY),
        "created_at": NOW_ISO,
        "updated_at": NOW_ISO,
    },
    {
        "task_id": "demo-task-clean-done",
        "tenant_id": TENANT_ID,
        "property_id": "demo-condo-bkk",
        "booking_id": "demo-bk-past",
        "kind": "CLEANING",
        "status": "COMPLETED",
        "priority": "normal",
        "urgency": "normal",
        "worker_role": "CLEANER",
        "ack_sla_minutes": 30,
        "title": "Standard clean — Bangkok Condo",
        "description": "Post-checkout cleaning completed.",
        "due_date": _ds(_TODAY - timedelta(days=3)),
        "created_at": _iso(_TODAY - timedelta(days=3)),
        "updated_at": _iso(_TODAY - timedelta(days=3, hours=-4)),
    },
]

# ============================================================
# Guest Deposit Records (actual table name, uuid PK,
#   needs property_id)
# ============================================================

DEPOSITS = [
    {
        "tenant_id": TENANT_ID,
        "booking_id": "demo-bk-instay",
        "property_id": "demo-condo-bkk",
        "amount": 5000,
        "currency": "THB",
        "status": "collected",
        "collected_by": ADMIN_USER_ID,
        "collected_at": _iso(_TODAY - timedelta(days=2)),
        "refund_amount": 5000,
        "created_at": _iso(_TODAY - timedelta(days=2)),
    },
]

# ============================================================
# Problem Reports (actual: reported_by, id is uuid auto-gen,
#   priority not severity)
# ============================================================

PROBLEM_REPORTS = [
    {
        "tenant_id": TENANT_ID,
        "property_id": "demo-condo-bkk",
        "reported_by": ADMIN_USER_ID,
        "category": "hvac",
        "priority": "normal",
        "description": "AC unit in master bedroom blowing warm air. Thermostat set to 22°C but room stays at 28°C.",
        "status": "open",
        "created_at": NOW_ISO,
        "updated_at": NOW_ISO,
    },
]

# ============================================================
# Tenant Permissions
# ============================================================

TENANT_PERMISSIONS = [
    {
        "tenant_id": TENANT_ID,
        "user_id": ADMIN_USER_ID,
        "role": "admin",
        "permissions": json.dumps({
            "can_manage_properties": True,
            "can_manage_bookings": True,
            "can_manage_tasks": True,
            "can_manage_workers": True,
            "can_view_financials": True,
            "can_manage_integrations": True,
        }),
        "created_at": NOW_ISO,
        "updated_at": NOW_ISO,
    },
]

# ============================================================
# Table registry — order matters for FK safety
# ============================================================

TABLE_DATA = [
    ("properties", PROPERTIES, None),               # PK is serial id, property_id has no unique
    ("booking_state", BOOKINGS, "booking_id"),
    ("booking_financial_facts", FINANCIAL_FACTS, None),  # PK is serial id, booking_id has no unique
    ("tasks", TASKS, "task_id"),
    ("guest_deposit_records", DEPOSITS, None),       # uuid PK auto-generated
    ("problem_reports", PROBLEM_REPORTS, None),       # uuid PK auto-generated
    ("tenant_permissions", TENANT_PERMISSIONS, "tenant_id,user_id"),
]


def _get_db():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ============================================================
# GUARD: Test tenant allowlist — only these prefixes can be
#   deleted by --reset-all-test.  Production tenants are NEVER
#   touched.
# ============================================================

_TEST_TENANT_PREFIXES = (
    "demo-",
    "test-",
    "test_",
    "proof-",
    "seed-",
    "public-onboard",
    "tenant_e2e",
    "tenant_test",
    "tenant_dup",
    "tenant_ord",
    "tenant_trig",
    "tenant_status",
    "tenant_replay",
    "tenant_1",
    "t_",
)

# Tables with tenant_id that can hold test data, ordered leaf → root
# for FK-safe deletion.
_RESET_TABLES_ORDERED = [
    # Layer 4 — leaf artifacts (FK to parent via uuid)
    "cleaning_photos",          # FK → cleaning_task_progress.id
    "deposit_deductions",       # FK → guest_deposit_records.id
    "problem_report_photos",    # FK → problem_reports.id
    # Layer 3 — operational state
    "cleaning_task_progress",
    "guest_deposit_records",
    "problem_reports",
    "task_notes",
    "task_actions",
    # Layer 2 — core derived data
    "booking_financial_facts",
    "tasks",
    "guest_profile",
    "guest_checkin_forms",
    "extra_orders",
    "notification_log",
    "notification_delivery_log",
    "audit_events",
    "admin_audit_log",
    "outbound_sync_log",
    "pre_arrival_queue",
    "user_sessions",
    # Layer 1.5 — integrations & connections
    "ical_connections",
    "tenant_permissions",       # cleaned then re-seeded
    # Layer 1 — booking_state (must null FK first)
    "booking_state",
    # Layer 0 — root
    "properties",
]

# event_log has NO tenant_id — purged separately as full table wipe.
_GLOBAL_PURGE_TABLES = ["event_log"]


def _is_test_tenant(tenant_id: str | None) -> bool:
    """Check if a tenant_id matches the test/demo allowlist."""
    if tenant_id is None:
        return True  # orphaned rows are always safe to clean
    return any(tenant_id.startswith(p) for p in _TEST_TENANT_PREFIXES)


def _count_test_rows(db, table: str) -> tuple[int, int]:
    """Return (test_rows, total_rows) for a table."""
    try:
        total_r = db.table(table).select("*", count="exact").limit(0).execute()
        total = total_r.count if hasattr(total_r, "count") and total_r.count else 0
    except Exception:
        return 0, 0

    if total == 0:
        return 0, 0

    # Count test rows by fetching tenant_ids
    try:
        all_rows = db.table(table).select("tenant_id").execute()
        test_count = sum(1 for r in all_rows.data if _is_test_tenant(r.get("tenant_id")))
        return test_count, total
    except Exception:
        return 0, total


def _delete_test_rows(db, table: str) -> int:
    """Delete all rows matching test tenant prefixes. Returns count deleted."""
    try:
        all_rows = db.table(table).select("tenant_id").execute()
    except Exception:
        return 0

    # Collect distinct test tenant_ids
    test_tenants = set()
    has_null = False
    for r in all_rows.data:
        tid = r.get("tenant_id")
        if tid is None:
            has_null = True
        elif _is_test_tenant(tid):
            test_tenants.add(tid)

    deleted = 0
    for tid in test_tenants:
        try:
            # Special handling for booking_state: null the FK before deleting
            if table == "booking_state":
                db.table(table).update({"last_event_id": None}).eq("tenant_id", tid).execute()
            result = db.table(table).delete().eq("tenant_id", tid).execute()
            deleted += len(result.data) if result.data else 0
        except Exception as exc:
            logger.warning("  %s: error deleting tenant=%s: %s", table, tid, exc)

    # Handle orphaned rows (tenant_id IS NULL)
    if has_null:
        try:
            if table == "booking_state":
                db.table(table).update({"last_event_id": None}).is_("tenant_id", "null").execute()
            result = db.table(table).delete().is_("tenant_id", "null").execute()
            deleted += len(result.data) if result.data else 0
        except Exception as exc:
            logger.warning("  %s: error deleting NULL tenant rows: %s", table, exc)

    return deleted


def reset_all_test(dry_run: bool = True) -> dict:
    """
    Full test data reset — deletes ALL test/demo tenant data across
    the entire dependency chain, then re-seeds fresh demo data.

    Guards:
        1. ENV guard — refuses to run if IHOUSE_ENV == 'production'
        2. Tenant allowlist — only deletes tenants matching _TEST_TENANT_PREFIXES
        3. Dry-run mode — default, shows what WOULD be deleted
        4. Leaf-to-root order — respects FK dependencies
        5. Re-seed — fresh demo data after cleanup
    """
    # === GUARD 1: Environment check ===
    env = os.environ.get("IHOUSE_ENV", "").lower()
    if env == "production":
        print("❌ BLOCKED: --reset-all-test cannot run when IHOUSE_ENV=production")
        return {"error": "blocked_production"}

    db = _get_db()
    summary = {"dry_run": dry_run, "guard": "passed", "env": env or "unset", "tables": {}}

    print(f"\n{'=' * 60}")
    print(f"  FULL TEST DATA RESET {'(DRY RUN)' if dry_run else '(LIVE)'}")
    print(f"  Environment: {env or 'unset (OK)'}")
    print(f"  Tenant prefixes: {', '.join(_TEST_TENANT_PREFIXES)}")
    print(f"{'=' * 60}\n")

    # === Phase 1: Count what would be deleted ===
    print("--- Phase 1: Scan ---\n")
    total_test = 0
    total_all = 0
    for table in _RESET_TABLES_ORDERED:
        test_rows, total_rows = _count_test_rows(db, table)
        total_test += test_rows
        total_all += total_rows
        marker = "🔴" if test_rows > 0 else "⚪"
        print(f"  {marker} {table}: {test_rows}/{total_rows} test rows")
        summary["tables"][table] = {"test_rows": test_rows, "total_rows": total_rows}

    print(f"\n  TOTAL: {total_test} test rows out of {total_all} total")
    print(f"  After reset: ~{total_all - total_test} rows remain\n")

    if dry_run:
        print("  ℹ️  This was a dry run. Run with --reset-all-test (no --dry-run) to execute.\n")
        return summary

    # === Phase 2: Delete (leaf → root) ===
    print("--- Phase 2: Delete (leaf → root) ---\n")
    for table in _RESET_TABLES_ORDERED:
        test_rows = summary["tables"][table]["test_rows"]
        if test_rows == 0:
            continue
        deleted = _delete_test_rows(db, table)
        print(f"  🗑️  {table}: deleted {deleted} rows")
        summary["tables"][table]["deleted"] = deleted

    # === Phase 2b: Purge global tables (no tenant_id) ===
    print("\n--- Phase 2b: Purge global tables ---\n")
    for table in _GLOBAL_PURGE_TABLES:
        try:
            r_count = db.table(table).select("*", count="exact").limit(0).execute()
            count = r_count.count if hasattr(r_count, "count") and r_count.count else 0
            if count == 0:
                print(f"  ⚪ {table}: already empty")
                continue
            r = db.table(table).delete().neq("event_id", "___never_match___").execute()
            deleted = len(r.data) if r.data else 0
            print(f"  🗑️  {table}: purged {deleted} rows (no tenant_id — full wipe)")
            summary["tables"][table] = {"purged": deleted}
        except Exception as exc:
            print(f"  ⚠️  {table}: {exc}")
            summary["tables"][table] = {"error": str(exc)}

    # === Phase 3: Re-seed fresh demo data ===
    print("\n--- Phase 3: Re-seed fresh demo data ---\n")
    seed_result = seed(dry_run=False)
    summary["reseed"] = seed_result

    # === Phase 4: Post-reset verification ===
    print("\n--- Phase 4: Post-reset verification ---\n")
    remaining = {}
    for table in _RESET_TABLES_ORDERED:
        _, total = _count_test_rows(db, table)
        test, _ = _count_test_rows(db, table)
        remaining[table] = {"total": total, "test": test}
        if total > 0:
            print(f"  {table}: {total} rows remaining ({test} test)")

    summary["post_reset"] = remaining

    # Key metric: booking count
    bs_after = remaining.get("booking_state", {}).get("total", "?")
    print(f"\n  📊 booking_state after reset: {bs_after} rows")
    print(f"\n✅ Full test data reset complete.\n")

    return summary


def seed(dry_run: bool = True) -> dict:
    summary = {"dry_run": dry_run, "tables": {}}

    if dry_run:
        print("\n=== DRY RUN — Demo Seed Preview ===\n")
        for tbl, rows, pk in TABLE_DATA:
            print(f"  {tbl}: {len(rows)} rows (pk={pk or 'auto-uuid'})")
            for r in rows[:3]:
                keys = list(r.keys())[:3]
                print(f"    → {' | '.join(f'{k}={r[k]}' for k in keys)}")
            if len(rows) > 3:
                print(f"    ... and {len(rows) - 3} more")
            summary["tables"][tbl] = len(rows)
        print("\n=== End Preview ===\n")
        return summary

    db = _get_db()

    for tbl, rows, pk in TABLE_DATA:
        print(f"  Seeding {tbl} ({len(rows)} rows)...")
        try:
            if pk:
                db.table(tbl).upsert(rows, on_conflict=pk).execute()
            else:
                # For auto-uuid PKs: delete existing demo rows first, then insert
                db.table(tbl).delete().eq("tenant_id", TENANT_ID).execute()
                db.table(tbl).insert(rows).execute()
            print(f"    ✓ {len(rows)} rows written")
            summary["tables"][tbl] = {"written": len(rows)}
        except Exception as exc:
            print(f"    ✗ Error: {exc}")
            summary["tables"][tbl] = {"error": str(exc)}

    print("\n✅ Demo seed complete.")
    return summary


def clean() -> dict:
    """Clean only demo-tenant data (lightweight)."""
    db = _get_db()
    summary = {}
    for tbl, rows, pk in reversed(TABLE_DATA):
        try:
            result = db.table(tbl).delete().eq("tenant_id", TENANT_ID).execute()
            deleted = len(result.data) if result.data else 0
            print(f"  {tbl}: deleted {deleted} rows")
            summary[tbl] = deleted
        except Exception as exc:
            print(f"  {tbl}: error — {exc}")
            summary[tbl] = str(exc)
    print("\n🧹 Demo data cleaned.")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Seed demo data for operational flow proofs")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=False,
                       help="Preview seed data without writing")
    group.add_argument("--clean", action="store_true", default=False,
                       help="Remove demo-tenant data only")
    group.add_argument("--reset-all-test", action="store_true", default=False,
                       help="Full reset: delete ALL test/demo data + re-seed fresh")
    group.add_argument("--reset-all-test-dry-run", action="store_true", default=False,
                       help="Preview what --reset-all-test would delete")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.clean:
        result = clean()
    elif args.reset_all_test:
        result = reset_all_test(dry_run=False)
    elif args.reset_all_test_dry_run:
        result = reset_all_test(dry_run=True)
    else:
        result = seed(dry_run=args.dry_run)

    print(f"\nSummary: {json.dumps(result, indent=2, default=str)}")


if __name__ == "__main__":
    main()
