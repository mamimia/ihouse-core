# 🗺️ Master Implementation Roadmap
## Domaniqo Product Vision → iHouse Core
### 172 Phases — Phases 586–757

> [!IMPORTANT]
> הספר הגדול. כל phase מפורט, בסדר כרונולוגי הגיוני. תלות בין phases מצוינת. כל wave בנויה כך שאפשר לעצור בסופה ולהראות מוצר עובד.

---

## 📊 Overview

| Wave | שם | Phases | מה נבנה | תלוי ב- |
|------|-----|--------|---------|---------|
| 1 | 🏗️ Foundation | 586–605 | DB schema, Worker IDs, Property fields | — |
| 2 | 📋 Guest Check-in | 606–625 | Form, Passport, Deposit, QR | Wave 1 |
| 3 | 🧹 Task Enhancement | 626–645 | Checklists, Photos, Supply check | Wave 1 |
| 4 | ⚠️ Problem Reporting | 646–665 | Full module from scratch | Wave 1, 3 |
| 5 | 🛍️ Guest Portal & Extras | 666–685 | Extras, Chat, Multi-language | Wave 1, 2 |
| 6 | 🚪 Checkout & Deposit | 686–705 | Settlement doc, Deductions, Photos | Wave 2, 3 |
| 7 | 📝 Manual Booking & Take-Over | 706–720 | Manual booking, Task take-over | Wave 1, 3 |
| 8 | 👁️ Owner Portal & Maintenance | 721–735 | Transparency, Specialists | Wave 1 |
| 9 | 🌍 i18n | 736–745 | EN/TH/HE, Auto-translate | Wave 4, 5 |
| 10 | 🚀 Bulk Import Wizard | 746–757 | OTA connect, CSV, iCal, Dedup | Wave 1 |

---

## 🔌 Existing Infrastructure — שימוש חוזר

> לפני שבונים, הנה מה שכבר יש שנשתמש בו:

| Module קיים | איפה נשתמש |
|-------------|------------|
| `task_automator.py` + `task_model.py` | הרחבה — checklists, photos, take-over |
| `sla_engine.py` | SLA for problem reports + maintenance |
| `guest_portal.py` + `guest_token.py` | הרחבה — extras, chat, QR |
| `onboarding_router.py` (3-step wizard) | הרחבה — GPS, photos, times, deposit |
| `booking_checkin_router.py` | הרחבה — guest form, passport, deposit |
| `owner_portal_data.py` | הרחבה — visibility toggles |
| `pre_arrival_scanner.py` | Pre-arrival email with form link |
| `channels/` (LINE/WhatsApp/Telegram/SMS/Email/SSE) | Alerts, guest chat, worker notifications |
| `financial_*.py` (6 routers) | Owner portal financial data |
| `outbound_sync_*.py` | OTA date blocking for manual bookings |
| `conflict_scanner.py` + `conflict_auto_resolver.py` | Double-booking prevention |
| `audit_writer.py` + `event_log.py` | Audit trail for every action |
| `i18n/language_pack.py` | Foundation for multi-language |
| `GUEST_WELCOME` TaskKind | → QR Portal trigger |
| `CHECKOUT_VERIFY` TaskKind | → Checkout flow with deposit |

---

# 🏗️ WAVE 1 — Foundation (Phases 586–605)

> DB schema extensions, Worker ID system, Property field enrichment. Everything else builds on this.

---

### Phase 586 — Property Schema Extension: GPS & Location
```
ALTER TABLE properties ADD:
├── latitude        FLOAT
├── longitude       FLOAT
├── gps_saved_at    TIMESTAMPTZ
└── gps_source      TEXT  ('manual' | 'device' | 'geocoded')

API:
├── PATCH /properties/{id} → accepts latitude, longitude
├── POST /properties/{id}/save-location → saves device GPS
└── GET /properties/{id}/location → returns lat/lng + map link

Tests:
├── Contract: save-location returns coordinates
├── Contract: location returns map URL
└── Invariant: lat must be -90 to 90, lng -180 to 180
```

### Phase 587 — Property Schema Extension: Check-in/out Times
```
ALTER TABLE properties ADD:
├── checkin_time     TEXT  DEFAULT '15:00'
├── checkout_time    TEXT  DEFAULT '11:00'

API:
├── PATCH /properties/{id} → accepts checkin_time, checkout_time
└── Include in onboarding step 1

Leverage: onboarding_router.py Step 1 — add fields to insert_data
Tests: Contract: default times are 15:00/11:00
```

### Phase 588 — Property Schema Extension: Deposit Configuration
```
ALTER TABLE properties ADD:
├── deposit_required    BOOLEAN  DEFAULT FALSE
├── deposit_amount      NUMERIC(10,2)
├── deposit_currency    CHAR(3) DEFAULT 'THB'
├── deposit_method      TEXT  DEFAULT 'cash'  ('cash' | 'transfer')

Tests: Invariant: deposit_amount > 0 when deposit_required = true
```

### Phase 589 — Property Schema Extension: House Rules
```
ALTER TABLE properties ADD:
├── house_rules         JSONB  DEFAULT '[]'::jsonb
│   Format: [{"rule": "No smoking", "icon": "🚭"}, ...]

API:
├── PUT /properties/{id}/house-rules → replaces rules array
├── GET /properties/{id}/house-rules → returns rules
└── Use in guest portal (QR) as source of truth

Leverage: guest_portal.py GuestBookingView.house_rules already exists — connect to property source
```

### Phase 590 — Property Schema Extension: Property Details (Extra Info)
```
ALTER TABLE properties ADD:
├── door_code           TEXT
├── key_location        TEXT
├── wifi_name           TEXT
├── wifi_password       TEXT
├── ac_instructions     TEXT
├── hot_water_info      TEXT
├── stove_instructions  TEXT
├── breaker_location    TEXT
├── trash_instructions  TEXT
├── parking_info        TEXT
├── pool_instructions   TEXT
├── laundry_info        TEXT
├── tv_info             TEXT
├── safe_code           TEXT
├── emergency_contact   TEXT
├── extra_notes         TEXT

All optional TEXT fields. Exposed as PATCH /properties/{id}
```

### Phase 591 — Reference Photos Schema & Storage
```
New table: property_reference_photos
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── property_id     TEXT NOT NULL
├── room_label      TEXT NOT NULL  ('bedroom_1', 'kitchen', 'living_room', 'bathroom_1', 'exterior')
├── photo_url       TEXT NOT NULL  (Supabase Storage)
├── display_order   INT DEFAULT 0
├── created_at      TIMESTAMPTZ DEFAULT now()

API:
├── POST /properties/{id}/reference-photos → upload + store
├── GET /properties/{id}/reference-photos → list by room
├── DELETE /properties/{id}/reference-photos/{photo_id}
└── Storage: Supabase Storage bucket 'reference-photos'

Tests: Upload returns URL, list returns sorted by display_order
```

### Phase 592 — Marketing Photos Schema
```
New table: property_marketing_photos
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── property_id     TEXT NOT NULL
├── photo_url       TEXT NOT NULL
├── caption         TEXT
├── source          TEXT  ('upload' | 'airbnb' | 'booking')
├── display_order   INT DEFAULT 0
├── created_at      TIMESTAMPTZ DEFAULT now()

API: same pattern as reference photos
```

### Phase 593 — Amenities Schema
```
New table: property_amenities
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── property_id     TEXT NOT NULL
├── amenity_key     TEXT NOT NULL  ('wifi', 'ac', 'pool', 'parking', 'washer', 'dryer', 'hair_dryer'...)
├── category        TEXT NOT NULL  ('kitchen', 'bathroom', 'bedroom', 'outdoor', 'entertainment', 'safety')
├── available       BOOLEAN DEFAULT TRUE
├── notes           TEXT
└── UNIQUE(tenant_id, property_id, amenity_key)

Seed: standard amenity catalog (50+ items)
API: POST /properties/{id}/amenities → bulk upsert
     GET /properties/{id}/amenities → grouped by category
```

### Phase 594 — Worker ID System
```
ALTER TABLE users ADD (or verify existing):
├── worker_id       TEXT UNIQUE  (format: 'WRK-001', 'MGR-001', 'CLN-001')
├── worker_role     TEXT  ('admin', 'ops_manager', 'checkin_worker', 'cleaner', 'maintenance', 'general')
├── display_name    TEXT
├── phone           TEXT
├── language        TEXT DEFAULT 'en'  ('en', 'th', 'he')

Auto-generate worker_id on user creation:
├── Admin     → ADM-{seq}
├── Ops Mgr   → MGR-{seq}
├── Worker    → WRK-{seq}
├── Cleaner   → CLN-{seq}
└── Maint     → MNT-{seq}

All task actions now track: performed_by_worker_id
```

### Phase 595 — Worker ID: Action Tracking
```
ALTER TABLE task_actions ADD (or create):
├── id              UUID PK
├── task_id         TEXT NOT NULL
├── action          TEXT NOT NULL  ('created', 'acknowledged', 'started', 'completed', 'canceled', 'taken_over', 'photo_added', 'checklist_item_done')
├── performed_by    TEXT NOT NULL  (worker_id)
├── payload         JSONB
├── occurred_at     TIMESTAMPTZ DEFAULT now()

Every task state change = new row in task_actions
Leverage: audit_writer.py pattern
```

### Phase 596 — Extras Catalog Schema
```
New table: extras_catalog
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── name            TEXT NOT NULL
├── description     TEXT
├── icon            TEXT   (emoji)
├── default_price   NUMERIC(10,2)
├── currency        CHAR(3) DEFAULT 'THB'
├── category        TEXT  ('transport', 'food', 'wellness', 'activities', 'services', 'other')
├── is_system       BOOLEAN DEFAULT FALSE  (pre-built vs custom)
├── active          BOOLEAN DEFAULT TRUE
├── created_at      TIMESTAMPTZ DEFAULT now()

Seed data (pre-built catalog):
├── 🏍️ Motorbike Rental (transport, ฿350/day)
├── 🚗 Car Rental (transport, ฿1,500/day)
├── 💆 Thai Massage (wellness, ฿500)
├── 👨‍🍳 Private Chef (food, ฿2,500)
├── 🧺 Laundry Service (services, ฿200/bag)
├── 🤿 Snorkeling Trip (activities, ฿800)
├── ⏰ Late Checkout (services, ฿500)
├── 🚐 Island Tour (activities, ฿1,500)
├── 🎣 Deep Sea Fishing (activities, ฿3,000)
├── 🧘 Yoga Class (wellness, ฿400)
├── 🍕 Food Delivery (food, ฿0 — varies)
├── 🛵 Scooter Rental (transport, ฿250/day)
├── 🏄 Surfing Lesson (activities, ฿1,200)
├── 🎉 Party Setup (services, ฿5,000)
└── 📸 Photography Session (services, ฿3,000)
```

### Phase 597 — Property-Extras Mapping
```
New table: property_extras
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── property_id     TEXT NOT NULL
├── extra_id        UUID REFERENCES extras_catalog(id)
├── price_override  NUMERIC(10,2)  (NULL = use catalog default)
├── active          BOOLEAN DEFAULT TRUE
├── notes           TEXT
└── UNIQUE(tenant_id, property_id, extra_id)

API:
├── POST /properties/{id}/extras → enable extras for property
├── GET /properties/{id}/extras → list active extras
├── PATCH /properties/{id}/extras/{extra_id} → override price, toggle
└── DELETE → deactivate
```

### Phase 598 — Problem Report Schema
```
New table: problem_reports
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── property_id     TEXT NOT NULL
├── booking_id      TEXT   (optional — may not be during a booking)
├── reported_by     TEXT NOT NULL  (worker_id)
├── category        TEXT NOT NULL ENUM:
│   'pool', 'plumbing', 'electrical', 'ac_heating', 'furniture',
│   'structure', 'tv_electronics', 'bathroom', 'kitchen',
│   'garden_outdoor', 'pest', 'cleanliness', 'security', 'other'
├── description     TEXT NOT NULL
├── description_original_lang  TEXT  (original language code)
├── description_translated     TEXT  (auto-translated)
├── priority        TEXT DEFAULT 'normal'  ('urgent' | 'normal')
├── status          TEXT DEFAULT 'open'  ('open' | 'in_progress' | 'resolved' | 'dismissed')
├── resolved_by     TEXT   (worker_id)
├── resolved_at     TIMESTAMPTZ
├── resolution_notes TEXT
├── maintenance_task_id  TEXT  (auto-created task reference)
├── created_at      TIMESTAMPTZ DEFAULT now()
├── updated_at      TIMESTAMPTZ DEFAULT now()

New table: problem_report_photos
├── id              UUID PK
├── report_id       UUID REFERENCES problem_reports(id)
├── photo_url       TEXT NOT NULL
├── caption         TEXT
├── created_at      TIMESTAMPTZ DEFAULT now()
```

### Phase 599 — Guest Form Schema
```
New table: guest_checkin_forms
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── booking_id      TEXT NOT NULL
├── property_id     TEXT NOT NULL
├── form_status     TEXT DEFAULT 'pending'  ('pending', 'partial', 'completed')
├── guest_type      TEXT DEFAULT 'tourist'  ('tourist', 'resident')
├── form_language   TEXT DEFAULT 'en'  ('en', 'th', 'he')
├── filled_by       TEXT  ('worker' | 'guest_pre_arrival' | 'both')
├── worker_id       TEXT  (who completed the form)
├── submitted_at    TIMESTAMPTZ
├── created_at      TIMESTAMPTZ DEFAULT now()

New table: guest_checkin_guests
├── id              UUID PK
├── form_id         UUID REFERENCES guest_checkin_forms(id)
├── guest_number    INT  (1 = primary, 2+)
├── full_name       TEXT NOT NULL
├── nationality     TEXT
├── document_type   TEXT  ('passport' | 'thai_id')
├── document_number TEXT
├── passport_photo_url  TEXT  (Supabase Storage)
├── phone           TEXT
├── email           TEXT
├── is_primary      BOOLEAN DEFAULT FALSE

New table: guest_deposit_records
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── booking_id      TEXT NOT NULL
├── property_id     TEXT NOT NULL
├── amount          NUMERIC(10,2) NOT NULL
├── currency        CHAR(3) DEFAULT 'THB'
├── status          TEXT DEFAULT 'collected'
│   ('collected', 'full_return', 'partial_return', 'forfeited')
├── cash_photo_url  TEXT
├── collected_by    TEXT  (worker_id)
├── collected_at    TIMESTAMPTZ
├── returned_by     TEXT  (worker_id)
├── returned_at     TIMESTAMPTZ
├── refund_amount   NUMERIC(10,2)
├── signature_url   TEXT  (digital signature image)
├── created_at      TIMESTAMPTZ DEFAULT now()

New table: deposit_deductions
├── id              UUID PK
├── deposit_id      UUID REFERENCES guest_deposit_records(id)
├── description     TEXT NOT NULL
├── amount          NUMERIC(10,2) NOT NULL
├── category        TEXT  ('electricity', 'damage', 'cleaning', 'laundry', 'other')
├── photo_url       TEXT  (evidence)
├── created_at      TIMESTAMPTZ DEFAULT now()
```

### Phase 600 — Cleaning Checklist Schema
```
New table: cleaning_checklist_templates
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── property_id     TEXT  (NULL = global template)
├── name            TEXT DEFAULT 'Standard Cleaning'
├── items           JSONB NOT NULL
│   Format: [
│     {"room": "bedroom_1", "label": "Change sheets", "label_th": "เปลี่ยนผ้าปูที่นอน", "requires_photo": true},
│     {"room": "bedroom_1", "label": "Change pillowcases", "label_th": "เปลี่ยนปลอกหมอน", "requires_photo": false},
│     {"room": "bathroom_1", "label": "Check soap/shampoo", "label_th": "ตรวจสบู่/แชมพู", "requires_photo": false},
│     ...
│   ]
├── supply_checks   JSONB
│   Format: [
│     {"item": "sheets", "label": "Enough sheets?", "label_th": "ผ้าปูที่นอนเพียงพอ?"},
│     {"item": "towels", "label": "Enough towels?", "label_th": "ผ้าขนหนูเพียงพอ?"},
│     ...
│   ]
├── created_at      TIMESTAMPTZ DEFAULT now()

New table: cleaning_task_progress
├── id              UUID PK
├── task_id         TEXT NOT NULL
├── tenant_id       TEXT NOT NULL
├── booking_id      TEXT NOT NULL
├── property_id     TEXT NOT NULL
├── template_id     UUID REFERENCES cleaning_checklist_templates(id)
├── checklist_state JSONB  (tracks each item: done/not done)
├── supply_state    JSONB  (tracks each supply check)
├── all_photos_taken BOOLEAN DEFAULT FALSE
├── all_items_done   BOOLEAN DEFAULT FALSE
├── all_supplies_ok  BOOLEAN DEFAULT FALSE
├── completed_at    TIMESTAMPTZ
├── worker_id       TEXT

New table: cleaning_photos
├── id              UUID PK
├── progress_id     UUID REFERENCES cleaning_task_progress(id)
├── room_label      TEXT NOT NULL
├── photo_url       TEXT NOT NULL
├── taken_by        TEXT  (worker_id)
├── taken_at        TIMESTAMPTZ DEFAULT now()
```

### Phase 601 — Extra Orders Schema
```
New table: extra_orders
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── booking_id      TEXT NOT NULL
├── property_id     TEXT NOT NULL
├── extra_id        UUID REFERENCES extras_catalog(id)
├── guest_token     TEXT
├── quantity         INT DEFAULT 1
├── unit_price      NUMERIC(10,2)
├── currency        CHAR(3)
├── status          TEXT DEFAULT 'requested'
│   ('requested', 'confirmed', 'in_progress', 'delivered', 'canceled')
├── notes           TEXT  (guest notes)
├── handled_by      TEXT  (worker_id)
├── requested_at    TIMESTAMPTZ DEFAULT now()
├── confirmed_at    TIMESTAMPTZ
├── delivered_at    TIMESTAMPTZ
```

### Phase 602 — Guest Chat Schema
```
New table: guest_messages
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── booking_id      TEXT NOT NULL
├── property_id     TEXT NOT NULL
├── sender_type     TEXT NOT NULL  ('guest' | 'manager')
├── sender_id       TEXT  (guest_token or worker_id)
├── message         TEXT NOT NULL
├── read_at         TIMESTAMPTZ
├── created_at      TIMESTAMPTZ DEFAULT now()

Leverage: existing guest_messages_router.py — extend it
```

### Phase 603 — Maintenance Specialists Schema
```
New table: maintenance_specialties
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── specialty_key   TEXT NOT NULL  ('pool', 'plumbing', 'electrical', 'painting', 'furniture', 'gardening', 'general')
├── display_name    TEXT NOT NULL
├── display_name_th TEXT
├── icon            TEXT  (emoji)
├── active          BOOLEAN DEFAULT TRUE

New table: worker_specialties
├── worker_id       TEXT NOT NULL
├── specialty_id    UUID REFERENCES maintenance_specialties(id)
├── tenant_id       TEXT NOT NULL
└── PRIMARY KEY (worker_id, specialty_id)

Behavior:
├── If worker has 0 specialties → sees ALL maintenance tasks (small biz)
├── If worker has 1+ specialties → sees ONLY matching tasks (big biz)
└── Admin toggle determines which mode

ALTER TABLE properties ADD:
├── maintenance_mode  TEXT DEFAULT 'single'  ('single' | 'specialists')
```

### Phase 604 — Owner Visibility Schema
```
New table: owner_visibility_settings
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── owner_user_id   TEXT NOT NULL
├── property_id     TEXT NOT NULL
├── visible_fields  JSONB NOT NULL DEFAULT '{
│     "booking_count": true,
│     "occupancy_calendar": true,
│     "guest_names": true,
│     "price_per_night": false,
│     "revenue": false,
│     "cleaning_status": true,
│     "maintenance_reports": true,
│     "operational_costs": false,
│     "guest_reviews": true,
│     "worker_details": false
│   }'
├── created_at      TIMESTAMPTZ DEFAULT now()
├── updated_at      TIMESTAMPTZ DEFAULT now()
└── UNIQUE(tenant_id, owner_user_id, property_id)
```

### Phase 605 — QR Token & Manual Booking Schema
```
New table: guest_qr_tokens
├── id              UUID PK
├── tenant_id       TEXT NOT NULL
├── booking_id      TEXT NOT NULL
├── property_id     TEXT NOT NULL
├── token           TEXT UNIQUE NOT NULL  (short unique token)
├── generated_by    TEXT  (worker_id)
├── portal_url      TEXT  (full URL to guest portal)
├── expires_at      TIMESTAMPTZ  (check_out_date + 1 day)
├── created_at      TIMESTAMPTZ DEFAULT now()

ALTER TABLE booking_state ADD:
├── booking_source     TEXT DEFAULT 'ota'
│   ('ota', 'direct', 'self_use', 'owner_use', 'maintenance_block')
├── tasks_opt_out      JSONB DEFAULT '[]'  (['checkin', 'cleaning'])
```

---

# 📋 WAVE 2 — Guest Check-in System (Phases 606–625)

---

### Phase 606 — Guest Check-in Form: Core API
```
POST /bookings/{booking_id}/checkin-form
├── Creates guest_checkin_forms record
├── Accepts: guest_type, form_language
├── Returns form_id + pre-filled fields (from booking data)
└── Leverage: booking_checkin_router.py

GET /bookings/{booking_id}/checkin-form
├── Returns current form state (for pre-arrival partial fill)
```

### Phase 607 — Guest Check-in Form: Add Guests
```
POST /checkin-forms/{form_id}/guests
├── Add guest details (name, nationality, document)
├── Supports multiple guests per form
├── Guest 1 = primary (is_primary = true)
├── Pre-fills from booking data if available
```

### Phase 608 — Guest Check-in Form: Passport Photo Upload
```
POST /checkin-forms/{form_id}/guests/{guest_id}/passport-photo
├── Upload passport photo to Supabase Storage
├── Store URL in guest_checkin_guests.passport_photo_url
├── Storage bucket: 'passport-photos' (private, not public)
├── Auto-delete after checkout + 30 days (privacy)
```

### Phase 609 — Guest Check-in Form: Tourist vs Resident Logic
```
When guest_type = 'tourist':
├── Required: full_name, nationality, passport_number, passport_photo, phone
├── document_type forced to 'passport'

When guest_type = 'resident':
├── Required: full_name, thai_id_number, id_photo, phone
├── document_type forced to 'thai_id'
├── Nationality not required (assumed Thai)
```

### Phase 610 — Guest Check-in Form: Deposit Collection
```
POST /bookings/{booking_id}/deposit
├── IF property.deposit_required = true:
│   ├── amount = property.deposit_amount
│   ├── currency = property.deposit_currency
│   ├── Cash photo upload
│   ├── collected_by = current worker_id
│   └── Creates guest_deposit_records entry
├── IF deposit_required = false:
│   └── Skip silently
```

### Phase 611 — Guest Check-in Form: Digital Signature
```
POST /checkin-forms/{form_id}/signature
├── Accept base64 signature image
├── Store in Supabase Storage
├── Link to form record
├── Optional — not blocking for completion
```

### Phase 612 — Guest Check-in Form: Submit & Complete
```
POST /checkin-forms/{form_id}/submit
├── Validates: all required fields filled
├── Validates: at least 1 guest with passport/ID photo
├── Validates: deposit collected (if required)
├── Sets form_status = 'completed'
├── Sets submitted_at = now()
├── Triggers: QR code generation (Phase 613)
├── Leverage: uses existing checkin_booking() to set status = checked_in
```

### Phase 613 — QR Code Generation
```
POST /bookings/{booking_id}/generate-qr
├── Pre-condition: checkin form completed
├── Generates unique short token (nanoid, 12 chars)
├── Creates guest_qr_tokens record
├── Builds portal URL: https://app.domaniqo.com/guest/{token}
├── Returns: QR code image (base64) + portal URL
├── Worker shows QR on their phone → guest scans
```

### Phase 614 — Pre-Arrival Email: Form Link
```
Enhance existing pre_arrival_scanner.py:
├── When booking is created + email available:
│   ├── Generate pre-arrival token (limited scope — form only)
│   ├── Build email:
│   │   "Hi {name}! Your check-in is on {date}.
│   │    Fill out your details now: {link}
│   │    Or complete it when you arrive!"
│   └── Send via email_sender.py
├── Guest fills form → sets form_status = 'partial'
├── Worker completes remaining (photo, deposit, signature)

Leverage: pre_arrival_scanner.py already exists + email_sender.py
```

### Phase 615 — Pre-Arrival Form: Guest Self-Service
```
GET /guest/pre-arrival/{token}
├── Public endpoint (no JWT — token-gated)
├── Returns: form fields, property name, dates
├── Guest fills: name, nationality, document number, phone, email

POST /guest/pre-arrival/{token}
├── Saves partial form data
├── Sets form_status = 'partial'
├── Worker sees what's pre-filled, completes the rest
```

### Phase 616 — Guest Form: Language Selection
```
Form accepts form_language parameter:
├── 'en' → English labels
├── 'th' → Thai labels (ภาษาไทย)
├── 'he' → Hebrew labels (עברית)

All form field labels stored in i18n system
Form validation messages also localized
```

### Phase 617 — Enhance booking_checkin_router: Wire to Guest Form
```
Modify POST /bookings/{id}/checkin:
├── Before allowing checkin: verify guest form is 'completed'
│   (or allow bypass with force=true for manager)
├── Link checkin event to worker_id who performed it
├── Include form_id in audit event payload
```

### Phase 618 — Enhance booking_checkin_router: Wire to QR
```
After successful checkin:
├── Auto-generate QR if not already exists
├── Return qr_token + portal_url in response
├── Worker app shows QR to guest
```

### Phase 619–625 — Guest Check-in: Tests & Edge Cases
```
619: Contract tests — form CRUD, guest CRUD, photo upload
620: Contract tests — deposit collection, signature
621: Contract tests — QR generation, pre-arrival token
622: E2E test — full flow: create form → add guests → passport → deposit → sign → submit → QR
623: Edge: pre-arrival partial fill → worker completes
624: Edge: multiple guests (5 passports)
625: Edge: resident (Thai ID) vs tourist (passport) form differences
```

---

# 🧹 WAVE 3 — Task System Enhancement (Phases 626–645)

---

### Phase 626 — Cleaning Checklist: Template CRUD
```
POST /properties/{id}/cleaning-checklist → create/update template
GET /properties/{id}/cleaning-checklist → get template
├── If no property-specific template → return global default
├── Template includes: items (per room) + supply checks
├── Each item has: label (en) + label_th + requires_photo flag
```

### Phase 627 — Cleaning Checklist: Default Template Seeder
```
Seed a standard global template with:
├── Bedroom: change sheets, pillowcases, clean room, photo
├── Bathroom: clean, check soap/shampoo, clean towels, photo
├── Kitchen: counters, stove, trash, photo
├── Living Room: clean + organize, photo
├── Storage: sheets check, towels check, soap check, TP check, photo
└── All items have EN + TH labels

Leverage: task_template_seeder.py already exists — extend it
```

### Phase 628 — Cleaning Task: Progress Tracking API
```
POST /tasks/{task_id}/start-cleaning
├── Creates cleaning_task_progress record
├── Links to template_id (property or global)
├── Initializes checklist_state from template items
├── Sets task status → IN_PROGRESS
├── Records worker_id

PATCH /tasks/{task_id}/cleaning-progress
├── Update checklist_state: mark individual items done
├── Recalculate: all_items_done flag
```

### Phase 629 — Cleaning Task: Room Photo Upload
```
POST /tasks/{task_id}/cleaning-photos
├── Upload photo for specific room_label
├── Store in cleaning_photos table + Supabase Storage
├── Recalculate: all_photos_taken flag
├── Track: taken_by worker_id + timestamp
```

### Phase 630 — Cleaning Task: Supply Check
```
PATCH /tasks/{task_id}/supply-check
├── Update supply_state for each item (ok / low / empty)
├── If any item = 'empty' → auto-create alert
├── Recalculate: all_supplies_ok flag
```

### Phase 631 — Cleaning Task: Complete Blocking
```
POST /tasks/{task_id}/complete
├── Pre-conditions (ALL must be true):
│   ├── all_items_done = true
│   ├── all_photos_taken = true
│   └── all_supplies_ok = true (or explicitly acknowledged)
├── If any false → return 409 with detail of what's missing
├── If all true → set task status → COMPLETED
├── Records completed_at + worker_id
```

### Phase 632 — Reference Photo Comparison View
```
GET /tasks/{task_id}/reference-vs-cleaning
├── Returns pairs:
│   ├── room: "bedroom_1"
│   │   ├── reference_photo: property_reference_photos URL
│   │   └── cleaning_photo: cleaning_photos URL (or null if not taken)
│   ├── room: "kitchen"
│   │   ├── reference_photo: ...
│   │   └── cleaning_photo: ...
├── Used by: checkout worker to compare "how it should look" vs "how cleaner left it"
```

### Phase 633 — Task: Navigate to Property
```
GET /tasks/{task_id}/navigate
├── Returns: property GPS coordinates + map link
├── Map link format: https://maps.google.com/?q={lat},{lng}
├── Falls back to address if no GPS saved

Leverage: property.latitude, property.longitude from Phase 586
```

### Phase 634 — Task Automator: Add CHECKOUT Task
```
Enhance task_automator.py:
├── BOOKING_CREATED now emits 3 tasks:
│   ├── CHECKIN_PREP (unchanged)
│   ├── CLEANING (unchanged — pre-arrival cleaning)
│   └── CHECKOUT_VERIFY (NEW — due on check_out date)
├── BOOKING_AMENDED: reschedule CHECKOUT_VERIFY too
├── BOOKING_CANCELED: cancel CHECKOUT_VERIFY too

Leverage: TaskKind.CHECKOUT_VERIFY already exists in task_model.py!
```

### Phase 635 — Task: Worker Calendar View
```
GET /workers/{worker_id}/calendar
├── Returns all upcoming tasks for this worker
├── Grouped by date
├── Each task: task_id, kind, property name, due_date, status, priority
├── Sorted by due_date ASC

GET /workers/{worker_id}/tasks/today
├── Returns tasks due today
├── Used for worker mobile app home screen
```

### Phase 636–645 — Task Enhancement: Tests
```
636: Contract tests — checklist CRUD, template seeder
637: Contract tests — cleaning progress, photo upload
638: Contract tests — supply check, complete blocking
639: E2E test — full cleaning flow: template → start → items → photos → supplies → complete
640: E2E test — complete blocked when photo missing
641: Contract tests — navigate returns GPS
642: Contract tests — CHECKOUT_VERIFY task auto-created
643: Contract tests — worker calendar
644: Edge: property with no template → uses global
645: Edge: worker has multiple tasks same day
```

---

# ⚠️ WAVE 4 — Problem Reporting (Phases 646–665)

---

### Phase 646 — Problem Report: Create API
```
POST /properties/{property_id}/problems
├── Body: category, description, priority, booking_id (optional)
├── reported_by = current worker_id (from JWT)
├── Returns: report_id
├── Stores original language code

Leverage: audit_writer.py pattern for event logging
```

### Phase 647 — Problem Report: Photo Upload
```
POST /problems/{report_id}/photos
├── Upload 1+ photos to Supabase Storage
├── Store URLs in problem_report_photos
├── Bucket: 'problem-reports'
```

### Phase 648 — Problem Report: Auto-Create Maintenance Task
```
On problem report creation:
├── If priority = 'urgent':
│   ├── Auto-create MAINTENANCE task
│   │   ├── priority = CRITICAL (5-min ACK SLA!)
│   │   └── Link: maintenance_task_id → task_id
│   ├── Alert → Admin dashboard (SSE)
│   └── Alert → Ops Manager dashboard (SSE)
├── If priority = 'normal':
│   └── Auto-create MAINTENANCE task (priority = MEDIUM)

Leverage: sla_engine.py for escalation!
```

### Phase 649 — Problem Report: List & Filter
```
GET /properties/{property_id}/problems
├── Filter: status, priority, category, date range
├── Pagination
├── Include: photos, reported_by name
├── Sort: newest first (or urgent first)

GET /problems/{report_id}
├── Full detail with photos, linked task, resolution
```

### Phase 650 — Problem Report: Update Status
```
PATCH /problems/{report_id}
├── status → 'in_progress', 'resolved', 'dismissed'
├── resolved_by = worker_id
├── resolution_notes = free text
├── Audit event on status change
```

### Phase 651 — Problem Report: Dashboard Alert (SSE)
```
When urgent problem created:
├── Emit SSE event: { type: 'PROBLEM_URGENT', property_id, report_id, category }
├── Admin + Ops Manager dashboards show real-time alert

Leverage: sse_broker.py already exists!
```

### Phase 652 — Problem Report: Category Icons & Labels
```
Problem category enum with:
├── i18n labels: EN + TH + HE
├── Icons: 🏊🔧⚡❄️🪑🏠📺🚿🍳🌿🐛🧹🔐❓
├── Each category maps to maintenance specialty (for routing)
```

### Phase 653–665 — Problem Reporting: Tests + Edge Cases
```
653: Contract tests — create, photo upload
654: Contract tests — auto-maintenance task creation
655: Contract tests — urgent → SSE alert
656: Contract tests — list, filter, pagination
657: E2E test — report problem → auto task → SLA countdown → escalation
658: E2E test — urgent report → admin dashboard alert
659: Edge: problem without booking (standalone inspection)
660: Edge: multiple photos per report
661-665: RESERVED for iteration & refinements
```

---

# 🛍️ WAVE 5 — Guest Portal & Extras (Phases 666–685)

---

### Phase 666 — Guest Portal: Enhanced Data Model
```
Enhance GuestBookingView (guest_portal.py):
├── Add: extras_available (list of extras for this property)
├── Add: chat_enabled (boolean)
├── Add: property_latitude, property_longitude
├── Add: ac_instructions, hot_water_info, etc.
├── Add: checkout_time (from property)
├── Remove stub data → wire to Supabase

Leverage: guest_portal.py structure already perfect — just add fields
```

### Phase 667 — Guest Portal: Extras Listing
```
GET /guest/{token}/extras
├── Returns extras enabled for this property
├── Each with: name, description, icon, price, currency
├── Reads from: property_extras + extras_catalog
```

### Phase 668 — Guest Portal: Order Extra
```
POST /guest/{token}/extras/order
├── Body: extra_id, quantity, notes
├── Creates extra_orders record
├── Status = 'requested'
├── Alert → Manager (notification via channels)
├── Returns order_id + confirmation
```

### Phase 669 — Extra Order: Manager Actions
```
PATCH /extra-orders/{order_id}
├── Manager: confirm, reject, mark delivered
├── Status transitions: requested → confirmed → delivered | canceled
├── Each change: notification to guest (in portal)
```

### Phase 670 — Guest Portal: Chat (Guest Side)
```
POST /guest/{token}/messages
├── Guest sends message to property manager
├── Stored in guest_messages

GET /guest/{token}/messages
├── Returns conversation history
├── Ordered by created_at

Leverage: guest_messages_router.py already exists — extend
```

### Phase 671 — Guest Portal: Chat (Manager Side)
```
POST /bookings/{booking_id}/guest-messages
├── Manager replies to guest message
├── sender_type = 'manager', sender_id = worker_id

GET /bookings/{booking_id}/guest-messages
├── Returns full conversation (both sides)
├── New messages = SSE event to manager dashboard
```

### Phase 672 — Guest Portal: WhatsApp Link
```
GET /guest/{token}/contact
├── Returns property manager WhatsApp link
├── Format: https://wa.me/{phone}?text=Hi, I'm staying at {property}
├── Also returns: phone number, email
```

### Phase 673 — Guest Portal: Map & Location
```
GET /guest/{token}/location
├── Returns: latitude, longitude, address
├── Map embed URL for display
├── Walking/driving directions link
```

### Phase 674 — Guest Portal: House Info Pages
```
GET /guest/{token}/house-info
├── Returns all house info fields:
│   ac_instructions, hot_water_info, stove_instructions,
│   parking_info, pool_instructions, laundry_info,
│   tv_info, emergency_contact, extra_notes
├── Only non-null fields returned
├── Grouped by category for portal display
```

### Phase 675 — Guest Portal: Multi-Language
```
GET /guest/{token}/portal?lang=th
├── All labels in selected language
├── Property info in original language (with translation option)
├── Extras in original language
├── Initial language = form_language from check-in
```

### Phase 676–685 — Guest Portal: Tests
```
676: Contract — enhanced portal data
677: Contract — extras listing for guest
678: Contract — order extra, manager confirm
679: Contract — guest chat send/receive
680: Contract — WhatsApp link generation
681: Contract — location + map
682: Contract — house info pages
683: E2E — full guest journey: QR → portal → view extras → order → chat
684: Edge — portal after checkout (read-only, no ordering)
685: RESERVED
```

---

# 🚪 WAVE 6 — Checkout & Deposit Settlement (Phases 686–705)

---

### Phase 686 — Checkout: Enhanced Worker View
```
GET /bookings/{booking_id}/checkout-view
├── Returns for checkout worker:
│   ├── Reference photos (from property_reference_photos)
│   ├── Latest cleaning photos (from this booking's cleaning task)
│   ├── Property info (door code, special notes)
│   ├── Deposit info (amount, collected, any existing deductions)
│   └── Guest info (name, number of guests)
```

### Phase 687 — Checkout: Deposit Settlement API
```
POST /bookings/{booking_id}/deposit-settlement
├── IF deposit.status = 'collected':
│   ├── Option A: Full return (no deductions)
│   │   └── deposit.status = 'full_return', refund_amount = original
│   ├── Option B: Partial return (with deductions)
│   │   ├── List of deductions: [{description, amount, category, photo_url}]
│   │   ├── refund_amount = deposit_amount - sum(deductions)
│   │   └── deposit.status = 'partial_return'
│   └── Guest signature on settlement
```

### Phase 688 — Deposit Deductions: CRUD
```
POST /deposits/{deposit_id}/deductions
├── Add deduction item: description, amount, category, photo
├── Recalculate refund_amount automatically

DELETE /deposits/{deposit_id}/deductions/{deduction_id}
├── Remove deduction, recalculate

GET /deposits/{deposit_id}/settlement
├── Returns: original, deductions[], total_deductions, refund_amount
```

### Phase 689 — Checkout: Photo Comparison
```
GET /bookings/{booking_id}/photo-comparison
├── Returns side-by-side:
│   ├── Reference photos (property baseline)
│   ├── Pre-checkin cleaning photos (from this booking)
│   └── Current state (worker takes new photos during checkout)
├── Helps decide: was there damage? → deduction
```

### Phase 690 — Checkout: Complete with Settlement
```
Enhance POST /bookings/{booking_id}/checkout:
├── Pre-check: deposit settlement complete (if deposit exists)
├── Pre-check: problems reported (if any found)
├── Records: checked_out_by = worker_id
├── Auto-create CLEANING task (existing behavior)
├── Audit: full checkout event with deposit settlement details
```

### Phase 691–705 — Checkout: Tests + Edge Cases
```
691: Contract — checkout view returns photos
692: Contract — deposit full return
693: Contract — deposit partial return with deductions
694: Contract — deduction CRUD + refund recalculation
695: Contract — photo comparison API
696: E2E — full checkout: view → deductions → settlement → sign → complete → cleaning task
697: Edge — checkout with no deposit
698: Edge — checkout with zero refund (all deducted)
699-705: RESERVED for iteration
```

---

# 📝 WAVE 7 — Manual Booking & Task Take-Over (Phases 706–720)

---

### Phase 706 — Manual Booking: Create API
```
POST /bookings/manual
├── Body: property_id, check_in, check_out, guest_name,
│         booking_source ('direct', 'self_use', 'owner_use', 'maintenance_block'),
│         tasks_opt_out (['checkin', 'cleaning', 'checkout'] — optional)
├── Creates booking_state record
├── booking_source saved
├── Returns booking_id (internal format: MAN-{property}-{date})
```

### Phase 707 — Manual Booking: OTA Date Blocking
```
On manual booking creation:
├── Trigger outbound sync → block dates on ALL connected OTAs
├── For each channel in channel_map for this property:
│   └── Push availability update: blocked = true

Leverage: outbound_sync_trigger.py + outbound_executor.py already exist!
```

### Phase 708 — Manual Booking: Selective Task Creation
```
On manual booking creation:
├── Read tasks_opt_out from request
├── If 'self_use' or 'owner_use':
│   ├── Show toggle: which tasks to create?
│   ├── Skip tasks listed in tasks_opt_out
│   └── E.g.: skip CHECKIN_PREP, keep CHECKOUT_VERIFY
├── If 'direct':
│   └── Create all tasks (normal behavior)
├── If 'maintenance_block':
│   └── Create NO tasks (just block dates)

Leverage: task_automator.py — add filter logic
```

### Phase 709 — Manual Booking: Cancel & Unblock
```
DELETE /bookings/{booking_id}/manual
├── Cancel booking → cancel all tasks
├── Unblock dates on all OTAs
├── Leverage: outbound_canceled_sync.py
```

### Phase 710 — Task Take-Over: API
```
POST /tasks/{task_id}/take-over
├── Body: reason ('worker_unavailable', 'worker_sick', 'emergency', 'other')
├── Auth: only ops_manager or admin can take over
├── Assigns task to current user (the manager)
├── Original worker's task → status = 'taken_over' (read-only)
├── Creates task_actions record: action='taken_over'
├── Notification to original worker: "Task taken over by {name} ({worker_id})"
```

### Phase 711 — Task Take-Over: Worker Notification
```
When task is taken over:
├── Original worker receives notification:
│   ├── "Task 'Cleaning — Sunset Villa' was taken over by Yossi (MGR-003)"
│   ├── Via their notification channel (LINE/WhatsApp/etc.)
│   └── Task in their app → locked, read-only

Leverage: notification_dispatcher.py + channels/
```

### Phase 712 — Task Take-Over: Manager Gets Full Context
```
After take-over:
├── Manager sees everything the original worker would see:
│   ├── Checklist (if cleaning)
│   ├── Reference photos
│   ├── GPS navigate
│   ├── Guest info (if check-in)
│   └── Problem report form
├── Manager completes task normally
├── Completion recorded with manager's worker_id
```

### Phase 713–720 — Manual Booking & Take-Over: Tests
```
713: Contract — manual booking create
714: Contract — OTA date blocking on manual
715: Contract — selective task opt-out
716: Contract — manual booking cancel + unblock
717: Contract — task take-over API
718: Contract — worker notification on take-over
719: E2E — manual self-use booking → no checkin task → checkout → cleaning
720: E2E — take-over flow: worker MIA → manager takes → completes → system continues
```

---

# 👁️ WAVE 8 — Owner Portal & Maintenance (Phases 721–735)

---

### Phase 721 — Owner Portal: Visibility Toggle API
```
PUT /owners/{owner_id}/properties/{property_id}/visibility
├── Body: visible_fields JSONB (per-field toggles)
├── Upserts owner_visibility_settings
├── Only admin/ops_manager can set this

GET /owners/{owner_id}/properties/{property_id}/visibility
├── Returns current visibility settings
```

### Phase 722 — Owner Portal: Filtered Data API
```
GET /owner-portal/{owner_id}/properties/{property_id}/summary
├── Reads visibility settings for this owner+property
├── Only returns data fields that are enabled
├── Uses existing owner_portal_data.py for data
├── Filters response based on visible_fields

Leverage: get_owner_property_rich_summary() already exists — wrap with filter
```

### Phase 723 — Owner Portal: Maintenance Reports for Owner
```
If visible_fields.maintenance_reports = true:
├── Include in owner summary:
│   ├── Active problem reports for this property
│   ├── Resolved reports (last 30 days)
│   └── Photos (if available)
```

### Phase 724 — Owner Portal: Owner Authentication
```
Owner login — separate from admin:
├── OTP-based (email or phone)
├── Read-only access to assigned properties
├── Uses existing auth patterns but with role = 'owner'

Leverage: auth_router.py + access_token_service.py
```

### Phase 725 — Maintenance: Specialist Sub-Types CRUD
```
POST /maintenance/specialties → create specialist type
GET /maintenance/specialties → list all
PATCH /maintenance/specialties/{id} → update
DELETE /maintenance/specialties/{id} → deactivate

POST /workers/{worker_id}/specialties → assign specialties
GET /workers/{worker_id}/specialties → list assigned
DELETE /workers/{worker_id}/specialties/{specialty_id} → remove
```

### Phase 726 — Maintenance: Filtered Task View
```
GET /workers/{worker_id}/maintenance-tasks
├── If worker has specialties:
│   └── Only return tasks matching their specialty categories
├── If worker has NO specialties:
│   └── Return ALL maintenance tasks (single-person mode)
├── Match: problem_report.category → maintenance_specialty.specialty_key
```

### Phase 727 — Maintenance: External Worker Push
```
POST /tasks/{task_id}/push-to-external
├── Body: worker_id (external worker)
├── Auth: admin or ops_manager only
├── Sends task details to external worker via notification channel
├── External worker sees: task info, photos, navigate, complete button
├── External worker does NOT see: financial info, other properties
```

### Phase 728 — Maintenance: Admin Toggle (One vs Multiple)
```
PATCH /settings/maintenance-mode
├── Body: mode ('single' | 'specialists')
├── Global per-tenant setting
├── When mode = 'single': all workers see all tasks
├── When mode = 'specialists': filtered by specialty
```

### Phase 729–735 — Owner Portal & Maintenance: Tests
```
729: Contract — visibility toggle CRUD
730: Contract — filtered owner summary
731: Contract — owner auth (OTP)
732: Contract — specialist CRUD
733: Contract — filtered maintenance tasks
734: Contract — external worker push
735: E2E — owner logs in → sees only allowed data → maintenance visible
```

---

# 🌍 WAVE 9 — i18n & Localization (Phases 736–745)

---

### Phase 736 — i18n: String Catalog Infrastructure
```
Expand i18n/language_pack.py:
├── EN (English) — default, complete
├── TH (Thai) — MVP priority
├── HE (Hebrew) — MVP priority
├── Structure: category → key → translations
│   E.g.: cleaning.change_sheets → { en: "Change sheets", th: "เปลี่ยนผ้าปูที่นอน", he: "החלפת סדינים" }

API: GET /i18n/{lang} → returns full language pack
```

### Phase 737 — i18n: Guest Form Localization
```
All guest form labels in 3 languages
├── Guest type selector: Tourist/Resident in EN/TH/HE
├── Form field labels
├── Validation error messages
├── Submit button labels
```

### Phase 738 — i18n: Cleaning Checklist Localization
```
All checklist items have:
├── label (EN)
├── label_th (TH)
├── label_he (HE)
├── Supply check items same pattern
```

### Phase 739 — i18n: Problem Reporting Localization
```
├── Category labels in EN/TH/HE
├── Priority labels
├── Status labels
├── Report form labels
```

### Phase 740 — i18n: Guest Portal Localization
```
├── Portal labels in selected language
├── Extras names in property's default language
├── Chat interface labels
├── House info section headers
```

### Phase 741 — i18n: Auto-Translate Integration
```
When problem reported in Thai:
├── Store original in description
├── Store language code in description_original_lang = 'th'
├── Call translate API (or LLM) → English
├── Store in description_translated
├── Manager sees: English translation + original Thai

Leverage: llm_service.py already exists — use for translation
```

### Phase 742 — i18n: Worker UI Language Preference
```
Each worker has language preference (Phase 594):
├── Cleaning checklist shown in their language
├── Task notifications in their language
├── Problem report form in their language
```

### Phase 743–745 — i18n: Tests + Future Prep
```
743: Unit tests — language pack completeness (all keys in all languages)
744: Contract tests — form, checklist, portal in TH
745: RESERVED — Future Wave 2 prep: Russian, Italian, Spanish
```

---

# 🚀 WAVE 10 — Bulk Import Wizard (Phases 746–757)

---

### Phase 746 — OTA OAuth: Airbnb Connection
```
POST /integrations/airbnb/connect
├── Initiates OAuth flow with Airbnb
├── On callback: stores access_token
├── Lists all properties from Airbnb API
├── Returns: property list with details + photos

Leverage: adapters/ota/ directory — extend with auth
```

### Phase 747 — OTA OAuth: Booking.com Connection
```
Same as 746 but for Booking.com
├── POST /integrations/booking/connect
├── Different API, same result pattern
```

### Phase 748 — Bulk Import: Property Selection
```
POST /import/preview
├── Body: integration_id, provider
├── Returns: list of properties with:
│   ├── name, address, photos, amenities
│   ├── bedrooms, bathrooms, max_guests
│   ├── Already exists in system? (boolean)
│   └── Suggested merge with existing? (boolean)

POST /import/select
├── Body: property_ids to import (select all or pick)
├── Returns: import_job_id
```

### Phase 749 — Bulk Import: Execute
```
POST /import/execute/{job_id}
├── For each selected property:
│   ├── Create property record (via onboarding_router step 1)
│   ├── Import photos as marketing_photos
│   ├── Import amenities
│   ├── Map channel (channel_map)
│   ├── Apply smart defaults: 3PM check-in, 11AM check-out
│   └── Status tracking per property
├── Returns: progress (X of Y imported)
```

### Phase 750 — Bulk Import: Smart Defaults
```
After import:
├── checkin_time = '15:00'
├── checkout_time = '11:00'
├── Cleaning checklist = global default template
├── deposit_required = false (admin sets manually)
├── house_rules = [] (admin adds manually)
├── Reference photos = empty (admin takes on-site)
```

### Phase 751 — iCal Fallback: Paste URL
```
POST /integrations/ical/connect
├── Body: property_id, ical_url
├── Parse iCal → extract future bookings
├── Create booking_state records
├── Set up recurring sync (poll every 15 min)

Leverage: existing iCal handling if any
```

### Phase 752 — CSV Import
```
POST /import/csv
├── Upload CSV file
├── Columns: name, address, rooms, bathrooms, max_guests, wifi, door_code
├── Parse + validate
├── Preview: show parsed properties
├── Confirm: create all properties
├── Returns: created count + any errors
```

### Phase 753 — Duplicate Detection
```
When importing:
├── Check if property with same address OR same OTA external_id exists
├── If match found:
│   ├── "This looks like [existing property] — merge?"
│   ├── Option: merge (link OTA channel to existing property)
│   └── Option: create new anyway (with warning)
│
├── Cross-OTA: Airbnb property imported → now importing from Booking →
│   detect same address → suggest merge

Leverage: onboarding_router.py already has 409 safety gate
```

### Phase 754–757 — Bulk Import: Tests + RESERVED
```
754: Contract — OTA connect + property list
755: Contract — bulk select + import execute
756: Contract — iCal parse + CSV parse
757: RESERVED — future OTA integrations (Trip.com, Vrbo, Agoda)
```

---

# 📌 Post-Roadmap: Existing Features to Re-surface Later

> [!NOTE]
> These exist in iHouse Core but aren't directly in the product vision. Flag them for future phases:

| Feature | Module | When to Surface |
|---------|--------|----------------|
| Price deviation detection | `price_deviation_detector.py` | Owner alerts in Owner Portal |
| Cashflow projections | `cashflow_router.py` | Advanced Owner Portal |
| Financial reconciliation | `financial_reconciler.py` | Admin dashboard (monthly) |
| AI copilot / LLM | `llm_service.py` | Smart suggestions, auto-translate |
| Buffer inspector | `buffer_router.py` | Admin debugging tools |
| DLQ inspector | `dlq_router.py` | Admin ops tools |
| Guest feedback | `guest_feedback.py` | Post-checkout survey |
| Statement generator | `statement_generator.py` | Owner monthly report emails |
| Analytics | `analytics_router.py` | Admin advanced dashboard |
| Bulk operations | `bulk_operations.py` | Admin power tools |
| Monitoring | `monitoring_router.py` | System health dashboard |
| Capability registry | `capability_registry_router.py` | Feature flags |

---

## ✅ Final Count

| Wave | Phases | Count |
|------|--------|-------|
| 1 — Foundation | 586–605 | 20 |
| 2 — Guest Check-in | 606–625 | 20 |
| 3 — Task Enhancement | 626–645 | 20 |
| 4 — Problem Reporting | 646–665 | 20 |
| 5 — Guest Portal & Extras | 666–685 | 20 |
| 6 — Checkout & Deposit | 686–705 | 20 |
| 7 — Manual Booking & Take-Over | 706–720 | 15 |
| 8 — Owner Portal & Maintenance | 721–735 | 15 |
| 9 — i18n | 736–745 | 10 |
| 10 — Bulk Import | 746–757 | 12 |
| **Total** | **586–757** | **172 phases** |

> [!IMPORTANT]
> Reserved phases in each wave = room for iteration, bug fixes, and new requirements. Total allocated: ~15 reserved phases out of 172.
