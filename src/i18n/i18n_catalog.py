"""
Wave 9 — Categorized i18n String Catalog (Phases 736–742)
===========================================================

Extends the Phase 258 language_pack.py with domain-specific
categorized translations for guest forms, cleaning checklists,
problem reports, guest portal, and worker UI.

Structure: CATEGORY_PACK[category][key] = {lang: translation}
"""
from __future__ import annotations

from typing import Dict

SUPPORTED_LANGUAGES = frozenset({"en", "th", "he"})
DEFAULT_LANGUAGE = "en"

CATEGORY_PACK: Dict[str, Dict[str, Dict[str, str]]] = {
    # ==================================================================
    # Phase 737 — Guest Form Localization
    # ==================================================================
    "guest_form": {
        "title": {"en": "Guest Registration", "th": "ลงทะเบียนแขก", "he": "רישום אורח"},
        "guest_type_tourist": {"en": "Tourist", "th": "นักท่องเที่ยว", "he": "תייר"},
        "guest_type_resident": {"en": "Resident", "th": "ผู้อยู่อาศัย", "he": "תושב"},
        "full_name": {"en": "Full Name", "th": "ชื่อ-นามสกุล", "he": "שם מלא"},
        "email": {"en": "Email", "th": "อีเมล", "he": "אימייל"},
        "phone": {"en": "Phone Number", "th": "เบอร์โทรศัพท์", "he": "מספר טלפון"},
        "passport_number": {"en": "Passport Number", "th": "เลขหนังสือเดินทาง", "he": "מספר דרכון"},
        "nationality": {"en": "Nationality", "th": "สัญชาติ", "he": "לאום"},
        "arrival_date": {"en": "Arrival Date", "th": "วันที่เข้าพัก", "he": "תאריך הגעה"},
        "departure_date": {"en": "Departure Date", "th": "วันที่ออก", "he": "תאריך עזיבה"},
        "number_of_guests": {"en": "Number of Guests", "th": "จำนวนผู้เข้าพัก", "he": "מספר אורחים"},
        "special_requests": {"en": "Special Requests", "th": "คำขอพิเศษ", "he": "בקשות מיוחדות"},
        "submit": {"en": "Submit", "th": "ส่ง", "he": "שלח"},
        "cancel": {"en": "Cancel", "th": "ยกเลิก", "he": "ביטול"},
        "required_field": {"en": "This field is required", "th": "จำเป็นต้องกรอก", "he": "שדה חובה"},
        "invalid_email": {"en": "Invalid email address", "th": "อีเมลไม่ถูกต้อง", "he": "כתובת אימייל לא תקינה"},
        "invalid_phone": {"en": "Invalid phone number", "th": "เบอร์โทรไม่ถูกต้อง", "he": "מספר טלפון לא תקין"},
        "success": {"en": "Registration complete", "th": "ลงทะเบียนสำเร็จ", "he": "הרישום הושלם"},
    },
    # ==================================================================
    # Phase 738 — Cleaning Checklist Localization
    # ==================================================================
    "cleaning": {
        "change_sheets": {"en": "Change sheets", "th": "เปลี่ยนผ้าปูที่นอน", "he": "החלפת סדינים"},
        "change_towels": {"en": "Change towels", "th": "เปลี่ยนผ้าขนหนู", "he": "החלפת מגבות"},
        "clean_bathroom": {"en": "Clean bathroom", "th": "ทำความสะอาดห้องน้ำ", "he": "ניקוי חדר אמבטיה"},
        "clean_kitchen": {"en": "Clean kitchen", "th": "ทำความสะอาดครัว", "he": "ניקוי מטבח"},
        "vacuum_floors": {"en": "Vacuum floors", "th": "ดูดฝุ่นพื้น", "he": "שאיבת אבק רצפות"},
        "mop_floors": {"en": "Mop floors", "th": "ถูพื้น", "he": "שטיפת רצפות"},
        "wipe_surfaces": {"en": "Wipe surfaces", "th": "เช็ดทำความสะอาดพื้นผิว", "he": "ניגוב משטחים"},
        "empty_trash": {"en": "Empty trash bins", "th": "ทิ้งขยะ", "he": "ריקון פחי אשפה"},
        "check_supplies": {"en": "Check supplies", "th": "ตรวจสอบของใช้", "he": "בדיקת חומרים"},
        "restock_toiletries": {"en": "Restock toiletries", "th": "เติมของใช้ในห้องน้ำ", "he": "מילוי מוצרי טואלטיקה"},
        "check_ac": {"en": "Check A/C", "th": "ตรวจสอบแอร์", "he": "בדיקת מזגן"},
        "check_lights": {"en": "Check all lights", "th": "ตรวจสอบหลอดไฟ", "he": "בדיקת תאורה"},
        "lock_windows": {"en": "Lock windows", "th": "ล็อคหน้าต่าง", "he": "נעילת חלונות"},
        "take_photos": {"en": "Take completion photos", "th": "ถ่ายรูปหลังทำความสะอาด", "he": "צילום לאחר סיום"},
        "report_damage": {"en": "Report any damage", "th": "รายงานความเสียหาย", "he": "דיווח על נזק"},
    },
    # ==================================================================
    # Phase 739 — Problem Reporting Localization
    # ==================================================================
    "problem_report": {
        "title": {"en": "Report a Problem", "th": "รายงานปัญหา", "he": "דיווח על בעיה"},
        "category_plumbing": {"en": "Plumbing", "th": "ประปา", "he": "אינסטלציה"},
        "category_electrical": {"en": "Electrical", "th": "ไฟฟ้า", "he": "חשמל"},
        "category_appliance": {"en": "Appliance", "th": "เครื่องใช้ไฟฟ้า", "he": "מכשיר חשמלי"},
        "category_structural": {"en": "Structural", "th": "โครงสร้าง", "he": "מבני"},
        "category_cleaning": {"en": "Cleaning", "th": "ความสะอาด", "he": "ניקיון"},
        "category_pest": {"en": "Pest Control", "th": "กำจัดแมลง", "he": "הדברה"},
        "category_other": {"en": "Other", "th": "อื่นๆ", "he": "אחר"},
        "priority_low": {"en": "Low", "th": "ต่ำ", "he": "נמוכה"},
        "priority_medium": {"en": "Medium", "th": "กลาง", "he": "בינונית"},
        "priority_high": {"en": "High", "th": "สูง", "he": "גבוהה"},
        "priority_critical": {"en": "Critical", "th": "วิกฤต", "he": "קריטית"},
        "status_open": {"en": "Open", "th": "เปิด", "he": "פתוח"},
        "status_in_progress": {"en": "In Progress", "th": "กำลังดำเนินการ", "he": "בטיפול"},
        "status_resolved": {"en": "Resolved", "th": "แก้ไขแล้ว", "he": "נפתר"},
        "description": {"en": "Description", "th": "รายละเอียด", "he": "תיאור"},
        "add_photo": {"en": "Add Photo", "th": "เพิ่มรูปภาพ", "he": "הוספת תמונה"},
        "submit_report": {"en": "Submit Report", "th": "ส่งรายงาน", "he": "שליחת דיווח"},
    },
    # ==================================================================
    # Phase 740 — Guest Portal Localization
    # ==================================================================
    "guest_portal": {
        "welcome": {"en": "Welcome to your stay", "th": "ยินดีต้อนรับ", "he": "ברוכים הבאים"},
        "booking_details": {"en": "Booking Details", "th": "รายละเอียดการจอง", "he": "פרטי הזמנה"},
        "check_in": {"en": "Check-in", "th": "เช็คอิน", "he": "צ'ק-אין"},
        "check_out": {"en": "Check-out", "th": "เช็คเอาท์", "he": "צ'ק-אאוט"},
        "wifi_info": {"en": "Wi-Fi Information", "th": "ข้อมูล Wi-Fi", "he": "מידע Wi-Fi"},
        "house_rules": {"en": "House Rules", "th": "กฎของบ้าน", "he": "כללי הבית"},
        "contact_us": {"en": "Contact Us", "th": "ติดต่อเรา", "he": "צרו קשר"},
        "house_info": {"en": "House Information", "th": "ข้อมูลบ้าน", "he": "מידע על הבית"},
        "location": {"en": "Location & Map", "th": "ตำแหน่งและแผนที่", "he": "מיקום ומפה"},
        "extras": {"en": "Available Extras", "th": "บริการเสริม", "he": "שירותים נוספים"},
        "chat": {"en": "Chat with Host", "th": "แชทกับเจ้าของ", "he": "צ'אט עם המארח"},
        "report_problem": {"en": "Report a Problem", "th": "รายงานปัญหา", "he": "דיווח על בעיה"},
        "navigate": {"en": "Navigate to Property", "th": "นำทางไปยังที่พัก", "he": "נווט לנכס"},
    },
    # ==================================================================
    # Phase 742 — Worker UI labels
    # ==================================================================
    "worker": {
        "my_tasks": {"en": "My Tasks", "th": "งานของฉัน", "he": "המשימות שלי"},
        "claim_task": {"en": "Claim Task", "th": "รับงาน", "he": "קבלת משימה"},
        "complete_task": {"en": "Complete Task", "th": "ทำงานเสร็จ", "he": "סיום משימה"},
        "task_details": {"en": "Task Details", "th": "รายละเอียดงาน", "he": "פרטי משימה"},
        "upload_photos": {"en": "Upload Photos", "th": "อัพโหลดรูปภาพ", "he": "העלאת תמונות"},
        "navigate": {"en": "Navigate", "th": "นำทาง", "he": "נווט"},
        "checklist": {"en": "Checklist", "th": "รายการตรวจสอบ", "he": "רשימת בדיקה"},
        "report_issue": {"en": "Report Issue", "th": "รายงานปัญหา", "he": "דיווח על בעיה"},
    },
    # ==================================================================
    # Common labels
    # ==================================================================
    "common": {
        "save": {"en": "Save", "th": "บันทึก", "he": "שמור"},
        "cancel": {"en": "Cancel", "th": "ยกเลิก", "he": "ביטול"},
        "delete": {"en": "Delete", "th": "ลบ", "he": "מחק"},
        "edit": {"en": "Edit", "th": "แก้ไข", "he": "עריכה"},
        "back": {"en": "Back", "th": "กลับ", "he": "חזרה"},
        "next": {"en": "Next", "th": "ถัดไป", "he": "הבא"},
        "loading": {"en": "Loading...", "th": "กำลังโหลด...", "he": "טוען..."},
        "error": {"en": "An error occurred", "th": "เกิดข้อผิดพลาด", "he": "אירעה שגיאה"},
        "no_data": {"en": "No data available", "th": "ไม่มีข้อมูล", "he": "אין נתונים"},
        "confirm": {"en": "Confirm", "th": "ยืนยัน", "he": "אישור"},
        "yes": {"en": "Yes", "th": "ใช่", "he": "כן"},
        "no": {"en": "No", "th": "ไม่", "he": "לא"},
    },
}


# ======================================================================
# Helpers
# ======================================================================

def get_category_pack(category: str, lang: str) -> Dict[str, str]:
    """Return all keys for a category in the given language."""
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    cat = CATEGORY_PACK.get(category, {})
    return {key: t.get(lang, t.get(DEFAULT_LANGUAGE, key)) for key, t in cat.items()}


def get_full_pack(lang: str) -> Dict[str, Dict[str, str]]:
    """Return the full categorized pack for a language."""
    lang = lang.lower().strip()
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE
    return {cat: get_category_pack(cat, lang) for cat in CATEGORY_PACK}


def translate_key(category: str, key: str, lang: str) -> str:
    """Single key lookup."""
    translations = CATEGORY_PACK.get(category, {}).get(key, {})
    return translations.get(lang, translations.get(DEFAULT_LANGUAGE, key))


def get_all_categories() -> list:
    return sorted(CATEGORY_PACK.keys())


def check_completeness() -> Dict[str, list]:
    """Return missing translations by language."""
    missing: Dict[str, list] = {}
    for cat, keys in CATEGORY_PACK.items():
        for key, translations in keys.items():
            for lang in SUPPORTED_LANGUAGES:
                if lang not in translations:
                    missing.setdefault(lang, []).append(f"{cat}.{key}")
    return missing
