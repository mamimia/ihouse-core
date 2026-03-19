import os
import uuid
from supabase import create_client

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
db = create_client(url, key)

row = {
    "tenant_id": "test-tenant",
    "provider": "telegram",
    "is_active": True,
    "credentials": {"bot_token": "test"}
}
try:
    res = db.table("tenant_integrations").upsert(row, on_conflict="tenant_id,provider").execute()
    print("SUCCESS", res)
except Exception as e:
    print("ERROR:", str(e))
