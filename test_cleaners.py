import os
from supabase import create_client
import json

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

resp = client.table("tenant_permissions").select("user_id, display_name, role, permissions, worker_roles").execute()
for r in resp.data:
    if r.get("role") == "worker":
        print(json.dumps(r, indent=2))
