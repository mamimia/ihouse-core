import os
from supabase import create_client

def run():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    db = create_client(url, key)

    res = db.table("staff_property_assignments").select("user_id, assigned_role").eq("property_id", "KPG-502").execute()
    print("KPG-502 Assignments:")
    for row in res.data:
        print(f"  User: {row['user_id']} | Role: {row['assigned_role']}")
        
    print("\nAll staff_property_assignments:")
    res_all = db.table("staff_property_assignments").select("*").execute()
    for row in res_all.data:
        print(f"  Prop: {row['property_id']} | User: {row['user_id']} | Role: {row['assigned_role']}")

if __name__ == "__main__":
    run()
