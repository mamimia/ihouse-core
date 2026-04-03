# Evidence File: Yael — Guest Experience Architect

**Paired memo:** `14_yael_guest_experience_architect.md`
**Evidence status:** Strong evidence from both frontend pages and backend routers. Guest portal and self check-in architectures fully verified. Messaging, extras, and pre-arrival confirmed as operational systems.

---

## Claim 1: Guest portal has 7 working sections served via token-gated public page

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/app/(public)/guest/[token]/page.tsx` — Public page (no auth middleware, token-validated) rendering 7 sections: (1) Welcome header with guest name, property, dates. (2) Home Essentials: Wi-Fi, check-in/out times, emergency contact, welcome message, house rules. (3) How Home Works: AC, hot water, stove, parking, pool, laundry, TV, extra notes, door/safe codes, key location, breaker, trash. (4) Need Help: WhatsApp, phone, LINE, email, chat. (5) Around You: Google Maps/Waze with GPS, nearby places, extras. (6) Your Stay: guest count, deposit status. (7) Language Switcher: EN, TH, HE.
- File: `src/api/guest_portal_router.py` — Backend serves all 7 sections' data via token-validated endpoints. Token validation calls `guest_token.py` for HMAC verification.

**What was observed:** The guest portal is a complete product surface. All 7 sections have both frontend rendering and backend data. The page is public (under `(public)` route group, no middleware auth) but token-gated via HMAC validation on the backend. Deposit status uses display icons: ✅ Collected, ⏳ Pending, ↩️ Returned, –– Waived.

**Confidence:** HIGH

**Uncertainty:** Whether each section handles empty state gracefully (no Wi-Fi configured, no house rules, empty extras) was not tested. The frontend may render blank sections for unconfigured properties.

---

## Claim 2: Self check-in uses two-gate architecture with access code release only after Gate 1

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/app/(public)/self-checkin/[token]/page.tsx` — Self check-in frontend implementing step-by-step flow with Gate 1 (blocking) and Gate 2 (non-blocking) distinction
- File: `src/api/self_checkin_portal_router.py` — Backend Gate 1 conditions (ALL must pass before access code release): (1) ID photo uploaded, (2) selfie captured, (3) agreement signed, (4) deposit acknowledgment, (5) time gate: current time ≥ booking check-in time, (6) property status check: operational_status must be 'available' or 'ready', (7) no unresolved checkout on the property. Gate 2 (non-blocking, post-entry): electricity meter reading, arrival photos, custom steps.
- Same file: Access code is returned ONLY when ALL Gate 1 conditions pass. Steps are idempotent (can be retried without side effects).
- Same file: Identity photos stored in `guest-identity` bucket.
- Same file: On completion, issues guest HMAC token for portal continuity.

**What was observed:** The two-gate architecture is a genuine security-first design. Gate 1 ensures all legal/identity/operational requirements are met before the guest receives the access code. Gate 2 captures operational data (meter, photos) after entry without blocking the guest. The idempotent step design means network interruptions don't corrupt state. Portal continuity via HMAC token issuance at completion provides seamless transition to the main guest portal.

**Confidence:** HIGH

**Uncertainty:** None for the architecture. The property status dependency (must be 'available' or 'ready') creates a guest-facing dependency on cleaning completion (Claudia's domain).

---

## Claim 3: Guest check-in form with QR token generation (12-char nanoid)

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/guest_checkin_form_router.py` — Form creation with guest data: type (tourist/resident), language, guest addition with passport photo upload, signature capture, deposit recording
- Same file: `POST /bookings/{booking_id}/generate-qr` generates 12-character nanoid token. QR image endpoint returns scannable PNG. Worker presents QR to guest at check-in.
- File: `src/services/guest_token.py` — Token lifecycle: generation → HMAC signing → hash storage → QR embedding → portal URL

**What was observed:** The check-in form is worker-initiated (worker starts the form, guest fills it out). QR generation creates a 12-character nanoid that encodes into a portal URL. The PNG QR image is scannable. This is the physical handoff point: worker shows QR → guest scans → enters portal.

**Confidence:** HIGH

**Uncertainty:** None.

---

## Claim 4: Guest messaging with bidirectional chat and SSE notifications

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/guest_messages_router.py` — Token-gated messaging endpoints: `POST /guest/{token}/messages` for guest sending, `GET /guest/{token}/messages` for history retrieval. Backend tracks: channel (WhatsApp, SMS, LINE, Telegram, email, manual), direction (OUTBOUND/INBOUND), intent tagging. SSE notification to manager on inbound guest message. Message preview truncated to 300 characters. Messaging copilot provides AI-assisted draft responses for managers.

**What was observed:** Guest messaging is a functional bidirectional system. The guest sends via token-gated endpoint. The manager receives via SSE notification. The messaging copilot assists managers with draft responses — an AI feature that reduces manager response time without exposing the AI to the guest. Multiple channels are tracked (WhatsApp, SMS, LINE, etc.) suggesting integration with external messaging platforms.

**Confidence:** HIGH

**Uncertainty:** Whether the external messaging platform integrations (WhatsApp, LINE, Telegram) are fully wired or channel-tracking only (i.e., messages are recorded with their channel but actual delivery happens externally). The backend tracks channel but the integration depth was not traced.

---

## Claim 5: Guest extras ordering with full status workflow

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/guest_extras_router.py` — Guest endpoints: `GET /guest/{token}/extras` returns available extras for the property, `POST /guest/{token}/extras/order` for ordering. Manager endpoints: `PATCH /extra-orders/{order_id}` for confirm/reject/deliver. Status workflow: requested → confirmed → delivered (or canceled).
- Database tables: `property_extras` (catalog per property), `extra_orders` (individual orders with status tracking)

**What was observed:** The extras system is a complete ordering workflow: catalog browsing, ordering, manager confirmation, delivery tracking. Simple but functional — no payment integration (extras are tracked operationally, not financially billed through the system).

**Confidence:** HIGH

**Uncertainty:** Whether properties have actual extras configured. New properties likely have an empty extras catalog. No default seeding mechanism was found.

---

## Claim 6: Pre-arrival scanner with configurable lookahead and dry-run mode

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/pre_arrival_router.py` — Pre-arrival scanner scans upcoming check-ins within configurable lookahead window (default 48 hours). Auto-creates preparation tasks and draft messages. Admin endpoint `/admin/pre-arrival-queue` shows scanned bookings with `tasks_created` and `draft_written` flags. Dry-run mode supported for testing without side effects.

**What was observed:** The pre-arrival system automates preparation for upcoming check-ins. The 48-hour default lookahead is operationally practical. Dry-run mode enables testing the scanner without creating real tasks or messages. The admin queue view provides visibility into what was scanned and what actions were taken.

**Confidence:** HIGH

**Uncertainty:** None regarding the system's existence. The actual delivery mechanism for pre-arrival messages to guests (which channel, when triggered) was not fully traced.

---

## Claim 7: Guest token has 7-day TTL from issuance — post-checkout portal behavior not fully defined

**Status:** PARTIALLY PROVEN

**Evidence basis:**
- File: `src/services/guest_token.py` — Token TTL is 7 days from issuance, not from checkout. Token remains valid after checkout if within TTL window.
- File: `ihouse-ui/app/(public)/guest/[token]/page.tsx` — Portal reads booking status to determine display content. Post-checkout behavior depends on what the portal renders when booking status changes.

**What was observed:** The token doesn't expire at checkout — it has a fixed 7-day TTL. After checkout, the guest can still access the portal if the token is valid. Whether the portal content changes post-checkout (hiding access codes, showing "thank you" state) depends on booking status checks in the frontend that were not fully traced.

**Confidence:** MEDIUM

**Uncertainty:** The post-checkout guest experience is the gap. Does the portal hide the access code after checkout? Does it show a checkout confirmation? The token mechanism is proven; the UX response to post-checkout state is not.

---

## Claim 8: No guest-initiated check-in form — check-in is worker-initiated

**Status:** DIRECTLY PROVEN (absence)

**Evidence basis:**
- File: `src/api/guest_checkin_form_router.py` — Form creation requires worker/admin context. No guest-facing endpoint for proactive check-in information submission.
- File: `src/api/pre_arrival_router.py` — Pre-arrival endpoint `/guest/pre-arrival/{token}` exists but its completeness as a guest self-service check-in form was not confirmed.

**What was observed:** The check-in form workflow is: worker creates form → guest fills it out (at property, via QR). There is no path for a guest to proactively fill in check-in information (name, passport, companions) before arriving at the property via the guest portal. The pre-arrival endpoint exists in the router but whether it provides a full guest-initiated form or just informational content was not fully traced.

**Confidence:** HIGH for the worker-initiated pattern. MEDIUM for the pre-arrival endpoint gap (it may partially address this, but wasn't fully confirmed).

**Uncertainty:** The pre-arrival endpoint could serve as a partial solution. Needs deeper trace.

---

## Claim 9: No guest satisfaction capture mechanism

**Status:** DIRECTLY PROVEN (absence)

**Evidence basis:**
- No rating, feedback, NPS, or satisfaction endpoint was found in any guest-facing router
- File: `src/api/guest_portal_router.py` — No feedback or rating endpoints
- File: `src/api/guest_messages_router.py` — Messaging only, no structured feedback capture

**What was observed:** After checkout, the system has no mechanism to learn whether the guest was satisfied. No star rating, no free-text feedback form, no NPS survey, no post-stay email with rating link. The guest's journey ends silently — the last interaction is either the portal access expiring or the guest simply not returning to the portal.

**Confidence:** HIGH

**Uncertainty:** None. This is a confirmed missing feature, not an untraceable gap.
