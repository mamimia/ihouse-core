"""
Phase 652 — Problem Report Category Labels & Icons (i18n)

EN/TH/HE labels + emoji icons for all 14 problem categories.
Each category maps to a maintenance specialty for task routing.

Usage:
    from i18n.problem_report_labels import get_category_label, get_all_categories
    label = get_category_label("pool", "th")  # "สระว่ายน้ำ"
"""
from __future__ import annotations

from typing import Any


# Category definitions: key → {icon, specialty, en, th, he}
PROBLEM_CATEGORIES: dict[str, dict[str, str]] = {
    "pool": {
        "icon": "🏊",
        "specialty": "pool",
        "en": "Pool",
        "th": "สระว่ายน้ำ",
        "he": "בריכה",
    },
    "plumbing": {
        "icon": "🔧",
        "specialty": "plumbing",
        "en": "Plumbing",
        "th": "ประปา",
        "he": "אינסטלציה",
    },
    "electrical": {
        "icon": "⚡",
        "specialty": "electrical",
        "en": "Electrical",
        "th": "ไฟฟ้า",
        "he": "חשמל",
    },
    "ac_heating": {
        "icon": "❄️",
        "specialty": "electrical",
        "en": "AC / Heating",
        "th": "เครื่องปรับอากาศ / เครื่องทำความร้อน",
        "he": "מיזוג / חימום",
    },
    "furniture": {
        "icon": "🪑",
        "specialty": "furniture",
        "en": "Furniture",
        "th": "เฟอร์นิเจอร์",
        "he": "ריהוט",
    },
    "structure": {
        "icon": "🏠",
        "specialty": "general",
        "en": "Structure / Building",
        "th": "โครงสร้าง / อาคาร",
        "he": "מבנה",
    },
    "tv_electronics": {
        "icon": "📺",
        "specialty": "electrical",
        "en": "TV / Electronics",
        "th": "ทีวี / อุปกรณ์อิเล็กทรอนิกส์",
        "he": "טלוויזיה / אלקטרוניקה",
    },
    "bathroom": {
        "icon": "🚿",
        "specialty": "plumbing",
        "en": "Bathroom",
        "th": "ห้องน้ำ",
        "he": "חדר אמבטיה",
    },
    "kitchen": {
        "icon": "🍳",
        "specialty": "general",
        "en": "Kitchen",
        "th": "ห้องครัว",
        "he": "מטבח",
    },
    "garden_outdoor": {
        "icon": "🌿",
        "specialty": "gardening",
        "en": "Garden / Outdoor",
        "th": "สวน / พื้นที่กลางแจ้ง",
        "he": "גינה / חוץ",
    },
    "pest": {
        "icon": "🐛",
        "specialty": "general",
        "en": "Pest Control",
        "th": "กำจัดสัตว์รบกวน",
        "he": "הדברה",
    },
    "cleanliness": {
        "icon": "🧹",
        "specialty": "general",
        "en": "Cleanliness",
        "th": "ความสะอาด",
        "he": "ניקיון",
    },
    "security": {
        "icon": "🔐",
        "specialty": "general",
        "en": "Security",
        "th": "ความปลอดภัย",
        "he": "אבטחה",
    },
    "other": {
        "icon": "❓",
        "specialty": "general",
        "en": "Other",
        "th": "อื่นๆ",
        "he": "אחר",
    },
}

_SUPPORTED_LANGS = frozenset({"en", "th", "he"})


def get_category_label(category: str, lang: str = "en") -> str:
    """Return localized label for a problem category."""
    lang = lang if lang in _SUPPORTED_LANGS else "en"
    cat = PROBLEM_CATEGORIES.get(category)
    if not cat:
        return category.replace("_", " ").title()
    return cat.get(lang, cat["en"])


def get_category_icon(category: str) -> str:
    """Return emoji icon for a problem category."""
    cat = PROBLEM_CATEGORIES.get(category)
    return cat["icon"] if cat else "❓"


def get_category_specialty(category: str) -> str:
    """Return maintenance specialty key for routing."""
    cat = PROBLEM_CATEGORIES.get(category)
    return cat["specialty"] if cat else "general"


def get_all_categories(lang: str = "en") -> list[dict[str, Any]]:
    """Return all categories with icons and localized labels."""
    lang = lang if lang in _SUPPORTED_LANGS else "en"
    return [
        {
            "key": key,
            "icon": cat["icon"],
            "label": cat.get(lang, cat["en"]),
            "specialty": cat["specialty"],
        }
        for key, cat in PROBLEM_CATEGORIES.items()
    ]
