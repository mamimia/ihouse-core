# Guest Portal — System Reality (Read Before Design)

**Read from:** ihouse-core real codebase + Team_Inbox screenshots + locked product rules
**Date:** 2026-04-03

> **This is not a worker surface.** The guest portal is a hospitality-facing companion for the guest. No internal operational identifiers. No property codes. No booking refs. No system jargon. Ever.

---

## What Already Exists [BUILT]

### Portal Architecture
- **Route:** `/guest/[token]` — public page, no login required
- **Auth:** HMAC-SHA256 signed token containing booking_ref, guest_email, expiry
- **Token TTL:** Default 7 days, configurable 1-30 days per issuance
- **Token security:** SHA-256 hash stored in DB (raw token never persisted), explicit revocation via `revoked_at` flag
- **Frontend:** Single scrollable page (`ihouse-ui/app/(public)/guest/[token]/page.tsx`, 670 lines)
- **No bottom nav.** No sidebar. Not a multi-tab app. Single-page scrollable portal.

### Portal Sections (Phase 64 structure — 6 built sections)

**1. Welcome / Stay Header**
- Guest name (canonical, sanitized for OTA placeholder names)
- Booking status badge (sanitized: "✅ Active", "📅 Upcoming", "✔ Checked Out")
- Property code shown (e.g., "KPG-500") ← **PROBLEM: internal code exposed**

**2. HOME ESSENTIALS**
- Check-in time (e.g., "15:00")
- Check-out time (e.g., "11:00")
- Wi-Fi name and password (when configured)
- Emergency contact
- House rules summary

**3. HOW THIS HOME WORKS**
- Dynamic list loaded from property configuration
- Categories: Air Conditioning, Hot Water, Stove/Kitchen, Parking, Pool, Laundry, TV/Entertainment, Extra Notes
- Each shows: category label + instruction text
- Icon per category

**4. NEED HELP**
- "Send a message to your host" heading
- Text input + "Send Message" button (blue)
- Messages routed to host/manager via SSE alert
- Max 2000 chars per message

**5. Around You / Extras**
- Location with Google Maps/Waze links
- Extras/services list with pricing (Phase 667-669)
- Guest can order extras: status lifecycle requested → confirmed/canceled → delivered

**6. Your Stay**
- Guest count
- Deposit status
- Checkout notes

### Footer
- Domaniqo logo ("Ð")
- "Powered by Domaniqo · info@domaniqo.com"

### Guest Name Sanitization (Phase 1047A-name)
OTA platforms often set placeholder names. The system blacklists: "reserved", "airbnb (not available)", "guest", "traveler" and similar. If guest name matches blacklist → falls back to generic "Welcome".

### Guest-Safe Fallbacks (Phase 1047A)
- Missing property_name → "Your Villa"
- Unsafe guest_name → generic "Welcome"
- Missing check-in/out times → defaults 15:00 / 11:00
- All sections conditional on data presence (empty sections hidden)

---

## Self Check-In Portal [BUILT — Phase 1012]

**Route:** `/self-checkin/[token]` — separate from main portal
**Architecture:** Two-gate system

**Gate 1 (Pre-Access):**
- Identity photo upload
- Agreement acceptance
- Deposit payment
- → On completion: access code released

**Gate 2 (Post-Entry):**
- Non-blocking follow-up steps after property entry
- Additional documentation

**State tracking:** `self_checkin_status` enum: none → approved → in_progress → access_released → completed → followup_required

---

## Guest Checkout [BUILT — Phase 1045]

**Route:** `/guest-checkout/[token]` — separate from main portal
**Steps:**
1. Confirm departure (required)
2. Key/access return (required)
3. Feedback (optional — rating 1-5, NPS computed)

**Token TTL extension:** Checkout time + 4-hour grace window (minimum 1 hour)
**Relationship to worker flow:** Non-blocking parallel — guest confirms departure independently of worker settlement.

---

## Guest Messaging [BUILT — Phase 670-675]

**Endpoints:**
- `POST /guest/{token}/messages` — guest sends message (max 2000 chars, triggers SSE)
- `GET /guest/{token}/messages` — full message history

**Routing:** Messages arrive to host/manager side. Bidirectional messaging with copilot assistance on manager side.

---

## Guest Feedback [BUILT — Phase 247]

- `POST /guest-feedback/{booking_id}` — rating (1-5) + text
- NPS computed from ratings
- Admin dashboard shows aggregated feedback by property

---

## Pre-Arrival [BUILT — Phase 615]

- `POST /guest/pre-arrival/{token}` — guest fills partial check-in form before arrival
- Contact info, special requests

---

## API Endpoints Summary

| Endpoint | Purpose | Auth |
|----------|---------|------|
| `GET /guest/portal/{token}` | Full portal data | Token |
| `GET /guest/{token}/house-info` | House instructions | Token |
| `GET /guest/{token}/contact` | Phone, email, WhatsApp | Token |
| `POST /guest/{token}/messages` | Send message | Token |
| `GET /guest/{token}/messages` | Message history | Token |
| `GET /guest/{token}/location` | GPS + map links | Token |
| `GET /guest/{token}/extras` | Available extras | Token |
| `POST /guest/{token}/extras/order` | Order extra | Token |
| `POST /guest/pre-arrival/{token}` | Pre-arrival form | Token |
| `POST /guest/verify-token` | Verify token | Public |

---

## What Is Visible in Current Screenshots [BUILT]

**Evidence:** Team_Inbox/GUEST UI — 2 screenshots

**Screenshot 1 (top of portal):**
- Dark navy/midnight background (not light/warm as product vision requests)
- Green "Active" badge on welcome card
- "Welcome, Bon" — guest name shown
- "KPG-500" — **internal property code visible** ← this must be corrected
- HOME ESSENTIALS section: Check-in time 15:00, Check-out time 11:00 (simple rows with icons)
- HOW THIS HOME WORKS section: list of amenity instructions (AC, Hot Water, Stove/Kitchen, Parking, Pool, Laundry, TV, Extra Notes) — each with icon + instruction text

**Screenshot 2 (bottom of portal):**
- Pool: "use with safe"
- Laundry: "call us for pickup"
- TV/Entertainment: "use remote"
- Extra Notes: "have fun"
- NEED HELP section: "Send a message to your host" + text input + "Send Message" button (blue)
- Footer: Domaniqo logo + "Powered by Domaniqo · info@domaniqo.com"

**Key visual observations:**
- Dark theme throughout (midnight navy, not warm/light)
- Cards are dark blue/navy with rounded corners
- Sections marked with emoji-style icons (🏠, ❄️, 🔥, etc.)
- Simple flat layout — no hero image, no host block, no departure block
- Very compact — all visible content fits in roughly 2 screen-heights
- No "Around You" section visible in screenshots
- No "Your Stay" section visible in screenshots
- No "Save This Stay" section visible
- No self check-in or checkout flows visible (separate routes)

---

## What Is Missing or Incomplete

### Critical Issues

1. **Internal property code exposed** — "KPG-500" visible on welcome card. Must be replaced with human property name. Fallback: "Your Villa". This is the single most important correction.

2. **Dark theme contradicts product vision** — The locked product rules specify: "warm, light palette, boutique hotel feel, not dark dashboard." Current portal uses the same dark theme as the worker shell. Guest portal needs its own visual identity.

3. **No property name shown** — Only internal code visible. The guest should see "Emuna Villa" or "Your Villa", never "KPG-500".

4. **No hero image** — No property cover photo at top. Product vision calls for "a beautiful photo of the villa" as the first visual element.

5. **No host/concierge block** — No human face, no host name, no response time indicator. Product vision specifies: "photo, name, hours, clear buttons: LINE, WhatsApp, Call, Message."

6. **No departure block** — No checkout guidance, no key return instructions, no departure confirmation. The guest checkout route exists (`/guest-checkout/[token]`) but is not linked from the main portal.

7. **No "Around You" section visible** — Extras API exists (Phase 667-669) but the section may be empty or hidden in the screenshot.

8. **No "Your Stay" section visible** — Guest count, deposit status, and checkout notes exist in the API but aren't visible.

9. **No "Save This Stay" / My Pocket bridge** — Product vision includes this as block 7 but it's not built.

### Structural Issues

10. **Single page, no state awareness** — The portal shows the same content regardless of booking status (pre-arrival, in-stay, post-departure). It should be contextual.

11. **Self check-in is a separate route** — `/self-checkin/[token]` is not linked from or integrated with the main portal experience.

12. **Guest checkout is a separate route** — `/guest-checkout/[token]` is not linked from or integrated with the main portal.

13. **Message thread not visible** — Only a send box exists on the portal. No visible history of past messages (though the API supports it).

14. **No satisfaction capture in portal** — Feedback endpoint exists but no UI trigger from the main portal.

---

## What Is Already Strong

1. **Token security** — HMAC-SHA256, hash-only storage, explicit revocation, configurable TTL. Production-grade.
2. **Guest name sanitization** — OTA placeholder blacklist with safe fallback. Well-designed.
3. **PII protection** — Passport photos, signatures, cash photos redacted from API responses. Only boolean flags returned.
4. **Internal ID filtering** — property_id, booking_id, tenant_id, guest_id are NOT exposed in guest API responses. (Exception: property code in frontend — see issue #1.)
5. **Conditional sections** — Empty data hides sections automatically. No broken empty states.
6. **Pre-arrival flow** — Guest can fill partial check-in form before arrival.
7. **Extras ordering** — Full lifecycle: request → confirm/cancel → deliver.
8. **Bidirectional messaging** — Guest sends, host receives via SSE. Full thread stored.
9. **Guest checkout flow** — Departure confirmation + key return + feedback. Independent of worker settlement.
10. **Self check-in gates** — Two-gate architecture with access code release.

---

## What Must Remain Hospitality-Safe

These rules are locked and must never be violated:

1. **No internal property codes.** Show human name or "Your Villa".
2. **No booking references.** No "KPG-500", no "ICAL-xxx", no task IDs.
3. **No internal status strings.** Use hospitality language: "Active", "Upcoming", "Checked Out" — not system enums.
4. **No operational jargon.** No "CHECKIN_PREP", no "CHECKOUT_VERIFY", no "task world".
5. **No worker-facing data.** No access codes (except at self check-in gate), no cleaning schedules, no maintenance reports.
6. **No error dumps.** Graceful fallbacks for all missing data.
7. **Human names.** Property names, host names, guest names — always human-readable.
8. **Warm tone.** "Welcome to your villa" not "Booking status: active".

---

## What Must Be Corrected Before Production-Safe

| Issue | Severity | Current State | Required State |
|-------|----------|---------------|----------------|
| Property code on welcome card | CRITICAL | Shows "KPG-500" | Show property name or "Your Villa" |
| Dark theme | HIGH | Dark navy dashboard | Warm/light hospitality palette |
| No hero image | MEDIUM | Text-only welcome | Property cover photo |
| No host block | MEDIUM | No human presence | Host name + photo + response time |
| No departure block | MEDIUM | No checkout guidance | Contextual departure info near checkout |
| No message history | LOW | Send-only box | Show recent thread |
| No portal ↔ self-checkin link | MEDIUM | Separate routes | Link from portal when applicable |
| No portal ↔ checkout link | MEDIUM | Separate routes | Link from portal near departure |
