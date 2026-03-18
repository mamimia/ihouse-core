import os
from supabase import create_client

def run():
    db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    res = db.table("tasks").select("task_id, kind, worker_role, assigned_to").eq("property_id", "KPG-502").execute()
    for row in res.data:
        print(row)
if __name__ == "__main__":
    run()
