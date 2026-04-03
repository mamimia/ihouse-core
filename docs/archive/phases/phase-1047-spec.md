# Phase 1047 — Current Stay Portal: Audit & Premium Redesign

**Status:** Audit complete — ready for implementation approval  
**Phase type:** Product completion — full guest surface redesign  
**Scope:** `/guest/[token]` portal only (public, token-gated)

---

## 1. Audit: What Currently Exists

### 1a. Frontend — `/app/(public)/guest/[token]/page.tsx`

The portal is a single `'use client'` Next.js page. 608 lines total.  
It loads data from one primary endpoint (`GET /guest/portal/{token}`) and three secondary fetch calls.

| Section | Status | Data source | Real or placeholder |
|---------|--------|------------|---------------------|
| **Hero / Welcome** | BUILT, thin | `/guest/portal/{token}` → `guest_name`, `check_in`, `check_out`, `booking_status` | REAL data (when filled). Status always renders "✅ Checked In" hardcoded regardless of actual status |
| **Home Essentials** | BUILT | `wifi_name`, `wifi_password`, `check_in_time`, `check_out_time`, `emergency_contact`, `welcome_message` | REAL — reads from `properties` table |
| **House Rules** | BUILT | `house_rules` (JSONB array) | REAL — reads from `properties` table |
| **How This Home Works** | BUILT, lazy | `GET /{token}/house-info` → ac, hot water, stove, parking, pool, laundry, tv, extra_notes | REAL — reads from `properties` table. Renders only if data exists |
| **Need Help / Contact** | BUILT, limited | `GET /{token}/contact` → `manager_phone`, `manager_whatsapp`, `manager_email` | PARTIAL — phone and LINE shown. No manager name, no photo, no response time |
| **Send Message** | BUILT, limited | `POST /{token}/messages` → `guest_chat_messages` table | REAL writing. Many gaps (see messaging audit below) |
| **Around You** | BUILT, sparse | `GET /{token}/location` + `GET /{token}/extras` | PARTIAL — shows Maps + Waze links if lat/lng exists. Nearby is a flat string array only. No curated picks |
| **Your Stay** | BUILT, thin | `number_of_guests`, `deposit_status`, `checkout_notes` | REAL — reads live deposit + property checkout_notes |
| **Departure Block** | NOT BUILT | — | MISSING |
| **Host / Concierge identity** | NOT BUILT | — | MISSING entirely |

### 1b. Available but UNUSED in the portal

Fields that exist in `properties` table but are not surfaced to the guest:

| Field | Present in DB | Used in portal |
|-------|--------------|----------------|
| `cover_photo_url` | ✅ Phase 844 | ❌ Not used — no hero image |
| `key_location` | ✅ Phase 590 | ❌ Not surfaced |
| `door_code` | ✅ Phase 590 | ❌ Not surfaced |
| `trash_instructions` | ✅ | ❌ Not surfaced |
| `breaker_location` | ✅ | ❌ Not surfaced |
| `safe_code` | ✅ | ❌ Not surfaced (intentionally sensitive) |
| `max_guests` | ✅ | ❌ Not surfaced |
| `amenities` | ✅ Phase 844 | ❌ Not surfaced |
| `description` | ✅ | ❌ Not surfaced |
| `manager_whatsapp` | ✅ | ⚠️ Used in `/contact` only — not in hero concierge block |
| `manager_name_display` | ❌ Not in schema | ❌ No host name on portal |
| `host_photo_url` | ❌ Not in schema | ❌ No host photo |
| `concierge_response_time` | ❌ Not in schema | ❌ No response expectation shown |
| `nearby_places` | ❌ Not in schema | ❌ Only raw `nearby[]` string array from location endpoint |
| `checkout_instructions` | ❌ Not in schema | ❌ `checkout_notes` exists (property-level), but no dedicated departure checklist |

---

## 2. Audit: Send Message — End-to-End

### Click path (guest side)
1. Guest opens `/guest/{token}` → Section 4 "Need Help" renders
2. Textarea + "Send Message" button present
3. On click: `POST /{token}/messages` with `{ message: "..." }` JSON body

### Bug: body key mismatch
- Frontend sends `{ message: "..." }`
- Backend reads `body.get("content")` (line 324 of `guest_portal_router.py`)
- **Result: every guest message is silently dropped with 400 VALIDATION_ERROR "content is required"**
- The frontend shows "✅ Message sent!" regardless (no error handling on fetch response)

### Backend write path (when content key is fixed)
- Writes to `guest_chat_messages` table with `{ booking_ref, sender_type: "guest", content, created_at }`
- After insert: fires SSE event `GUEST_MESSAGE_NEW` to the tenant's SSE channel

### Operator-side visibility
- **`guest_chat_messages` table** — guest-originated inbound messages. Read via `GET /{token}/messages`.
- **`guest_messages_log` table** — outbound manager→guest comms log (Phase 236). Different table, different router.
- Currently: **no UI surface in the admin or OM hub shows `guest_chat_messages`**
- The SSE event `GUEST_MESSAGE_NEW` fires but no UI listens for it / renders an inbox
- **Effective result: guest messages go into the DB but no operator sees them**

### Routing
- Not routed to concierge, ops, or admin — just stored in DB
- No notification channel (LINE, email, push) connected to inbound guest messages
- No expected response path exists

---

## 3. Audit Summary

### BUILT and production-ready
- Token-based public route with canonical token resolver ✅
- Property essentials (wifi, check-in time, emergency) ✅
- House rules ✅
- House info (a/c, hot water, stove, laundry, pool, parking) ✅
- Location: maps/waze links ✅
- Deposit status readout ✅
- Multi-language labels structure (EN/TH/HE) ✅

### BUILT but broken
- **Send Message**: body key mismatch — messages never reach DB
- **Status display**: hardcoded "✅ Checked In" — doesn't reflect actual booking_status
- **House info endpoint**: returns `{ info: { ... } }` but frontend reads the root keys directly — data doesn't render
- **Contact endpoint**: returns `whatsapp_link`, `phone`, `email` but frontend renders `contact.phone` and `contact.line` — `line` is never returned by this endpoint

### BUILT but thin / not acceptable quality
- Hero: no image, no real villa identity, no host presence
- "Need Help" section: shows phone/LINE only — no who-is-responding, no response time promise
- "Around You": raw string list only — not curated recommendations
- "Your Stay": 2-3 data points, no real richness
- Overall visual quality: dark, thin, utility-grade — not hospitality premium

### MISSING entirely
- Hero image / cover photo (field exists in DB: `cover_photo_url`)
- Host identity block (name, photo, role — no DB fields exist yet for name/photo/role)
- Departure Block (Sections 7 per product direction)
- Trash instructions surfaced to guest
- Key location / door code surfaced
- Any operator inbox for inbound guest messages
- LINE notification to ops when guest sends a message

---

## 4. Product-Level Issues

| Issue | Severity |
|-------|----------|
| Guest messages are silently lost | 🔴 Critical |
| Hero image unused despite DB field | 🟠 High |
| Status hardcoded — always shows "Checked In" | 🟠 High |
| No host identity — guest doesn't know who to trust | 🟠 High |
| House info section doesn't render (data shape mismatch) | 🟠 High |
| No departure block | 🟡 Medium |
| Contact section reads wrong field keys | 🟡 Medium |
| Visual quality below hospitality bar | 🟡 Medium |
| "Around You" has no curated content | 🟡 Medium |

---

## 5. Reuse vs Replace Decision

### Keep and enrich
- Token resolution + public route structure ✅
- `/guest/portal/{token}` as primary data endpoint — extend response shape ✅
- `/guest/{token}/house-info` — fix field rendering bug, keep endpoint ✅
- `/guest/{token}/contact` — fix field mapping, keep endpoint ✅
- `POST /{token}/messages` — fix body key (`message` → `content`), keep endpoint ✅

### Replace entirely
- `WelcomeHeader` component — rebuild as full hero with image, status, dates, host card
- `InfoCard`, `SectionHeader` — generic components, replace with richer design system
- `NeedHelp` section — rebuild as "Your Host" premium block with identity, channels, trust signals
- `AroundYou` section — rebuild with curated card grid, not plain text list
- Overall visual/CSS system — current inline styles are inconsistent and non-premium

### Add new (backend required)
- `properties.manager_name_display` — text field for host display name (NEW column)
- `properties.concierge_phone_display` — curated display-safe contact string (NEW column)
- `properties.host_photo_url` — host avatar (NEW column)
- `properties.response_time_display` — e.g. "Usually within 1 hour" (NEW column)
- `properties.nearby_curated` — JSONB array of `{ label, emoji, note }` (NEW column)
- `properties.departure_checklist` — JSONB array of string checklist items (NEW column)
- `properties.key_handoff_instructions` — text field for departure key flow (NEW column)

### Fix bugs
- Guest message body key mismatch: `message` → `content`
- House info response shape: frontend reads top-level, backend wraps in `{ info: {...} }`
- Contact field rename: `whatsapp_link` → phone/line display fix
- Status display: use real `booking_status` value, not hardcoded string

---

## 6. Implementation Plan

### Phase 1047A — Emergency fixes (no new UI work)
1. Fix `POST /{token}/messages` key mismatch (`message` → `content`): frontend change
2. Fix house info renderer: unwrap `{ info: {...} }` → use `info` object
3. Fix contact field: map `whatsapp_link`, `phone`, `email` correctly
4. Fix status display: use `booking_status` from response, not hardcoded string
5. Wire `cover_photo_url` into the hero (field exists, just unused)

**Deploy target:** Immediate, same Vercel/Railway deploy. No DB changes.

### Phase 1047B — Host identity + DB fields
1. DB migration: add 7 new `properties` columns (see §5 above)
2. Extend `/guest/portal/{token}` response to include new fields
3. Rebuild `WelcomeHeader` → `HeroBlock` with: image, villa name, dates, status chip, host card row
4. Build new `YourHostBlock` with: host name, photo, response time, CTA buttons (WhatsApp, LINE, in-portal message)

### Phase 1047C — Premium redesign pass
1. Replace inline style system with consistent design tokens
2. Rebuild all section cards with hospitality-grade visual hierarchy
3. Google Fonts: import Inter or similar
4. Section 5: "Around You" — rebuild as curated card grid from `nearby_curated` JSONB
5. Section 7: Departure Block — checkout date chip, checklist, key handoff, confirmation CTA

### Phase 1047D — Messaging closure
1. Fix inbound guest message pipeline: SSE → LINE notification to ops channel
2. Add guest messages inbox to admin guest dossier (surface `guest_chat_messages` per booking)
3. Allow ops to reply via portal (write back `sender_type: "host"` rows, guest reads full thread)

---

## 7. New Backend Fields Required

```sql
ALTER TABLE properties
  ADD COLUMN IF NOT EXISTS manager_name_display   TEXT,
  ADD COLUMN IF NOT EXISTS host_photo_url          TEXT,
  ADD COLUMN IF NOT EXISTS response_time_display   TEXT DEFAULT 'Usually within 1 hour',
  ADD COLUMN IF NOT EXISTS nearby_curated          JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS departure_checklist     JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS key_handoff_instructions TEXT,
  ADD COLUMN IF NOT EXISTS concierge_role_display  TEXT DEFAULT 'Your Host';
```

---

## 8. Phase Decision

**Next action: approve this plan, then implement in order:**

1. **1047A** — Fix broken items now (no design work, no DB changes). Small deploy.
2. **1047B** — DB migration + host identity fields. One migration, backend + frontend.
3. **1047C** — Full premium redesign pass. Largest phase.
4. **1047D** — Messaging closure. Requires: LINE integration, inbox UI.

Each sub-phase is independently deployable and produces a visible improvement.
