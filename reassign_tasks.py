import os
from supabase import create_client

def run():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    db = create_client(url, key)

    res = db.table("tasks").select("*").is_("assigned_to", "null").neq("status", "CANCELED").execute()
    tasks = res.data or []
    
    updates = 0
    for t in tasks:
        # First fix any legacy worker_roles:
        new_role = t["worker_role"]
        if t["kind"] == "CHECKIN_PREP" and new_role == "PROPERTY_MANAGER":
            new_role = "CHECKIN"
        if t["kind"] == "CHECKOUT_VERIFY" and new_role == "INSPECTOR":
            new_role = "CHECKOUT"
            
        # Try to find a worker for this new_role in the property
        prop_staff = db.table("staff_property_assignments").select("user_id").eq("property_id", t["property_id"]).execute()
        staff_ids = [s["user_id"] for s in (prop_staff.data or [])]
        
        assigned_user = None
        if staff_ids:
            perms = db.table("tenant_permissions").select("user_id, worker_roles").in_("user_id", staff_ids).execute()
            for p in (perms.data or []):
                roles = p.get("worker_roles") or []
                if new_role.lower() in roles:
                    assigned_user = p["user_id"]
                    break
        
        update_payload = {"worker_role": new_role}
        if assigned_user:
            update_payload["assigned_to"] = assigned_user
            
        db.table("tasks").update(update_payload).eq("task_id", t["task_id"]).execute()
        updates += 1
        print(f"Task {t['task_id']} ({t['kind']}) on {t['property_id']} -> Role: {new_role}, Assigned to: {assigned_user}")

    print(f"Fixed operations / workers for {updates} active unassigned tasks.")

if __name__ == "__main__":
    run()
