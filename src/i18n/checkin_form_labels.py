"""
Phase 616 — Check-in Form Language Labels (EN / TH / HE)

Used by guest-facing forms and pre-arrival portal.
"""
from __future__ import annotations

CHECKIN_FORM_LABELS = {
    "en": {
        "page_title": "Guest Check-in Form",
        "full_name": "Full Name",
        "nationality": "Nationality",
        "document_type": "Document Type",
        "document_number": "Document / Passport Number",
        "phone": "Phone",
        "email": "Email",
        "passport_photo": "Upload Passport / ID Photo",
        "signature": "Sign Here",
        "deposit_amount": "Deposit Amount",
        "deposit_currency": "Currency",
        "submit": "Submit Check-in Form",
        "guest_type_tourist": "Tourist",
        "guest_type_resident": "Resident",
        "add_guest": "Add Another Guest",
        "house_rules_title": "House Rules",
        "agree_rules": "I agree to the house rules",
        "wifi_info": "WiFi Information",
        "emergency_contact": "Emergency Contact",
        "collected_by": "Collected By",
        "notes": "Additional Notes",
    },
    "th": {
        "page_title": "แบบฟอร์มเช็คอินผู้เข้าพัก",
        "full_name": "ชื่อ-นามสกุล",
        "nationality": "สัญชาติ",
        "document_type": "ประเภทเอกสาร",
        "document_number": "เลขที่หนังสือเดินทาง / บัตรประชาชน",
        "phone": "เบอร์โทรศัพท์",
        "email": "อีเมล",
        "passport_photo": "อัปโหลดรูปถ่ายพาสปอร์ต / บัตรประชาชน",
        "signature": "ลงนามที่นี่",
        "deposit_amount": "จำนวนเงินมัดจำ",
        "deposit_currency": "สกุลเงิน",
        "submit": "ส่งแบบฟอร์มเช็คอิน",
        "guest_type_tourist": "นักท่องเที่ยว",
        "guest_type_resident": "ผู้พักอาศัย",
        "add_guest": "เพิ่มผู้เข้าพัก",
        "house_rules_title": "กฎของบ้าน",
        "agree_rules": "ฉันยอมรับกฎของบ้าน",
        "wifi_info": "ข้อมูล WiFi",
        "emergency_contact": "ผู้ติดต่อฉุกเฉิน",
        "collected_by": "เก็บเงินโดย",
        "notes": "หมายเหตุเพิ่มเติม",
    },
    "he": {
        "page_title": "טופס צ'ק-אין לאורח",
        "full_name": "שם מלא",
        "nationality": "לאום",
        "document_type": "סוג מסמך",
        "document_number": "מספר דרכון / תעודה",
        "phone": "טלפון",
        "email": "אימייל",
        "passport_photo": "העלה תמונת דרכון / תעודה",
        "signature": "חתום כאן",
        "deposit_amount": "סכום פיקדון",
        "deposit_currency": "מטבע",
        "submit": "שלח טופס צ'ק-אין",
        "guest_type_tourist": "תייר",
        "guest_type_resident": "תושב",
        "add_guest": "הוסף אורח נוסף",
        "house_rules_title": "כללי הבית",
        "agree_rules": "אני מסכים לכללי הבית",
        "wifi_info": "פרטי WiFi",
        "emergency_contact": "איש קשר לחירום",
        "collected_by": "נגבה על ידי",
        "notes": "הערות נוספות",
    },
}


# Phase 609 — Tourist vs Resident form logic
TOURIST_REQUIRED_FIELDS = {"full_name", "nationality", "document_type", "document_number", "passport_photo"}
RESIDENT_REQUIRED_FIELDS = {"full_name", "document_number"}


def get_required_fields(guest_type: str) -> set:
    """Phase 609: Return required fields based on guest type."""
    if guest_type == "resident":
        return RESIDENT_REQUIRED_FIELDS
    return TOURIST_REQUIRED_FIELDS


def get_labels(language: str = "en") -> dict:
    """Return labels for the given language, with English fallback."""
    return CHECKIN_FORM_LABELS.get(language, CHECKIN_FORM_LABELS["en"])
