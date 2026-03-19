import os
from supabase import create_client
db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
res = db.rpc("get_policies", {"p_table": "notification_channels"}).execute()
print(res)
