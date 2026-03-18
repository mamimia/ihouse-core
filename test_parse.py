import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
db = create_client(url, key)

from src.tasks.task_model import Task
from src.tasks.task_writer import _row_to_task

res = db.table("tasks").select("*").limit(20).execute()
for r in res.data:
    try:
        task = _row_to_task(r)
    except Exception as e:
        print(f"FAILED on task {r['task_id']}: {e}")

print("DONE")
