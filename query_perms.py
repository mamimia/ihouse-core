import os
from supabase import create_client
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
db = create_client(url, key)
res = db.table("tenant_permissions").select("*").execute()
print(res.data[0] if res.data else "No perms")
