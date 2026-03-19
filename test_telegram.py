import asyncio
import os
from supabase import create_client
from channels.notification_dispatcher import NotificationMessage, _default_telegram_adapter

async def test_telegram_message(tenant_id: str, chat_id: str):
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    db = create_client(url, key)
    
    msg = NotificationMessage(
        title="iHouse Core Test",
        body="This is a live test notification from iHouse Core routed through the new tenant_integrations database!"
    )
    
    print(f"Dispatching test message to chat_id: {chat_id} for tenant: {tenant_id}")
    attempt = _default_telegram_adapter(
        channel_id=chat_id,
        message=msg,
        db=db,
        tenant_id=tenant_id
    )
    
    print("Dispatch Result:", attempt)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python test_telegram.py <tenant_id> <chat_id>")
    else:
        asyncio.run(test_telegram_message(sys.argv[1], sys.argv[2]))
