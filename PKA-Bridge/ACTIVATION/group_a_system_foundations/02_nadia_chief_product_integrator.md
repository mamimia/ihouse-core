# Activation Memo: Nadia — Chief Product Integrator

**Phase:** 971 (Group A Activation)
**Date:** 2026-04-02
**Grounded in:** Direct reading of ihouse-core repository

---

## 1. What in the Current Real System Belongs to This Domain

Nadia's domain is integration truth — whether features are actually wired end-to-end from database through backend through API through frontend. The real system has:

- **134 backend routers** serving data to a **Next.js 16 / React 19 frontend** with 60+ route pages
- **Two API clients** (api.ts ~400 lines, staffApi.ts ~200 lines) with different token strategies
- **Supabase RPC functions** (apply_envelope) called by backend, queried by frontend via API
- **Multiple migration waves** (legacy SQL + Supabase format) creating the schema
- **Envelope response standard** (ok/data/meta or ok/error/code) enforced across all routers

## 2. What Appears Built

- **api.ts**: Full-featured client with 40+ typed API methods, automatic envelope unwrapping, 401/403 distinction (logout on 401 only, not 403), retry logic for GET requests, preview role header injection. Extensive TypeScript types for Tasks, Bookings, Financial data, Guests, Audit events.
- **staffApi.ts**: Worker-facing client with `getTabToken()` (sessionStorage-first for Act As isolation), `getWorkerId()` from JWT decode, preview role forwarding. Guards against mixing with api.ts.
- **Checkin integration**: 7-step wizard in frontend calls multiple backend routers (guest_checkin_form, checkin_identity, checkin_settlement, checkin_photos, booking_checkin). Each step hits specific endpoints. OCR linkage (Phase 988) connects meter/passport capture to ocr_results table.
- **Checkout integration**: 4-step frontend flow calls checkout_settlement_router (closing meter, settlement start/calculate/finalize) and booking_checkin_router (POST /bookings/{id}/checkout for status transition).
- **Cleaner integration**: Frontend cleaner flow calls cleaning_task_router for checklist template retrieval, progress tracking, photo uploads, supply tracking, inline issue reporting.
- **Settlement engine**: Frontend settlement steps call draft → calculate → add deductions → finalize. Backend creates electricity deductions automatically from meter delta × rate.
- **Guest portal**: Token-gated public page loads 6 sections via best-effort async fetch. Backend guest_portal_router serves property info, guest_messages for chat, guest_token for access.

## 3. What Appears Partial

- **Dual deposit path**: Frontend check-in wizard step 5 (deposit collection) calls `checkin_settlement_router` which writes to `cash_deposits`. But `deposit_settlement_router` (Phases 687-692) has a separate POST /deposits endpoint. The frontend may be calling one, both, or neither consistently. Which router does the check-in wizard actually call? This needs trace verification.
- **Financial aggregation wiring**: financial_aggregation_router, financial_dashboard_router, financial_correction_router exist as routers. Frontend `/financial` and `/financial/statements` pages exist. Whether the frontend calls match the backend contracts needs verification — the SYSTEM_MAP noted a potential key mismatch (response.items vs response.data.line_items).
- **Owner portal v2 filtering**: owner_portal_v2_router defines visibility toggle endpoints. owner_visibility_router exists. But whether the owner financial summary endpoint actually filters based on toggle state is unconfirmed — the frontend may show all data regardless of toggles.
- **Self check-in portal integration**: Backend self_checkin_portal_router (Phase 1012) has a complete two-gate architecture. Frontend /self-checkin/[token] exists. Integration completeness needs verification — the gate logic is complex (time gates, photo uploads, access code release).

## 4. What Appears Missing

- **Contract documentation**: No OpenAPI spec or typed contract between frontend and backend beyond what TypeScript types in api.ts imply. Contract drift is caught only at runtime.
- **staffApi.ts typed methods**: staffApi.ts has fewer typed wrapper methods than api.ts — many worker-facing API calls may use raw fetch with untyped responses, increasing contract risk.
- **Integration test layer**: No visible integration tests that verify frontend-to-backend contract alignment. The claimed 7,765 tests may be unit tests.

## 5. What Appears Risky

- **Two deposit routers, unclear frontend binding**: The check-in wizard calls deposit collection. The checkout wizard calls deposit settlement/return/forfeit. But these may hit different backend tables or the same table via different routers. If the check-in writes to `cash_deposits` via checkin_settlement_router and the checkout reads from `deposits` via deposit_settlement_router, the data won't connect.
- **134 routers with financial ordering**: The comment in main.py says financial-specific routes MUST register before the catch-all `/financial/{booking_id}`. If a new router is added in the wrong position, a specific route could be swallowed by the catch-all.
- **api.ts 401 logout behavior**: Auto-logout on 401 is correct, but the code shows it does NOT logout on 403 (CAPABILITY_DENIED, PREVIEW_READ_ONLY). If a 403 is returned for a stale token (miscategorized), the user sees a broken state instead of being redirected to login.

## 6. What Appears Correct and Worth Preserving

- **Envelope standard**: The ok/data/error pattern is consistently applied across routers via `ok()` and `err()` helpers. Frontend unwraps this uniformly.
- **Token isolation**: api.ts reads localStorage; staffApi.ts reads sessionStorage-first. This is a critical safety boundary. Comment guards in staffApi.ts ("NEVER mix with admin api.ts") reinforce this.
- **Step-by-step wizard architecture**: Both check-in (7-step) and checkout (4-step) wizards in the frontend are task-bound — they load from task data, not booking data directly. This is architecturally sound: the task is the unit of work.
- **OCR linkage pattern**: Phase 982/988 links photo captures to structured OCR results with confidence scores and status tracking (pending_review → confirmed/rejected/corrected). This is a solid pipeline.

## 7. What This Role Would Prioritize Next

1. **Trace the deposit write/read path end-to-end**: Follow the frontend check-in wizard deposit step → identify which backend endpoint it calls → verify the table written → follow the checkout settlement → verify it reads from the same table. This is the #1 integration truth question.
2. **Verify owner portal filtering**: Call the owner financial summary endpoint with visibility toggles set to restrictive values. Confirm whether the response actually filters data or returns everything regardless.
3. **Map staffApi.ts coverage**: List all worker-facing API calls and determine which use typed wrapper methods vs. raw fetch. Identify contract risk zones.

## 8. Dependencies on Other Roles

- **Larry**: Nadia needs Larry to confirm sequencing — should the deposit trace happen before or after Elena's consistency audit?
- **Elena**: Nadia's deposit trace will identify the table written; Elena should verify whether the data in that table is consistent with event_log expectations
- **Ravi**: Ravi's flow mapping depends on Nadia's integration truth — Ravi maps the flow, Nadia confirms the plumbing
- **Daniel**: Nadia needs Daniel to confirm which roles are allowed to call the settlement endpoints — role guards on financial mutation endpoints are critical

## 9. What the Owner Most Urgently Needs to Understand

The system has significantly more integration surface area than the SYSTEM_MAP captured. There are now 134 routers, a self-check-in portal, an OCR platform, and a full settlement engine. The integration quality appears generally strong — the envelope standard, token isolation, and wizard architecture are well-designed.

The most urgent integration truth question is the **deposit data path**: the check-in and checkout flows may be writing and reading deposits through different routers that target different tables. Until this is traced end-to-end, we cannot confirm that money collected at check-in is visible and settleable at checkout.
