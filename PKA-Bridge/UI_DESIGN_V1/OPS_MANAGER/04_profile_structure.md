# OPS Manager — Profile Structure (V1)

---

## Profile Access
- Mobile: via "More" sheet → Profile
- Desktop: via sidebar avatar click or sidebar "Profile" item
- URL: `/manager/profile`

---

## Profile Sections

### 1. Identity Header
```
┌─────────────────────────────┐
│  [Avatar 48px]              │
│  Pranee Thana               │
│  Operational Manager        │
│  ● Active                   │
└─────────────────────────────┘
```
- Avatar: circle, colored background, initials (or photo if uploaded)
- Name: 16px Manrope 800
- Role: 11px Inter, mid-gray
- Status: green dot + "Active" or red dot + "Suspended"
- Non-editable (admin-managed)

### 2. Contact Information
| Field | Type | Editable |
|-------|------|----------|
| Email | text | No (set by admin) |
| User ID | text | No (system-assigned) |
| Display Name | text | Yes (save button) |

### 3. Supervised Properties
- Chip list of assigned properties
- Each chip: property name (tappable → goes to property detail in bookings)
- If none: "No properties currently assigned" (muted text)
- Non-editable (admin-managed assignments)

### 4. Notification Preferences
| Field | Type | Editable | Notes |
|-------|------|----------|-------|
| LINE ID | text input | Yes | Primary notification channel in Thailand |
| Phone Number | text input | Yes | SMS fallback |
| [Save Preferences] button | — | — | Saves to `/permissions/{user_id}` |

### 5. Active Capabilities
- Read-only display of delegated capabilities
- Each capability: checkmark badge + capability name
- Examples: task_management, booking_view, staff_oversight, financial_view
- Footer: "Capabilities are managed by your admin" (muted, italicized)
- If none delegated: "No additional capabilities delegated by admin"

### 6. Session Information
- Mode indicator: Direct Login / Preview Mode / Act-As Mode
- Preview/Act-As: shows who initiated and when
- "End Session" button (only in Preview/Act-As modes)
- Last login timestamp

---

## Profile in Desktop Sidebar
On desktop, the sidebar header shows a compact profile summary:
```
┌──────────────────────┐
│ [AV] Pranee Thana    │
│      Op. Manager     │
│      ● Online        │
└──────────────────────┘
```
Click → navigates to full profile page.

---

## Mode Indicators (All Screens)

### Preview Mode
- Sidebar footer: "PREVIEW MODE" badge (blue background)
- "Close Preview" button
- All actions are read-only (no mutations)

### Act-As Mode
- Sidebar footer: "ACTING AS" badge (red background)
- Shows real admin identity: "Admin: [name]"
- "End Session" button
- Actions are live (mutations attributed to real admin)
- TTL countdown if approaching 4h limit

### Direct Login
- No special badge
- Standard operational mode
