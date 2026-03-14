"""
Cleaning Template Seeder — Phase 627

Default cleaning checklist template with EN + TH labels per room.
Used as fallback when no property-specific template exists.

Architecture:
- Pure data module — no DB reads/writes, no external calls.
- Returns a static dict that can be inserted into cleaning_checklist_templates.
"""
from __future__ import annotations


def get_default_template() -> dict:
    """
    Return the standard global cleaning checklist template.

    Structure:
        items: list of checklist items grouped by room
        supply_checks: list of supply verification items

    Each item has:
        room: room identifier (e.g. 'bedroom_1', 'kitchen')
        label: English label
        label_th: Thai label
        requires_photo: whether a photo is required for this item
    """
    return {
        "name": "Standard Cleaning",
        "items": [
            # --- Bedroom ---
            {"room": "bedroom_1", "label": "Change bed sheets", "label_th": "เปลี่ยนผ้าปูที่นอน", "requires_photo": True},
            {"room": "bedroom_1", "label": "Change pillowcases", "label_th": "เปลี่ยนปลอกหมอน", "requires_photo": False},
            {"room": "bedroom_1", "label": "Dust all surfaces", "label_th": "ปัดฝุ่นทุกพื้นผิว", "requires_photo": False},
            {"room": "bedroom_1", "label": "Vacuum/sweep floor", "label_th": "ดูดฝุ่น/กวาดพื้น", "requires_photo": False},
            {"room": "bedroom_1", "label": "Empty trash bin", "label_th": "เทถังขยะ", "requires_photo": False},
            # --- Bathroom ---
            {"room": "bathroom_1", "label": "Clean toilet", "label_th": "ทำความสะอาดชักโครก", "requires_photo": True},
            {"room": "bathroom_1", "label": "Clean shower/bathtub", "label_th": "ทำความสะอาดฝักบัว/อ่างอาบน้ำ", "requires_photo": False},
            {"room": "bathroom_1", "label": "Clean mirror & sink", "label_th": "ทำความสะอาดกระจกและอ่างล้างหน้า", "requires_photo": False},
            {"room": "bathroom_1", "label": "Replace towels", "label_th": "เปลี่ยนผ้าเช็ดตัว", "requires_photo": False},
            {"room": "bathroom_1", "label": "Check soap & shampoo", "label_th": "ตรวจสบู่และแชมพู", "requires_photo": False},
            {"room": "bathroom_1", "label": "Mop floor", "label_th": "ถูพื้น", "requires_photo": True},
            # --- Kitchen ---
            {"room": "kitchen", "label": "Clean countertops", "label_th": "ทำความสะอาดเคาน์เตอร์", "requires_photo": True},
            {"room": "kitchen", "label": "Clean stove/cooktop", "label_th": "ทำความสะอาดเตา", "requires_photo": False},
            {"room": "kitchen", "label": "Wash dishes & utensils", "label_th": "ล้างจานและช้อนส้อม", "requires_photo": False},
            {"room": "kitchen", "label": "Empty trash", "label_th": "เทถังขยะ", "requires_photo": False},
            {"room": "kitchen", "label": "Clean refrigerator", "label_th": "ทำความสะอาดตู้เย็น", "requires_photo": False},
            # --- Living Room ---
            {"room": "living_room", "label": "Clean & organize", "label_th": "ทำความสะอาดและจัดระเบียบ", "requires_photo": True},
            {"room": "living_room", "label": "Dust furniture", "label_th": "ปัดฝุ่นเฟอร์นิเจอร์", "requires_photo": False},
            {"room": "living_room", "label": "Vacuum/sweep floor", "label_th": "ดูดฝุ่น/กวาดพื้น", "requires_photo": False},
            # --- Exterior ---
            {"room": "exterior", "label": "Sweep entrance", "label_th": "กวาดทางเข้า", "requires_photo": True},
            {"room": "exterior", "label": "Check pool area (if applicable)", "label_th": "ตรวจสระว่ายน้ำ (ถ้ามี)", "requires_photo": False},
        ],
        "supply_checks": [
            {"item": "sheets", "label": "Enough clean sheets?", "label_th": "ผ้าปูที่นอนสะอาดเพียงพอ?"},
            {"item": "towels", "label": "Enough clean towels?", "label_th": "ผ้าขนหนูสะอาดเพียงพอ?"},
            {"item": "soap", "label": "Soap stocked?", "label_th": "สบู่เพียงพอ?"},
            {"item": "shampoo", "label": "Shampoo stocked?", "label_th": "แชมพูเพียงพอ?"},
            {"item": "toilet_paper", "label": "Toilet paper stocked?", "label_th": "กระดาษชำระเพียงพอ?"},
            {"item": "trash_bags", "label": "Trash bags available?", "label_th": "ถุงขยะเพียงพอ?"},
            {"item": "cleaning_supplies", "label": "Cleaning supplies stocked?", "label_th": "น้ำยาทำความสะอาดเพียงพอ?"},
        ],
    }


def get_rooms_requiring_photos() -> list[str]:
    """Return list of rooms that have at least one item requiring a photo."""
    template = get_default_template()
    rooms = set()
    for item in template["items"]:
        if item.get("requires_photo"):
            rooms.add(item["room"])
    return sorted(rooms)
