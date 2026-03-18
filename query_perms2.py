import os
from supabase import create_client

def run():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    db = create_client(url, key)

    res = db.table("tenant_permissions").select("*").execute()
    if res.data:
        for row in res.data[:3]:
            print(f"UID: {row['user_id']} | Role: {row.get('role')} | Perms JSONB: {row.get('permissions')}")
    else:
        print("No perms found")

if __name__ == "__main__":
    run()
