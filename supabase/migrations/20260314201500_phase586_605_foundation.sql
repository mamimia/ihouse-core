-- ==========================================================================
-- Phases 586–605: Wave 1 — Foundation Schema Extensions
-- ==========================================================================

-- Phase 586 — Property GPS & Location
ALTER TABLE properties ADD COLUMN IF NOT EXISTS latitude FLOAT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS longitude FLOAT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS gps_saved_at TIMESTAMPTZ;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS gps_source TEXT; -- 'manual' | 'device' | 'geocoded'

-- Phase 587 — Check-in/out Times
ALTER TABLE properties ADD COLUMN IF NOT EXISTS checkin_time TEXT DEFAULT '15:00';
ALTER TABLE properties ADD COLUMN IF NOT EXISTS checkout_time TEXT DEFAULT '11:00';

-- Phase 588 — Deposit Configuration
ALTER TABLE properties ADD COLUMN IF NOT EXISTS deposit_required BOOLEAN DEFAULT FALSE;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS deposit_amount NUMERIC(10,2);
ALTER TABLE properties ADD COLUMN IF NOT EXISTS deposit_currency CHAR(3) DEFAULT 'THB';
ALTER TABLE properties ADD COLUMN IF NOT EXISTS deposit_method TEXT DEFAULT 'cash'; -- 'cash' | 'transfer'

-- Phase 589 — House Rules (JSONB)
ALTER TABLE properties ADD COLUMN IF NOT EXISTS house_rules JSONB DEFAULT '[]'::jsonb;

-- Phase 590 — Property Details (Extra Info)
ALTER TABLE properties ADD COLUMN IF NOT EXISTS door_code TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS key_location TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS wifi_name TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS wifi_password TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS ac_instructions TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS hot_water_info TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS stove_instructions TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS breaker_location TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS trash_instructions TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS parking_info TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS pool_instructions TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS laundry_info TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS tv_info TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS safe_code TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS emergency_contact TEXT;
ALTER TABLE properties ADD COLUMN IF NOT EXISTS extra_notes TEXT;

-- Phase 591 — Reference Photos
CREATE TABLE IF NOT EXISTS property_reference_photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    room_label TEXT NOT NULL,
    photo_url TEXT NOT NULL,
    display_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ref_photos_property ON property_reference_photos(tenant_id, property_id);

-- Phase 592 — Marketing Photos
CREATE TABLE IF NOT EXISTS property_marketing_photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    photo_url TEXT NOT NULL,
    caption TEXT,
    source TEXT DEFAULT 'upload',
    display_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mkt_photos_property ON property_marketing_photos(tenant_id, property_id);

-- Phase 593 — Amenities
CREATE TABLE IF NOT EXISTS property_amenities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    amenity_key TEXT NOT NULL,
    category TEXT NOT NULL,
    available BOOLEAN DEFAULT TRUE,
    notes TEXT,
    UNIQUE(tenant_id, property_id, amenity_key)
);
CREATE INDEX IF NOT EXISTS idx_amenities_property ON property_amenities(tenant_id, property_id);

-- Phase 594 — Worker ID fields on users
-- Using IF NOT EXISTS pattern for safety
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='worker_id') THEN
        ALTER TABLE users ADD COLUMN worker_id TEXT UNIQUE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='worker_role') THEN
        ALTER TABLE users ADD COLUMN worker_role TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='display_name') THEN
        ALTER TABLE users ADD COLUMN display_name TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='phone') THEN
        ALTER TABLE users ADD COLUMN phone TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='language') THEN
        ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'en';
    END IF;
END $$;

-- Phase 595 — Worker Action Tracking
CREATE TABLE IF NOT EXISTS task_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id TEXT NOT NULL,
    action TEXT NOT NULL,
    performed_by TEXT NOT NULL,
    payload JSONB,
    occurred_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_task_actions_task ON task_actions(task_id);

-- Phase 596 — Extras Catalog
CREATE TABLE IF NOT EXISTS extras_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT,
    default_price NUMERIC(10,2),
    currency CHAR(3) DEFAULT 'THB',
    category TEXT,
    is_system BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_extras_catalog_tenant ON extras_catalog(tenant_id);

-- Phase 597 — Property-Extras Mapping
CREATE TABLE IF NOT EXISTS property_extras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    extra_id UUID REFERENCES extras_catalog(id),
    price_override NUMERIC(10,2),
    active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    UNIQUE(tenant_id, property_id, extra_id)
);
CREATE INDEX IF NOT EXISTS idx_property_extras ON property_extras(tenant_id, property_id);

-- Phase 598 — Problem Reports
CREATE TABLE IF NOT EXISTS problem_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    booking_id TEXT,
    reported_by TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    description_original_lang TEXT,
    description_translated TEXT,
    priority TEXT DEFAULT 'normal',
    status TEXT DEFAULT 'open',
    resolved_by TEXT,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    maintenance_task_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_problem_reports_property ON problem_reports(tenant_id, property_id);
CREATE INDEX IF NOT EXISTS idx_problem_reports_status ON problem_reports(tenant_id, status);

CREATE TABLE IF NOT EXISTS problem_report_photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID REFERENCES problem_reports(id),
    photo_url TEXT NOT NULL,
    caption TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Phase 599 — Guest Check-in Forms
CREATE TABLE IF NOT EXISTS guest_checkin_forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    booking_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    form_status TEXT DEFAULT 'pending',
    guest_type TEXT DEFAULT 'tourist',
    form_language TEXT DEFAULT 'en',
    filled_by TEXT,
    worker_id TEXT,
    submitted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_checkin_forms_booking ON guest_checkin_forms(tenant_id, booking_id);

CREATE TABLE IF NOT EXISTS guest_checkin_guests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id UUID REFERENCES guest_checkin_forms(id),
    guest_number INT,
    full_name TEXT NOT NULL,
    nationality TEXT,
    document_type TEXT,
    document_number TEXT,
    passport_photo_url TEXT,
    phone TEXT,
    email TEXT,
    is_primary BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS guest_deposit_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    booking_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    currency CHAR(3) DEFAULT 'THB',
    status TEXT DEFAULT 'collected',
    cash_photo_url TEXT,
    collected_by TEXT,
    collected_at TIMESTAMPTZ,
    returned_by TEXT,
    returned_at TIMESTAMPTZ,
    refund_amount NUMERIC(10,2),
    signature_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_deposit_records_booking ON guest_deposit_records(tenant_id, booking_id);

CREATE TABLE IF NOT EXISTS deposit_deductions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deposit_id UUID REFERENCES guest_deposit_records(id),
    description TEXT NOT NULL,
    amount NUMERIC(10,2) NOT NULL,
    category TEXT,
    photo_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Phase 600 — Cleaning Checklists
CREATE TABLE IF NOT EXISTS cleaning_checklist_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    property_id TEXT,
    name TEXT DEFAULT 'Standard Cleaning',
    items JSONB NOT NULL DEFAULT '[]'::jsonb,
    supply_checks JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cleaning_templates ON cleaning_checklist_templates(tenant_id, property_id);

CREATE TABLE IF NOT EXISTS cleaning_task_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    booking_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    template_id UUID REFERENCES cleaning_checklist_templates(id),
    checklist_state JSONB,
    supply_state JSONB,
    all_photos_taken BOOLEAN DEFAULT FALSE,
    all_items_done BOOLEAN DEFAULT FALSE,
    all_supplies_ok BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    worker_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_cleaning_progress_task ON cleaning_task_progress(task_id);

CREATE TABLE IF NOT EXISTS cleaning_photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    progress_id UUID REFERENCES cleaning_task_progress(id),
    room_label TEXT NOT NULL,
    photo_url TEXT NOT NULL,
    taken_by TEXT,
    taken_at TIMESTAMPTZ DEFAULT now()
);

-- Phase 601 — Extra Orders
CREATE TABLE IF NOT EXISTS extra_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    booking_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    extra_id UUID REFERENCES extras_catalog(id),
    guest_token TEXT,
    quantity INT DEFAULT 1,
    unit_price NUMERIC(10,2),
    currency CHAR(3),
    status TEXT DEFAULT 'requested',
    notes TEXT,
    handled_by TEXT,
    requested_at TIMESTAMPTZ DEFAULT now(),
    confirmed_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_extra_orders_booking ON extra_orders(tenant_id, booking_id);

-- Phase 603 — Maintenance Specialists
CREATE TABLE IF NOT EXISTS maintenance_specialties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    specialty_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    display_name_th TEXT,
    icon TEXT,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS worker_specialties (
    worker_id TEXT NOT NULL,
    specialty_id UUID REFERENCES maintenance_specialties(id),
    tenant_id TEXT NOT NULL,
    PRIMARY KEY (worker_id, specialty_id)
);

ALTER TABLE properties ADD COLUMN IF NOT EXISTS maintenance_mode TEXT DEFAULT 'single';

-- Phase 604 — Owner Visibility Settings
CREATE TABLE IF NOT EXISTS owner_visibility_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    owner_user_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    visible_fields JSONB NOT NULL DEFAULT '{
        "booking_count": true,
        "occupancy_calendar": true,
        "guest_names": true,
        "price_per_night": false,
        "revenue": false,
        "cleaning_status": true,
        "maintenance_reports": true,
        "operational_costs": false,
        "guest_reviews": true,
        "worker_details": false
    }'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, owner_user_id, property_id)
);

-- Phase 605 — QR Tokens + Manual Booking Fields
CREATE TABLE IF NOT EXISTS guest_qr_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    booking_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    generated_by TEXT,
    portal_url TEXT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_qr_tokens_booking ON guest_qr_tokens(tenant_id, booking_id);
CREATE INDEX IF NOT EXISTS idx_qr_tokens_token ON guest_qr_tokens(token);

ALTER TABLE booking_state ADD COLUMN IF NOT EXISTS booking_source TEXT DEFAULT 'ota';
ALTER TABLE booking_state ADD COLUMN IF NOT EXISTS tasks_opt_out JSONB DEFAULT '[]'::jsonb;
