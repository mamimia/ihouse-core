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
        bam_id = "19f9f4ed-34ae-45a3-87e2-309b8054d738"
        res = client.table("tasks").update({"assigned_to": None}).eq("assigned_to", bam_id).execute()
        count = len(res.data) if res.data else 0
        print(f"Successfully unassigned {count} tasks from Bam.")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
