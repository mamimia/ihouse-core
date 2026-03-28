# 🔍 System vs Product Vision Audit
### iHouse Core — מול חזון המוצר Domaniqo v2.0

> מסמך זה מפרט מה **יש לנו**, מה **חסר**, מה **יש לנו יותר מדי**, ומה צריך **לבנות** כדי ליישם את חזון המוצר.

---

## 📊 סיכום מהיר

| קטגוריה | מה יש | מה חסר | סטטוס |
|---------|--------|--------|-------|
| Property Registration | בסיסי ✅ | GPS, photos, amenities, deposit, hours | 🟡 40% |
| Onboarding Wizard | 3-step flow ✅ | Bulk import, OTA pull, smart defaults | 🟡 50% |
| Booking Lifecycle | Full flow ✅ | Manual booking with task opt-out | 🟢 75% |
| Check-in/out Status | State machine ✅ | Guest form, passport, deposit, QR | 🟡 35% |
| Task Automation | 6 kinds, SLA engine ✅ | Checklists, photos, take-over | 🟡 45% |
| Guest QR Portal | Basic structure ✅ | Extras, chat, QR gen, i18n | 🔴 25% |
| Owner Portal | Rich data ✅ | Configurable transparency toggles | 🟡 60% |
| Problem Reporting | Backend ✅ (6 endpoints, auto-task, SSE, audit, i18n) | Admin UI, photo storage pipeline | 🟡 60% |
| Guest Extras | ❌ | Everything | 🔴 0% |
| Maintenance | Task kind exists | Dashboard, split by specialty | 🔴 15% |
| Channels | 6 channels ✅ | Guest chat, WhatsApp for guests | 🟢 70% |
| i18n | Exists ✅ | Auto-translate, Thai/Hebrew | 🔴 20% |
| Worker IDs | ❌ | Unique IDs per worker | 🔴 0% |

**Overall: ~35% of product vision is implemented**

---

## 1. 🏠 רישום נכסים (Property Registration)

### ✅ מה יש:
```
onboarding_router.py (Phase 214):
├── property_id, display_name, timezone, base_currency
├── property_type, city, country, max_guests
├── bedrooms, beds, bathrooms, address, description
├── source_url, source_platform
└── Safety gate: 409 if property has active bookings
```

### ❌ מה חסר (מהחזון):
| שדה | סטטוס | עדיפות |
|-----|--------|-------|
| 📍 GPS Location (latitude/longitude) | חסר | 🔴 Critical |
| 📍 "Save Current Location" button | חסר | 🔴 Critical |
| 📸 Marketing Photos (import from OTA) | חסר | 🟡 High |
| 📸 Reference Photos (cleaner reference) | חסר | 🔴 Critical |
| ⏰ Check-in Time (default 3:00 PM) | חסר | 🟡 High |
| ⏰ Check-out Time (default 11:00 AM) | חסר | 🟡 High |
| 💰 Deposit amount + currency | חסר | 🟡 High |
| 🔑 Door code / key location | חסר (בDB?) | 🟡 High |
| 📶 WiFi name + password | **יש ב-guest_portal** | ✅ Partial |
| 📋 House Rules | **יש ב-guest_portal** | ✅ Partial |
| 🧹 Cleaning Checklist template | חסר | 🔴 Critical |
| 🛍️ Extras (per-property on/off) | חסר | 🟡 High |
| 🧹 Amenities (from OTA + manual) | חסר | 🟡 High |
| 👤 Default worker assignments (per property) | **יש (Step 3)** | ✅ Exists |
| ❄️ AC, boiler, parking, safe, etc. | חסר | 🟢 Medium |

### 🔵 מה יש לנו יותר מדי:
- **`source_url` + `source_platform`**: רלוונטי אבל עוד לא מקושר ל-API pull
- **Currency validation (25 currencies)**: יותר ממה שצריך ל-MVP (THB + USD מספיק)

---

## 2. 🔄 Onboarding Wizard

### ✅ מה יש:
```
3-Step Flow (Phase 214):
Step 1: POST /onboarding/start → Create property (Supabase)
Step 2: POST /onboarding/{id}/channels → Map OTA channels  
Step 3: POST /onboarding/{id}/workers → Assign workers
Status: GET /onboarding/{id}/status → Completion check
```

### ❌ מה חסר (מהחזון):
| פיצ'ר | סטטוס |
|-------|--------|
| One-Click OTA Connect (OAuth/API) | חסר — חסר adapter |
| Bulk Select & Import (50 properties) | חסר |
| iCal Fallback paste | חסר |
| CSV/Spreadsheet Import | חסר |
| Duplicate Detection (cross-OTA merge) | חסר |
| Smart Defaults (auto check-in/out times) | חסר |
| Pull amenities from OTA | חסר |
| Pull photos from OTA | חסר |

### 💡 הערכה:
ה-wizard הקיים הוא **backend API בלבד** — אין UI, אין OTA pull, אין bulk. צריך מעטפת שלמה.

---

## 3. 📅 Booking Lifecycle

### ✅ מה יש (מתקדם מאוד!):
```
90+ routers כולל:
├── bookings_router.py — CRUD מלא
├── booking_lifecycle_router.py — lifecycle events
├── booking_checkin_router.py — checkin/checkout transitions
├── booking_history_router.py — history trail
├── booking_guest_link_router.py — guest linkage
├── amendments_router.py — booking amendments
├── conflicts_router.py — double-booking conflict resolution
├── availability_router.py — calendar availability
├── channel_map_router.py — OTA channel mapping
├── financial_*.py — 6 financial routers!
├── outbound sync — adapters for pushing to OTAs
└── audit trail — full event logging
```

### ❌ מה חסר:
| פיצ'ר | סטטוס |
|-------|-------|
| Manual Booking (by manager) | חסר — אין API ליצירת booking ידני |
| Booking Source = "self-use" / "owner" | חסר |
| Selective Task Opt-Out (no cleaning for self-use) | חסר |
| Pre-arrival email trigger | `pre_arrival_scanner.py` **קיים** ✅ |
| OTA date blocking on manual booking | חסר |

### 🔵 מה יש יותר מדי (relative to vision):
- **6 financial routers** — מתקדם מעבר ל-MVP
- **Conflict auto-resolver** — complex, MVP doesn't need it
- **Price deviation detector** — not in vision
- **Cashflow projections** — advanced, owner portal will use this
- **Financial corrections/reconciliation** — advanced

> [!NOTE]
> זה **לא "יותר מדי"** — זה מתקדם. הכל שימושי, פשוט לא קריטי ל-MVP.

---

## 4. ✅ Check-in / Check-out

### ✅ מה יש:
```
booking_checkin_router.py (Phase 398):
├── POST /bookings/{id}/checkin → active → checked_in
├── POST /bookings/{id}/checkout → checked_in → checked_out
├── Creates CLEANING task on checkout ✅
├── Audit events ✅
└── Idempotent ✅
```

### ❌ מה חסר (מהחזון):
| פיצ'ר | סטטוס | עדיפות |
|-------|--------|-------|
| 📋 Guest Form (name, passport, phone) | חסר | 🔴 Critical |
| 📸 Passport photo capture (per guest) | חסר | 🔴 Critical |
| 👤 Guest Type selector (Tourist/Resident) | חסר | 🟡 High |
| 🌐 Form language selection (EN/TH/HE) | חסר | 🟡 High |
| 💰 Deposit collection (amount + photo) | חסר | 🟡 High |
| 💰 Deposit return + **deductions doc** | חסר | 🟡 High |
| 📱 QR Code generation → guest portal | חסר | 🔴 Critical |
| ✍️ Digital signature | חסר | 🟢 Medium |
| 📧 Pre-arrival form link (email) | חסר | 🟡 High |
| 📸 Reference photos at checkout (comparison) | חסר | 🟡 High |
| Worker ID tracking (who did the checkin) | חסר | 🟡 High |

---

## 5. 📋 Task System

### ✅ מה יש (מתקדם!):
```
task_model.py (Phase 111):
├── 6 TaskKinds: CLEANING, CHECKIN_PREP, CHECKOUT_VERIFY,
│                MAINTENANCE, GENERAL, GUEST_WELCOME
├── 5 WorkerRoles: CLEANER, PROPERTY_MANAGER, MAINTENANCE_TECH,
│                  INSPECTOR, GENERAL_STAFF
├── 4 Priorities: LOW, MEDIUM, HIGH, CRITICAL
├── SLA engine: 5-min CRITICAL ACK ✅
├── State machine: PENDING → ACKNOWLEDGED → IN_PROGRESS → COMPLETED

task_automator.py (Phase 112):
├── BOOKING_CREATED → CHECKIN_PREP + CLEANING tasks ✅
├── BOOKING_CANCELED → Cancel PENDING tasks ✅
├── BOOKING_AMENDED → Reschedule tasks ✅

task_writer.py — persistence layer ✅
sla_engine.py — SLA monitoring + escalation ✅
Channels: LINE, WhatsApp, Telegram, SMS, Email ✅
```

### ❌ מה חסר:
| פיצ'ר | סטטוס | עדיפות |
|-------|--------|-------|
| 📋 Cleaning Checklist (per property) | חסר | 🔴 Critical |
| 📸 Mandatory photo per room | חסר | 🔴 Critical |
| 📦 Supply check (sheets, towels, soap) | חסר | 🔴 Critical |
| ⛔ "Complete" blocked until all done | חסר | 🔴 Critical |
| 📸 Reference photo comparison | חסר | 🟡 High |
| ⚠️ Problem Reporting (from task) | **Backend built** (Phase 598 + 647–652). Auto-creates MAINTENANCE task. | 🟡 UI needed |
| 🔀 Task Take-Over (Ops Manager) | חסר | 🟡 High |
| 📍 Navigate to property (GPS link) | חסר | 🟡 High |
| 🧹 CHECKOUT task auto-creation | **Partial** — created on checkout API call | 🟡 |
| Worker ID per action | חסר | 🟡 High |
| Task calendar view (worker sees upcoming) | חסר | 🟡 High |

### 🔵 מה יש ולא בחזון (אבל שימושי):
- `GUEST_WELCOME` task kind — **יתחבר ל-QR Portal**: ה-task הזה בעצם הוא מה שמוביל ליצירת ה-QR + פתיחת הפורטל לאורח
- `INSPECTOR` role — החזון משתמש ב-"Check-in/out Worker" במקום
- `GENERAL` task kind — catch-all, שימושי

---

## 6. 📱 Guest QR Portal

### ✅ מה יש:
```
guest_portal.py (Phase 262):
├── GuestBookingView dataclass:
│   ├── booking_ref, property_name, property_address ✅
│   ├── check_in_date, check_out_date ✅
│   ├── check_in_time, check_out_time ✅
│   ├── wifi_name, wifi_password ✅
│   ├── access_code ✅
│   ├── house_rules ✅
│   ├── emergency_contact ✅
│   ├── guest_name, nights, status ✅
│
├── Token-gated access (no auth middleware) ✅
├── Stub lookup (CI-safe) ✅
└── guest_token.py — token validation service ✅
```

### ❌ מה חסר:
| פיצ'ר | סטטוס | עדיפות |
|-------|--------|-------|
| 🛍️ Extras listing (per property) | חסר | 🔴 Critical |
| 🛍️ Order Extra → alert to manager | חסר | 🔴 Critical |
| 💬 Chat with manager | חסר | 🟡 High |
| 📱 WhatsApp link | חסר | 🟡 High |
| 📍 Location on map (GPS) | חסר | 🟡 High |
| ❄️ AC Instructions link | חסר | 🟢 Medium |
| 🚿 Hot Water Instructions | חסר | 🟢 Medium |
| 📱 QR Code generation endpoint | חסר | 🔴 Critical |
| 🌐 Multi-language portal | חסר | 🟡 High |

---

## 7. 👁️ Owner Portal

### ✅ מה יש (חזק!):
```
owner_portal_data.py (Phase 301):
├── Booking counts by status ✅
├── Upcoming bookings (next 5) ✅
├── Recent bookings (30 days) ✅
├── Financial summary (90 days): gross, net, fees, commission ✅
├── Occupancy rate (30 days) ✅
├── Role-based: financials only for role="owner" ✅
└── Rich summary combining all above ✅
```

### ❌ מה חסר:
| פיצ'ר | סטטוס | עדיפות |
|-------|--------|-------|
| Per-field visibility toggles (Admin configures) | חסר | 🟡 High |
| "Transparency slider" (50%-100%) | חסר | 🟡 High |
| Maintenance reports + photos for owner | חסר | 🟢 Medium |
| Guest reviews visibility | חסר | 🟢 Medium |
| Cleaning status visibility | חסר | 🟢 Medium |
| Owner login (separate auth) | חסר | 🟡 High |

---

## 8. ⚠️ Problem Reporting — Backend Built (Phases 598, 647–652)

> **Update (2026-03-28):** This section previously said "חסר לגמרי" (0%). That was wrong.
> The backend was built across Phases 598, 647–652. See `src/api/problem_report_router.py`.

### ✅ מה יש:
```
├── problem_report_router.py — 6 endpoints (POST/GET/PATCH + photos)
├── 14 categories (pool, plumbing, electrical, ac_heating, ...)
├── 4 statuses (open, in_progress, resolved, dismissed)
├── Auto-create MAINTENANCE task (Phase 648) — urgent→CRITICAL, normal→MEDIUM
├── SSE alert on urgent reports (Phase 651) — PROBLEM_URGENT event
├── Audit event on status change (Phase 650) — PROBLEM_REPORT_STATUS_CHANGED
├── Category→specialty routing (Phase 652)
├── i18n labels (Phase 652) — EN/TH/HE for 14 categories
├── DB: problem_reports + problem_report_photos tables (RLS enabled)
├── Frontend: /ops/maintenance page calls these endpoints
└── Mounted in main.py (always active, no feature flag)
```

### ❌ מה חסר:
| פיצ'ר | סטטוס | עדיפות |
|-------|--------|-------|
| Admin UI — cross-property report dashboard | חסר | 🟡 High |
| Photo Storage pipeline (Supabase Storage upload) | לא מאומת | 🟡 High |
| RLS policy verification on problem_reports | לא מאומת | 🟡 High |
| Auto-translate (description_original_lang) | שדה קיים, pipeline חסר | 🟢 Medium |

**עדיפות: 🟡 High (backend done, UI + storage gaps remain)**

---

## 9. 🛍️ Guest Extras — חסר לגמרי

צריך לבנות מאפס:
```
├── Extras catalog (admin-defined per property)
├── DB tables: extras, property_extras
├── Guest portal: list extras + order button
├── Order → alert to manager
├── Order tracking (status: requested → confirmed → delivered)
└── Admin UI: manage extras catalog
```
**עדיפות: 🟡 High (not MVP-blocking)**

---

## 10. 🔧 Maintenance Worker

### ✅ מה יש:
```
├── TaskKind.MAINTENANCE exists ✅
├── WorkerRole.MAINTENANCE_TECH exists ✅
└── Can receive tasks via notification channels ✅
```

### ❌ מה חסר:
```
├── Split by specialty (pool, plumbing, electrical)
├── External worker limited access
├── Dedicated dashboard / task list
├── Photo evidence (before/after)
└── Task push from Admin/Ops (for external)
```

---

## 11. 🌍 i18n / Internationalization

### ✔️ מה יש:
```
├── i18n/language_pack.py — basic structure ✅
└── Channels support multiple chat platforms ✅
```

### ❌ מה חסר:
```
├── Guest form language selection (EN/TH/HE)
├── Cleaner UI in Thai
├── Auto-translate (Thai → English for reports)
├── Guest portal multi-language
└── Full string catalog (not just packs)
```

### 📊 Language Roadmap:
```
🟢 MVP:     English 🇬🇧 + Thai 🇹🇭 + Hebrew 🇮🇱
🟡 Wave 2:  Russian 🇷🇺 + Italian 🇮🇹 + Spanish 🇪🇸
🟠 Wave 3:  Chinese 🇨🇳 + Japanese 🇯🇵 + Korean 🇰🇷
```

---

## 12. 📋 סיכום — מה לעשות ובאיזה סדר

### 🔴 Phase A — Core MVP (שבלעדי זה אין מוצר)

| # | מה | הנקודה |
|---|-----|--------|
| A1 | Property: GPS + Reference Photos + Check-in/out times + Deposit | שדות חדשים ב-properties table |
| A2 | Guest Check-in Form (Tourist/Resident, passport photo, deposit) | API + Model חדש |
| A3 | QR Code Generation → Guest Portal link | Endpoint חדש |
| A4 | Cleaning Checklist (per property, mandatory photos, supply check) | Model + API חדש |
| A5 | Problem Reporting — **Admin UI + photo storage** | Backend built (Phases 598, 647–652). Needs admin dashboard + storage pipeline |
| A6 | Guest Portal: extras + chat | הרחבת guest_portal.py |
| A7 | Manual Booking (by manager, with task opt-out) | Endpoint חדש |

### 🟡 Phase B — Essential but not blocking

| # | מה |
|---|-----|
| B1 | Bulk Import Wizard (One-Click Connect, CSV, iCal) |
| B2 | Owner Portal: configurable transparency toggles |
| B3 | Task Take-Over (Ops Manager) |
| B4 | Worker IDs (unique, tracked per action) |
| B5 | i18n: Thai + English + Hebrew |
| B6 | Pre-arrival email with form link |

### 🟢 Phase C — Polish & Scale

| # | מה |
|---|-----|
| C1 | Maintenance split by specialty |
| C2 | External maintenance worker (limited access) |
| C3 | Guest Extras ordering + tracking |
| C4 | Auto-translate (Thai → English) |
| C5 | Property amenities import from OTA |
| C6 | Deposit dispute flow (at checkout) |
| C7 | Country-specific forms (Spain SES when expanding) |

---

## 13. 💡 מה שיש לנו ולא בחזון — אבל שווה לשמור

| מה יש | למה שווה לשמור |
|-------|----------------|
| Financial dashboards (6 routers!) | Owner Portal ישתמש בזה |
| Conflict auto-resolver | מונע double bookings |
| SLA engine (5-min CRITICAL) | Core operational discipline |
| Event sourcing architecture | Audit trail, history, replay |
| SSE real-time broker | Live dashboard updates |
| AI copilot (LLM service) | Future automation layer |
| Price deviation detector | Owner alerts |
| Outbound sync (rate-limit + retry) | OTA date blocking |

> [!IMPORTANT]
> **iHouse Core הוא הרבה יותר מתקדם ארכיטקטונית מחזון המוצר.**
> 
> הבעיה: האדריכלות מעולה, אבל ה-**"last mile"** — הדברים שהמשתמש נוגע בהם (טפסים, צ'קליסטים, תמונות, QR) — עדיין לא בנויים.
> 
> **המשימה**: לחבר את האינפרה המתקדמת שיש לנו ← אל פני המשתמש (worker app, guest portal, admin dashboard).
