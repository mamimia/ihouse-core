import os
import asyncio
from supabase import create_client
from channels.notification_dispatcher import NotificationMessage, _default_telegram_adapter

async def test_run():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    db = create_client(url, key)

    chat_id = "903092014"
    tenant_id = "tenant_mamimia_staging"
    user_id = "25407914-2071-4ee8-b8ae-8aa5967d8f20"

    res = db.table("tenant_permissions").select("language").eq("user_id", user_id).execute()
    lang = res.data[0]["language"] if res.data else "en"
    
    # Translations
    msgs = {
        "en": "🚨 *Domaniqo New Task* 🚨\n[CLEANING] Villa Sabai\n📅 Today, 11:00 AM - 14:00 PM\n📍 123 Beach Road\n⚠️ Please open your App to Accept this task now.",
        "he": "🚨 *Domaniqo משימה חדשה* 🚨\n[ניקיון] וילה סבאי\n📅 היום, 11:00 - 14:00\n📍 רחוב החוף 123\n⚠️ אנא פתח את האפליקציה כדי לאשר את המשימה כעת.",
        "th": "🚨 *Domaniqo งานใหม่* 🚨\n[ทำความสะอาด] วิลล่าสบาย\n📅 วันนี้ 11:00 - 14:00 น.\n📍 ถ.ชายหาด 123\n⚠️ กรุณาเปิดแอปเพื่อยอมรับงานนี้"
    }

    body = msgs.get(lang, msgs["en"])
    title = {"en": "Domaniqo Task", "he": "Domaniqo משימה", "th": "Domaniqo งาน"}.get(lang, "Domaniqo Task")

    msg = NotificationMessage(title=title, body=body)
    
    print(f"Detected language '{lang}'. Sending translated message...")
    res2 = _default_telegram_adapter(chat_id, msg, db, tenant_id)
    print("Sent:", res2)

if __name__ == "__main__":
    asyncio.run(test_run())
