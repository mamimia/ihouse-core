import os
import json
from supabase import create_client

def run():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    db = create_client(url, key)

    res = db.table("tenant_permissions").select("*").execute()
    for row in res.data:
        perms = row.get("permissions") or {}
        print(f"User: {row['user_id']} | Details: {json.dumps(perms)}")

if __name__ == "__main__":
    run()
