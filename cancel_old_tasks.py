import os
import sys
from datetime import datetime
from supabase import create_client

from src.services.audit_writer import write_audit_event

def _get_supabase_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Missing SUPABASE credentials in environment.")
        sys.exit(1)
    return create_client(url, key)

def cancel_old_tasks():
    db = _get_supabase_client()
    
    # Get today's ISO date string
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Find all tasks before today that are not completed or already canceled
    print(f"Finding pending/in_progress tasks with due_date < {today_str}...")
    
    res = db.table("tasks").select("*").lt("due_date", today_str).neq("status", "completed").neq("status", "CANCELED").execute()
    
    tasks = res.data or []
    if not tasks:
        print("No old active tasks found to cancel. System is already clean.")
        return
    
    print(f"Found {len(tasks)} old active tasks. Canceling them now...")
    
    for task in tasks:
        task_id = task["task_id"]
        tenant_id = task["tenant_id"]
        old_status = task["status"]
        
        # 1. Update status to CANCELED
        db.table("tasks").update({"status": "CANCELED"}).eq("task_id", task_id).execute()
        
        # 2. Write Audit Log
        write_audit_event(
            tenant_id=tenant_id,
            actor_id="system_admin_cleanup",
            action="TASK_CANCELED",
            entity_type="task",
            entity_id=task_id,
            payload={
                "from_status": old_status,
                "to_status": "CANCELED",
                "reason": "Admin mass cleanup of past overdue tasks"
            },
            client=db
        )
        print(f"  - Canceled task {task_id} (was {old_status}, due {task['due_date']})")

    print(f"Successfully CANCELED and logged {len(tasks)} old tasks.")

if __name__ == "__main__":
    cancel_old_tasks()
