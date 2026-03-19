import asyncio
import os
import json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
client = create_client(url, key)

def main():
    try:
        res = client.auth.admin.list_users()
        users = res.users if hasattr(res, 'users') else []
        target = None
        for u in users:
            meta = u.user_metadata or {}
            email = u.email or ""
            if "Jozzy" in str(meta) or "testCleaner" in email:
                target = u
                break
        
        if target:
            print("Found user:", target.email)
            response = client.auth.admin.generate_link(
                {"type": "magiclink", "email": target.email, "options": {"redirect_to": "http://localhost:3000/auth/callback"}}
            )
            print("--------------------------------------------------------------------------------")
            print("MAGIC LINK:")
            print(response.properties.action_link)
            print("--------------------------------------------------------------------------------")
        else:
            print("Could not find Jozzy. Here are the last 5 users:")
            for u in sorted(users, key=lambda x: x.created_at, reverse=True)[:5]:
                print(u.email, u.user_metadata)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
