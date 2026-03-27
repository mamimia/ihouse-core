import os
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
db = create_client(url, key)

booking_id = "MAN-KPG-502-20260326-f360"

# 1. Booking State
b_res = db.table("booking_state").select("*").eq("booking_id", booking_id).execute()
print("=== BOOKING STATE ===")
print(b_res.data)

if b_res.data:
    tenant_id = b_res.data[0].get("tenant_id")
    # 2. Tasks
    t_res = db.table("tasks").select("*").eq("booking_id", booking_id).execute()
    print("\n=== TASKS ===")
    print(t_res.data)

    # 3. Guests
    guest_id = b_res.data[0].get("guest_id")
    if guest_id:
        g_res = db.table("guests").select("*").eq("id", guest_id).execute()
        print("\n=== GUESTS ===")
        print(g_res.data)

    # Search for any guest with full_name containing 'Longie' just in case
    g_search = db.table("guests").select("*").ilike("full_name", "%Longie%").execute()
    print("\n=== SEARCH GUESTS ===")
    print(g_search.data)

