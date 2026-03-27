import os
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
db = create_client(url, key)

task_id = "6688f6ee75ae38f6"
tenant_id = "tenant_mamimia_staging"

db.table("tasks").update({"status": "ACKNOWLEDGED"}).eq("task_id", task_id).eq("tenant_id", tenant_id).execute()
print("RESET TO ACKNOWLEDGED")
