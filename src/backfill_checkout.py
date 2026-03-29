import os
import uuid
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
db = create_client(url, key)

from tasks.task_model import TaskKind, TaskStatus, TaskPriority, WorkerRole
from datetime import datetime, timezone, date as date_type
import hashlib

# Phase 887d: Pre-fetch approved property IDs — Approved-Only Lifecycle Rule.
# Never backfill CHECKOUT_VERIFY tasks for bookings on non-approved properties.
approved_res = db.table("properties").select("property_id").eq("status", "approved").execute()
approved_property_ids = {row["property_id"] for row in (approved_res.data or [])}
print(f"Approved properties: {len(approved_property_ids)}")

# ── Phase 993-fix: Source bookings from booking_state directly ──────────────
# CRITICAL: CHECKOUT_VERIFY tasks must use check_out as due_date.
# Do NOT derive this from CLEANING tasks — CLEANING tasks use check_in as their
# due_date (for pre-arrival prep), which is the WRONG date for checkout tasks.
# Always read check_out from booking_state as the canonical source.

today_str = date_type.today().isoformat()

res = db.table("booking_state").select(
    "booking_id, property_id, tenant_id, check_in, check_out"
).not_.is_("check_out", "null").execute()
bookings = res.data or []

updates = 0
skipped_non_approved = 0
skipped_no_checkout = 0
skipped_past = 0

for b in bookings:
    booking_id = b["booking_id"]
    property_id = b["property_id"]
    tenant_id = b["tenant_id"]
    check_out = b.get("check_out")

    # Guard: skip if no checkout date
    if not check_out:
        skipped_no_checkout += 1
        continue

    # Guard: skip already-past checkouts (stale backfill prevention)
    if check_out < today_str:
        skipped_past += 1
        continue

    # Phase 887d: Skip non-approved properties
    if property_id not in approved_property_ids:
        skipped_non_approved += 1
        continue

    # Check if a checkout task already exists
    check = db.table("tasks").select("task_id").eq("booking_id", booking_id).eq("kind", "CHECKOUT_VERIFY").execute()
    if not check.data:
        # Deterministic task_id — same seed as task_automator.py
        seed = f"CHECKOUT_VERIFY:{booking_id}:{property_id}"
        task_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]

        row = {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "booking_id": booking_id,
            "property_id": property_id,
            "kind": "CHECKOUT_VERIFY",
            "status": "PENDING",
            "priority": "MEDIUM",
            "urgency": "normal",
            "ack_sla_minutes": 60,
            "due_date": check_out,   # ← CORRECT: check_out is the checkout date, NOT check_in
            "title": f"Checkout verification for {booking_id}",
            "description": "System backfill",
            "worker_role": "CHECKOUT",
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "updated_at": datetime.now(tz=timezone.utc).isoformat()
        }

        db.table("tasks").insert(row).execute()
        updates += 1

print(f"Backfilled {updates} CHECKOUT_VERIFY tasks.")
print(f"Skipped: {skipped_non_approved} non-approved, {skipped_past} past-checkout, {skipped_no_checkout} no-checkout-date.")
