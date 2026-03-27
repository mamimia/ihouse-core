import os
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
db = create_client(url, key)

res = db.table("guests").select("id, full_name, created_at, updated_at, identity_source").ilike("full_name", "%Longie%").execute()
print(res.data)

# Let's insert a row to test if a trigger duplicates it
new_guest = {
    "tenant_id": "tenant_mamimia_staging",
    "full_name": "Test Name",
}
insert_res = db.table("guests").insert(new_guest).execute()
print("INSERTED test row:", insert_res.data)
