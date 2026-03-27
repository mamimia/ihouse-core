import os
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
import httpx

# Get tokens from somewhere or just use db to do the update directly to see if the db update fails?
# Wait, let's just use the supabase client directly as the router uses it.
from api.error_models import ErrorCode
from tasks.task_model import VALID_TASK_TRANSITIONS, TaskStatus

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
db = create_client(url, key)

task_id = "6688f6ee75ae38f6"
tenant_id = "tenant_mamimia_staging"

result = db.table("tasks").select("*").eq("task_id", task_id).eq("tenant_id", tenant_id).limit(1).execute()
print("TASK RECORD FOUND:", bool(result.data))
if result.data:
    row = result.data[0]
    print("CURRENT STATUS:", row.get("status"))
    allowed = VALID_TASK_TRANSITIONS.get(TaskStatus(row["status"]), frozenset())
    print("ALLOWED TRANSITIONS:", allowed)
    if TaskStatus.COMPLETED not in allowed:
        print("TRANSITION NOT ALLOWED")

    try:
        update_res = db.table("tasks").update({"status": "COMPLETED"}).eq("task_id", task_id).eq("tenant_id", tenant_id).execute()
        print("UPDATE SUCCESS. Rows affected:", len(update_res.data))
    except Exception as e:
        print("UPDATE ERROR:", e)

