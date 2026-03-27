import os
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
db = create_client(url, key)

result = db.table("tasks").select("*").eq("tenant_id", "tenant_mamimia_staging").eq("worker_role", "CHECKIN").limit(1).execute()
print("TASKS:", result.data)
