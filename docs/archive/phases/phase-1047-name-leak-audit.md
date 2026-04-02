# Phase 1047 — Guest Portal: Internal Identifier Leakage Audit

**Trigger:** Staging screenshot confirmed `KPG-500` visible to guest as property name.  
**Rule locked:** Guest-facing surfaces must never render internal codes. Generic fallback only.

---

## 1. Current Leakage Truth — All Guest Portal Areas

### Hero / WelcomeHeader
| Field | Source | Guest-safe? | Fallback today | Fallback leaks? |
|---|---|---|---|---|
| `property_name` | `properties.name` | ✅ when set | `property_id or booking_ref` | 🔴 YES — confirmed leaking |
| `guest_name` | `guests.full_name` → fallback `bookings.guest_name` | ⚠️ partial | Raw OTA name e.g. "Airbnb (Not available)" | 🟡 POSSIBLE |
| `booking_status` | `bookings.status` raw | ✅ fixed 1047A | `_stayStatusChip()` maps known values | 🟡 unknown status falls through raw |
| `cover_photo_url` | `properties.cover_photo_url` | ✅ URL only | null → not rendered | ✅ safe |

### Home Essentials section
| Field | Guest-safe? | Notes |
|---|---|---|
| `wifi_name` | ✅ | Operator content, not an ID |
| `wifi_password` | ✅ | Operator content |
| `check_in_time` | ✅ | Time string |
| `check_out_time` | ✅ | Time string |
| `emergency_contact` | ✅ | Operator content |
| `welcome_message` | ✅ | Operator content |
| `house_rules` | ✅ | Operator content |

### How This Home Works section (house-info endpoint)
| Field | Guest-safe? | Notes |
|---|---|---|
| `ac_instructions` etc. | ✅ | Operator-authored free text |
| Section rendered as card only if data exists | Safe | No identifiers in the fields themselves |

### Need Help / Contact section
| Field | Guest-safe? | Leakage? |
|---|---|---|
| `contact.phone` | ✅ | Phone number |
| `contact.whatsapp_link` | ⚠️ | WhatsApp pre-fill text includes `property.name` directly. If `properties.name` is null → uses `""` → pre-fill is "Hi, I'm staying at " (empty but not an ID). If `properties.name` is a code → code goes into the WhatsApp text |
| `contact.email` | ✅ | Email address |

### Around You section
| Field | Guest-safe? | Notes |
|---|---|---|
| `location.map_url` | ✅ | Google Maps URL |
| `location.directions_url` | ✅ | Google Maps URL |
| `extras[].name` | ✅ | Operator content |
| `extras[].extra_id` | ✅ | Used as React `key` only — NOT rendered to guest |

### Your Stay section
| Field | Guest-safe? | Notes |
|---|---|---|
| `number_of_guests` | ✅ | Count |
| `deposit_status` | ✅ | Mapped through `depositLabel` object |
| `checkout_notes` | ✅ | Operator content |

### DB-fallback path (token valid, DB unavailable)
Line 308-313 of backend:
```python
return JSONResponse(status_code=200, content={
    "property_name": f"Property ({booking_ref})",   # 🔴 LEAKS booking_ref
    "check_in_time": "15:00",
    "check_out_time": "11:00",
    "house_rules": [],
})
```
Secondary leakage: the DB-unreachable fallback also includes the booking_ref directly.

---

## 2. Name-Source Mapping

### Current fallback chain for `property_name`

```
properties.name (DB)
  → null/missing?
    → property_id from token context        ← 🔴 INTERNAL CODE
      → null?
        → booking_ref from token context    ← 🔴 INTERNAL CODE
```

### WhatsApp link text

```
properties.name (DB field, fetched in /contact endpoint)
  → null/empty?
    → "" (empty string)          ← safe but ugly
    → WhatsApp text becomes: "Hi, I'm staying at "
```

### Guest name chain

```
guests.full_name (resolved via guest_id from booking_state)
  → guest_id not set?
    → bookings.guest_name (raw)  ← 🟡 can be "Airbnb (Not available)", "guest12345", etc.
      → null?
        → None → frontend shows "Welcome" (safe)
```

### Booking status chain

```
bookings.status (raw)
  → _stayStatusChip() maps known values
    → unknown value falls through as-is  ← 🟡 could show internal status string
```

---

## 3. Required Fix Set (by severity)

### 🔴 Critical — fix immediately

**Fix A — property_name fallback in portal endpoint (backend)**  
Location: `guest_portal_router.py` line 290  
Before:
```python
"property_name": prop_data.get("name", property_id or booking_ref),
```
After:
```python
"property_name": prop_data.get("name") or None,  # null → frontend uses guest-safe fallback
```

**Fix B — DB-unreachable fallback (backend)**  
Location: `guest_portal_router.py` line 309  
Before:
```python
"property_name": f"Property ({booking_ref})",
```
After:
```python
"property_name": None,  # frontend guard handles this
```

**Fix C — frontend guest-safe fallback (frontend)**  
Location: `page.tsx` line 206  
Before:
```tsx
{data.property_name}
```
After:
```tsx
{data.property_name || 'Your Villa'}
```
This is the final guest-facing defense. Must never render null/undefined.

### 🟡 Medium — fix in same phase

**Fix D — WhatsApp pre-fill text (backend)**  
Location: `guest_portal_router.py` line 412  
Before:
```python
property_name = prop.get("name", "")
wa_link = f"https://wa.me/...?text=Hi, I'm staying at {property_name}"
```
After:
```python
human_prop_name = prop.get("name") or "your villa"
wa_link = f"https://wa.me/...?text=Hi, I'm a guest staying at {human_prop_name}"
```

**Fix E — booking_status unknown-value fallback (frontend)**  
Location: `_stayStatusChip()` in `page.tsx`  
Before:
```tsx
if (s) return status!;  // returns raw internal status string
```
After:
```tsx
if (s) return 'In Stay';  // unknown status → default guest-safe label
```

**Fix F — guest_name sanitizer (backend)**  
Location: `guest_portal_router.py` — after canonical_guest_name resolution  
Add filter for known OTA placeholder strings:
```python
_INTERNAL_GUEST_NAME_PATTERNS = {
    'reserved', 'airbnb (not available)', 'not available',
    'guest', 'traveler', 'traveller',
}
if canonical_guest_name and canonical_guest_name.lower().strip() in _INTERNAL_GUEST_NAME_PATTERNS:
    canonical_guest_name = None  # frontend shows "Welcome" — safe
```

---

## 4. Full Audit Scope — Every Place to Check

| Area | File | Risk | Status |
|---|---|---|---|
| Hero property name | `page.tsx:206` | 🔴 Leaking | Fixed in this phase |
| Hero guest name | `page.tsx:203` | 🟡 OTA strings possible | Fixed in this phase |
| Hero booking_status chip | `page.tsx:200 + _stayStatusChip()` | 🟡 unknown values | Fixed in this phase |
| DB-fallback response | `guest_portal_router.py:309` | 🔴 booking_ref in name | Fixed in this phase |
| WhatsApp pre-fill text | `guest_portal_router.py:412` | 🟡 property code if name null | Fixed in this phase |
| extra_id | `page.tsx:465` | ✅ React key only | No action — verified safe |
| deposit_status | `page.tsx:507` | ✅ Mapped through label object | No action — verified safe |
| house_rules | `page.tsx:634` | ✅ Operator content | No action |
| House info fields | `page.tsx:304` | ✅ Operator content | No action |
| Location map_url | `page.tsx:~450` | ✅ URL only | No action |
| Checkout notes | `page.tsx:514` | ✅ Operator content | No action |
| Wi-Fi credentials | `page.tsx:618-619` | ✅ Operator content | No action |

**Departure Block (not yet built):** must be designed with this rule as a constraint from day one.  
**Host identity block (1047B):** must use only `manager_name_display`, not DB user IDs.

---

## 5. Proof Standard

Required before this phase is marked PROVEN:

1. Screenshot: real property name renders correctly (Emuna Villa or equivalent)
2. Screenshot: null-name case renders "Your Villa" (not a code, not blank)
3. Screenshot: no internal code visible anywhere in the full portal scroll
4. Screenshot: WhatsApp link pre-fill contains human property name or "your villa"
5. Trace: confirm with a test token where `properties.name` is null

---

## Phase Plan

### Phase 1047A-name (this phase — immediate, no DB changes)

**Fixes:** A, B, C, D, E, F above  
**Database:** no changes  
**Proof:** staging screenshots with real name + null-name test  
**Remaining open:** booking_status raw fallback for truly unknown values (low risk, generic fallback covers it)

### Why not defer

This is not a cosmetic issue. An internal property code visible on a guest-facing surface is a product defect. It must be fixed before any premium redesign work begins — you cannot build on an incorrect naming foundation.

### What stays open after this phase

- Operator-authored content (house_rules, checkout_notes, house_info fields) could theoretically contain internal codes if an admin writes them. This is a content governance issue, not a systemic code bug. Out of scope for automated fix.
- `check_in_time` / `check_out_time` default "15:00" / "11:00" — these fallbacks are guest-safe (standard hospitality times, not identifiers).
