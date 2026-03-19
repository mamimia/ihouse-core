import asyncio
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
client = create_client(url, key)

async def main():
    try:
        assigned_to = "test_user"
        props_csv = "prop1,prop2"
        res = client.table("tasks").select("*").or_(
            f"assigned_to.eq.{assigned_to},property_id.in.({props_csv})"
        ).execute()
        print("Success:", res)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
