import os
import json
from supabase import create_client

def run():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    db = create_client(url, key)

    res = db.table("staff_property_assignments").select("*").execute()
    print("STAFF_PROPERTY_ASSIGNMENTS:")
    for r in res.data:
        print(f"Prop: {r['property_id']} | User: {r['user_id']}")

    res_wpa = db.table("worker_property_assignments").select("*").execute()
    print("\nWORKER_PROPERTY_ASSIGNMENTS:")
    for r in res_wpa.data:
        print(f"Prop: {r['property_id']} | Worker: {r['worker_id']} | Role: {r['worker_role']}")

if __name__ == "__main__":
    run()
