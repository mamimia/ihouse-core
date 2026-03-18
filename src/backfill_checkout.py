import os
import uuid
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
db = create_client(url, key)

from tasks.task_model import TaskKind, TaskStatus, TaskPriority, WorkerRole
from datetime import datetime, timezone

# Find all CLEANING tasks to figure out the dates and bookings
res = db.table("tasks").select("booking_id, property_id, tenant_id, due_date").eq("kind", "CLEANING").execute()
cleanings = res.data or []

updates = 0
for c in cleanings:
    booking_id = c["booking_id"]
    property_id = c["property_id"]
    tenant_id = c["tenant_id"]
    due_date = c["due_date"] # The check_out date (since my update, or check_in for old)
    
    # Check if a checkout task already exists
    check = db.table("tasks").select("task_id").eq("booking_id", booking_id).eq("kind", "CHECKOUT_VERIFY").execute()
    if not check.data:
        import hashlib
        # deterministic task_id
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
            "due_date": due_date,
            "title": f"Checkout verification for {booking_id}",
            "description": "System backfill",
            "worker_role": "CHECKOUT",
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "updated_at": datetime.now(tz=timezone.utc).isoformat()
        }
        
        db.table("tasks").insert(row).execute()
        updates += 1

print(f"Backfilled {updates} CHECKOUT_VERIFY tasks.")
