import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Missing credentials")
    exit(1)

db = create_client(url, key)

res = db.table("staff_property_assignments").select("user_id, property_id, tenant_id").execute()
assignments = res.data or []

result_perms = db.table("tenant_permissions").select("user_id, tenant_id, worker_roles").execute()
user_roles_map = {(r["tenant_id"], r["user_id"]): (r.get("worker_roles") or []) for r in (result_perms.data or [])}

tasks = db.table("tasks").select("task_id, property_id, worker_role, tenant_id").neq("status", "COMPLETED").neq("status", "CANCELED").execute().data or []

updates = 0
for t in tasks:
    t_role = t["worker_role"]
    # map old roles to the new ui-aligned aliases
    if t_role == "PROPERTY_MANAGER":
        check_role = "CHECKIN"
    elif t_role == "MAINTENANCE_TECH":
        check_role = "MAINTENANCE"
    elif t_role == "INSPECTOR":
        check_role = "CHECKOUT"
    else:
        check_role = t_role

    role_normalized = check_role.lower()

    # Find the first assigned staff who has this role
    match_uid = None
    for a in assignments:
        if a["property_id"] == t["property_id"] and a["tenant_id"] == t["tenant_id"]:
            uid = a["user_id"]
            if role_normalized in user_roles_map.get((t["tenant_id"], uid), []):
                match_uid = uid
                break

    if match_uid or t_role != check_role:
        update_data = {"worker_role": check_role}
        if match_uid:
            update_data["assigned_to"] = match_uid
        db.table("tasks").update(update_data).eq("task_id", t["task_id"]).execute()
        updates += 1

print(f"Updated {updates} tasks.")
