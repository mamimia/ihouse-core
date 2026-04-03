# Activation Memo: Yael — Guest Experience Architect

**Phase:** 973 (Group C Activation)
**Date:** 2026-04-03
**Grounded in:** Direct reading of ihouse-core repository (ihouse-ui/app/(public)/guest/[token]/page.tsx, ihouse-ui/app/(public)/self-checkin/[token]/page.tsx, src/api/guest_portal_router.py, self_checkin_portal_router.py, guest_checkin_form_router.py, guest_extras_router.py, guest_messages_router.py, src/services/guest_token.py, pre_arrival_router.py)
**Builds on:** Group A (self check-in two-gate architecture, SELF_CHECKIN_FOLLOWUP task), Group B (check-in wizard worker side, OCR capture)

---

## 1. What in the Current Real System Belongs to This Domain

Yael's domain is the guest-facing product — everything a guest interacts with. The real system has:

- **Guest portal** (`/guest/[token]`): 7-section interface (Welcome, Home Essentials, How Home Works, Need Help, Around You, Your Stay, Language Switcher) served via token-gated public page
- **Self check-in portal** (`/self-checkin/[token]`): Two-gate architecture — blocking Gate 1 (ID, selfie, agreement, deposit ack, time gate) → access code release → non-blocking Gate 2 (meter, photos)
- **Guest check-in form** (`guest_checkin_form_router.py`): Form creation, guest addition, passport photo upload, signature capture, QR token generation
- **Guest messaging** (`guest_messages_router.py`): Bidirectional chat (guest ↔ manager) with SSE notifications, channel tracking, messaging copilot
- **Guest extras** (`guest_extras_router.py`): Extras catalog per property with ordering workflow (requested → confirmed → delivered)
- **Pre-arrival system** (`pre_arrival_router.py`): Automated scanning, task creation, draft message generation for upcoming check-ins
- **Guest token lifecycle** (`guest_token.py`): HMAC-SHA256 token with 7-day TTL, hash-only storage, booking-scoped, revocable
- **QR code generation**: 12-char nanoid token → portal URL → PNG QR image generation

## 2. What Appears Built

- **Guest portal (7 sections, PROVEN BUILT)**: Frontend at `ihouse-ui/app/(public)/guest/[token]/page.tsx`. Backend at `guest_portal_router.py`. Sections: (1) Welcome header with guest name, property, dates. (2) Home Essentials: Wi-Fi name/password, check-in/out times, emergency contact, welcome message, house rules. (3) How Home Works: AC, hot water, stove, parking, pool, laundry, TV, extra notes, door/safe codes, key location, breaker, trash. (4) Need Help: WhatsApp link, phone, LINE, email, chat messaging. (5) Around You: Google Maps/Waze links with GPS coords, nearby places, extras catalog. (6) Your Stay: guest count, deposit status (✅ Collected, ⏳ Pending, ↩️ Returned, –– Waived). (7) Language switcher: EN, TH, HE.

- **Self check-in portal (Phase 1012/1016, PROVEN BUILT)**: Frontend at `ihouse-ui/app/(public)/self-checkin/[token]/page.tsx`. Backend at `self_checkin_portal_router.py`. Gate 1 (blocking): ID photo, selfie, agreement, deposit ack, time gate (current time ≥ check-in time), property status check (available/ready), no unresolved checkout. Gate 2 (non-blocking): electricity meter, arrival photos, custom steps. Access code ONLY released after ALL Gate 1 conditions pass. Steps are idempotent. Identity photos stored in `guest-identity` bucket. Post-entry incomplete → creates SELF_CHECKIN_FOLLOWUP task (Phase 1004). On success: issues guest HMAC token for portal continuity.

- **Guest check-in form (Phases 606-618, PROVEN BUILT)**: Worker-initiated form with guest data capture. Guest type (tourist/resident), language selection, guest addition with passport photo upload, signature capture, deposit recording. QR token generation (`POST /bookings/{booking_id}/generate-qr` → 12-char nanoid). QR image endpoint returns scannable PNG. PII handling: passport photos redacted to `***` in API responses, boolean flags instead.

- **Guest messaging (Phase 670, PROVEN BUILT)**: Token-gated endpoints for guest-to-host communication. `POST /guest/{token}/messages` for sending, `GET /guest/{token}/messages` for history. Backend tracks channel (WhatsApp, SMS, LINE, Telegram, email, manual) and direction (OUTBOUND/INBOUND). SSE notification to manager on inbound message. Intent tagging. Message preview truncated to 300 chars. Guest messaging copilot assists managers with draft responses.

- **Guest extras (Phases 667-669, PROVEN BUILT)**: `GET /guest/{token}/extras` returns available extras for property. `POST /guest/{token}/extras/order` for ordering. Manager confirms/rejects/delivers via `PATCH /extra-orders/{order_id}`. Status workflow: requested → confirmed → delivered (or canceled). Tables: `property_extras` (catalog), `extra_orders` (orders).

- **Pre-arrival system (Phase 232, PROVEN BUILT)**: `pre_arrival_scanner.py` scans upcoming check-ins with configurable lookahead (default 48h). Auto-creates tasks + draft messages. Admin endpoint `/admin/pre-arrival-queue` shows scanned bookings with tasks_created, draft_written flags. Dry-run mode supported.

- **Guest token lifecycle (Phase 298, PROVEN SECURE)**: HMAC-SHA256 with base64url encoding. 7-day TTL. Constant-time comparison. Hash-only DB storage. Booking-scoped. Revocation support. QR code delivery mechanism.

- **Canonical guest name resolution (Phase 949d-2)**: When guest_id exists in booking_state, looks up `guests.full_name`. Handles iCal bookings where name may be "Reserved" or "Airbnb (Not available)".

## 3. What Appears Partial

- **Guest token delivery mechanism**: Token is generated and QR code is created, but the delivery path to the guest (how the guest receives the link) is not fully defined in code. Worker hands QR to guest at check-in. Pre-arrival sends via email/SMS. But the automated delivery chain (which channel, when, with what message) depends on notification infrastructure that wasn't fully traced.

- **Guest extras catalog population**: The ordering system works, but whether properties have actual extras configured depends on admin setup. New properties likely have an empty extras catalog. No default extras seeding.

- **Post-checkout guest experience**: Guest token has 7-day TTL from issuance (not from checkout). After checkout, the portal is accessible if the token is still valid. But whether the portal content changes post-checkout (e.g., hiding access codes, showing "checkout complete" state) depends on booking status checks that weren't fully traced in the frontend.

- **Guest portal empty states**: When property configuration is incomplete (no Wi-Fi configured, no house rules, no appliance instructions), the portal sections may render empty. Whether each section shows a helpful empty state ("Contact your host for Wi-Fi details") or just blank space was not fully traced.

## 4. What Appears Missing

- **No guest-initiated check-in form**: The check-in form (`guest_checkin_form_router.py`) is worker-initiated. The guest fills it out when the worker presents it (via QR). There's no path for the guest to proactively fill out check-in information before arrival through the portal. The pre-arrival form endpoint exists (`/guest/pre-arrival/{token}`) but its completeness was not fully confirmed.

- **No read receipts or typing indicators in messaging**: Guest messaging is basic send/receive. No read receipts, no typing indicators, no message status (sent/delivered/read). Functional for MVP but lacks modern messaging expectations.

- **No guest satisfaction signal**: No rating system, no feedback form, no NPS capture. After checkout, the system has no mechanism to learn whether the guest was satisfied.

- **No guest-side checkout confirmation**: Checkout is entirely worker-driven. The guest has no portal notification that checkout is complete, no receipt, no summary of their stay. The checkout happens to them rather than with them.

## 5. What Appears Risky

- **Guest portal with unconfigured properties**: If an admin assigns a property to an owner and issues a guest token before configuring Wi-Fi, house rules, appliance instructions, etc., the guest sees a portal with empty sections. The first impression of the system is emptiness. This is a trust risk at the guest touchpoint.

- **Self check-in Gate 1 dependency on property status**: Gate 1 checks `property.operational_status` must be 'available' or 'ready'. If cleaning hasn't completed (status = 'needs_cleaning'), the guest cannot self check-in even if they arrive on time. This is correct behavior but creates a guest-facing dependency on the cleaning flow (Claudia's domain).

**Open question impact — checkout canonicality (#3)**: The checkout flow transitions booking status via direct write. If this transition fails or is incomplete, the guest portal may show incorrect stay status. Since the portal reads booking status to determine what to display, checkout canonicality directly affects guest-facing truth.

**Open question impact — deposit duplication (#1)**: If duplicate deposits exist, the guest portal's deposit status display (✅ Collected, ⏳ Pending, etc.) may show inconsistent information. The portal reads from cash_deposits — duplicate records could produce confusing status.

## 6. What Appears Correct and Worth Preserving

- **Two-gate self check-in architecture**: Gate 1 (blocking) ensures security requirements are met before access code release. Gate 2 (non-blocking) captures operational data without delaying guest entry. This balances security with guest experience correctly.
- **HMAC token over JWT for guests**: Guests don't need roles or permissions — they need scoped, time-limited access to a specific booking's information. HMAC is the right choice.
- **Portal continuity from self check-in**: Self check-in completion issues a guest HMAC token for the main portal. Seamless transition from check-in flow to property information.
- **Guest messaging with copilot**: Manager gets AI-assisted draft responses. Reduces response time without requiring the guest to know about the AI.
- **PII redaction in API responses**: Passport photos and signatures never returned in plaintext. Boolean flags only. Correct for a system where the API response might be logged or cached.
- **Extras ordering system**: Simple but complete workflow (requested → confirmed → delivered). Correct for MVP — extensible without redesign.
- **Pre-arrival scanning with configurable lookahead**: 48h default is operationally sound. Dry-run mode enables testing without side effects.

## 7. What This Role Would Prioritize Next

1. **Define empty states for all portal sections**: Every section needs a guest-friendly message when content is not configured.
2. **Add pre-arrival guest form**: Allow guests to fill in check-in information (name, passport, companions) before arrival via a portal link. Reduces check-in friction.
3. **Add guest checkout confirmation**: When checkout completes, update the portal to show "Thank you for your stay" with summary.
4. **Add guest satisfaction capture**: Post-checkout rating or feedback form. Even a simple 1-5 star rating would provide signal.

## 8. Dependencies on Other Roles

- **Marco (Group B)**: Marco owns the worker-side check-in wizard; Yael owns the guest experience of the same event. The QR code handoff from worker to guest is the shared boundary.
- **Claudia (Group B)**: The self check-in Gate 1 depends on property readiness (operational_status). If cleaning is delayed, guest self check-in is blocked.
- **Oren**: Oren reviews the guest token security. Yael designs the experience built on that security.
- **Miriam**: Yael owns guest experience; Miriam owns owner experience. They share the property as a connecting entity.
- **Hana (Group B)**: Pre-arrival task creation connects Hana's staff system (task assignment to workers) with Yael's guest-facing pre-arrival information.

## 9. What the Owner Most Urgently Needs to Understand

The guest-facing product is substantially more complete than expected. The guest portal has 7 working sections with multilingual support. Self check-in is a sophisticated two-gate architecture. Guest messaging exists with copilot assistance. Extras ordering is built. Pre-arrival scanning automates preparation.

The guest experience has a real product — not a placeholder. Two things need attention:

1. **Empty states destroy first impressions**: A guest portal with unconfigured sections (no Wi-Fi, no house rules, empty extras) makes the system look broken. Every section needs a graceful empty state before properties go live.

2. **No guest-side checkout or feedback**: The guest's journey ends silently. No "thank you" screen, no receipt, no feedback mechanism. Adding even a basic post-checkout confirmation would complete the experience loop.
