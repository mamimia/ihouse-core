# Evidence File: Miriam — Owner Experience Strategist

**Paired memo:** `11_miriam_owner_experience_strategist.md`
**Evidence status:** Strong evidence from both backend routers and frontend portal. Visibility enforcement traced to application level. Financial presentation fully verified.

---

## Claim 1: Owner portal renders real financial data (portfolio summary, per-property cards, statement drawer)

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/app/(app)/owner/page.tsx` — Owner portal frontend with portfolio summary metrics (properties count, total bookings, gross revenue, owner net), per-property financial cards, statement drawer with per-booking line items
- File: `src/api/owner_portal_v2_router.py` — Backend summary endpoint returning aggregated financial data per property
- File: `src/api/owner_statement_router.py` — Statement generation with per-booking line items including gross, commission, net, lifecycle_status, epistemic_tier

**What was observed:** The owner portal is a working product surface, not a placeholder. Frontend renders real financial data fetched from dedicated backend endpoints. Portfolio summary shows aggregate metrics. Per-property cards show gross/commission/net. Statement drawer opens with per-booking detail including lifecycle status and confidence tier.

**Confidence:** HIGH

**Uncertainty:** Whether all edge cases render correctly (zero bookings, single booking, mixed-confidence bookings) was not tested in the frontend.

---

## Claim 2: Owner statement honesty rule — OTA_COLLECTING excluded from net totals

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/owner_statement_router.py` — Statement generation logic explicitly filters OTA_COLLECTING bookings from net calculation while still including them in the line item list for visibility
- File: `src/adapters/ota/payment_lifecycle.py` — OTA_COLLECTING is one of the 7 lifecycle states, assigned when OTA has collected payment but payout has not been released

**What was observed:** The statement engine shows OTA_COLLECTING bookings in the line items (owner sees them) but explicitly excludes them from net_to_property totals. Only PAYOUT_RELEASED bookings count toward the net. This is the Phase 120 honesty rule — the system never over-promises money that hasn't been confirmed received.

**Confidence:** HIGH

**Uncertainty:** None. The exclusion logic is explicit in the statement generation code.

---

## Claim 3: PDF statement generation with language support

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/owner_statement_router.py` — `format=pdf` parameter triggers `generate_owner_statement_pdf()` function. Returns Content-Type: application/pdf. Language parameter accepts en, th, he.
- File: `ihouse-ui/app/(app)/owner/page.tsx` — Frontend has "Download PDF" button in statement drawer

**What was observed:** PDF generation is functional with multilingual support (English, Thai, Hebrew). The frontend has a working download button that triggers the PDF endpoint.

**Confidence:** HIGH

**Uncertainty:** The actual visual quality and layout of the PDF was not rendered and inspected.

---

## Claim 4: 8 visibility flags with application-level enforcement (NOT SQL-level)

**Status:** DIRECTLY PROVEN — PARTIAL RESOLUTION OF OPEN QUESTION #4

**Evidence basis:**
- File: `src/api/owner_portal_v2_router.py` — 8 visibility flags: show_bookings, show_financial_summary, show_occupancy, show_maintenance_reports, show_guest_info, show_task_progress, show_worker_details, show_cleaning_status. Default ON: bookings, financial_summary, occupancy. Default OFF: maintenance, guest, task, worker, cleaning.
- File: `src/api/owner_portal_v2_router.py` — Summary endpoint retrieves full data from database, then applies filtering in Python application logic based on the flags before returning the response

**What was observed:** The summary endpoint fetches all property data regardless of visibility settings. Filtering is applied in application code after the database query returns. The response is correctly filtered — the owner sees only what's enabled. But the database query itself is not scoped by visibility flags. A bug in the filtering logic would expose all data.

**Confidence:** HIGH — this is confirmed behavior, not inference

**Uncertainty:** None regarding the mechanism. The question of whether this should be SQL-level is a design recommendation, not an evidence gap.

---

## Claim 5: Owner property scoping (Phase 166) restricts owners to their own properties

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/owner_portal_v2_router.py` — When caller role is 'owner', access is restricted to properties listed in the caller's `permissions.property_ids` array. Returns 403 if owner attempts to access a property not in their property_ids.
- File: `src/api/admin_owners_router.py` — Property assignment via `property_owners` table with UNIQUE(owner_id, property_id) constraint

**What was observed:** Owner scoping is enforced per-request. Each API call checks the caller's role and, for owners, restricts to their assigned properties. Admin and manager roles bypass this restriction. The property_owners table has a structural UNIQUE constraint preventing duplicate assignments.

**Confidence:** HIGH

**Uncertainty:** None.

---

## Claim 6: No payout persistence — computed on-demand only

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/financial_writer_router.py` — Explicit comment: "Full payout persistence is a deferred feature." Payout endpoint computes amounts but does not write to any payouts table.
- File: `artifacts/supabase/schema.sql` — No `payouts` table exists in the schema

**What was observed:** The payout calculation is real (applies management fee deduction, reads from booking_financial_facts), but the result is ephemeral. It's returned in the API response and discarded. No audit trail exists for actual payouts made to owners.

**Confidence:** HIGH

**Uncertainty:** None. This is an explicitly documented design decision (deferred feature), not an accidental gap.

---

## Claim 7: Management fee calculated at statement time, not stored

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/owner_statement_router.py` — management_fee_pct read from property/tenant configuration at statement generation time. management_fee_amount = total_gross × management_fee_pct / 100. Both included in statement response. Neither persisted to a dedicated table.

**What was observed:** Fee calculation is inline during statement generation. Default is 15%. If the percentage changes, regenerating the same statement would produce different numbers. No snapshot or versioning mechanism exists for the applied rate.

**Confidence:** HIGH

**Uncertainty:** Whether fee rate changes are common in practice. The risk is structural (no versioning) but may be low-frequency in operations.

---

## Claim 8: Statement email delivery is placeholder

**Status:** INFERRED FROM FRONTEND + BACKEND GAP

**Evidence basis:**
- File: `ihouse-ui/app/(app)/owner/page.tsx` — "Send by email" button exists in statement drawer UI
- Backend: No email dispatch function was found connected to the statement endpoint

**What was observed:** The UI element exists but the actual email sending mechanism was not traced to a working dispatch function. The button likely triggers an endpoint that either simulates or stubs the delivery.

**Confidence:** MEDIUM

**Uncertainty:** The email dispatch could exist in a notification service not examined in this trace. The claim is based on absence of evidence, not evidence of absence.
