import os
from datetime import datetime, timezone
from supabase import create_client
from tasks.task_writer import write_tasks_for_booking_created

def run():
    db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    # Find the problematic bookings logic
    # Jon Bolton (MAN...890e): Mar 21 - Mar 23
    # Dan Amir (MAN...cab3): Mar 23 - Mar 24
    # Kiko Papir (MAN...f360): Mar 26 - Mar 28

    books = db.table("booking_state").select("*").eq("property_id", "KPG-502").gte("check_in", "2026-03-20").execute()
    
    deleted = db.table("tasks").delete().eq("property_id", "KPG-502").neq("status", "CANCELED").execute()
    print(f"Deleted {len(deleted.data or [])} broken tasks.")

    for b in (books.data or []):
        count = write_tasks_for_booking_created(
            tenant_id=b["tenant_id"],
            booking_id=b["booking_id"],
            property_id=b["property_id"],
            check_in=b["check_in"],
            check_out=b["check_out"],  # Using the corrected checkout!
            provider=b["source"] or "manual",
            client=db,
        )
        print(f"Re-created {count} tasks natively for {b['booking_id']}")
        
if __name__ == "__main__":
    run()
