# Phase 973 — Group C Activation: Stakeholder-Facing Product

**Date:** 2026-04-03
**Depends on:** Phase 971 (Group A Activation), Phase 972 (Group B Activation)
**Status:** Complete

---

## Objective

Activate Group C (4 roles) to read the real stakeholder-facing product surfaces in ihouse-core and produce first-pass domain memos with paired evidence files. Group C covers the product surfaces that face external stakeholders: property owners, guests, and the trust/privacy boundaries that protect both. Group C explicitly builds on Groups A and B findings and addresses the 5 open questions carried forward.

## Group C Roster

| # | Name | Title | Domain |
|---|------|-------|--------|
| 11 | Miriam | Owner Experience Strategist | Owner portal, statement engine, visibility controls, owner lifecycle |
| 12 | Victor | Financial Lifecycle Designer | Payment lifecycle, deposit lifecycle, settlement engine, reconciliation |
| 13 | Oren | Trust & Privacy Reviewer | Trust boundaries, PII controls, token security, data exposure |
| 14 | Yael | Guest Experience Architect | Guest portal, self check-in, messaging, extras, pre-arrival |

## Artifacts Produced

### Memos (PKA-Bridge/ACTIVATION/group_c_stakeholder_facing_product/)
- `11_miriam_owner_experience_strategist.md`
- `12_victor_financial_lifecycle_designer.md`
- `13_oren_trust_privacy_reviewer.md`
- `14_yael_guest_experience_architect.md`

### Evidence (PKA-Bridge/ACTIVATION/group_c_stakeholder_facing_product/evidence/)
- `11_miriam_owner_experience_strategist_evidence.md` — 8 claims
- `12_victor_financial_lifecycle_designer_evidence.md` — 9 claims
- `13_oren_trust_privacy_reviewer_evidence.md` — 9 claims
- `14_yael_guest_experience_architect_evidence.md` — 9 claims

## Key Findings

### Cross-Role Convergence Pattern: The Product Is More Complete Than Expected — Again

Continuing the pattern from Group B, all 4 Group C roles independently discovered substantially more built product than anticipated:

1. **Owner portal with real financial data** (Miriam): Working portfolio summary, per-property cards, per-booking statements with epistemic confidence tiers, PDF generation, honesty rule excluding unconfirmed payments from net totals.
2. **7-state payment lifecycle** (Victor): Fully deterministic state machine, append-only financial facts with confidence tiers, working settlement engine with auto-electricity deduction.
3. **Textbook-correct token security** (Oren): HMAC-SHA256 with constant-time comparison, hash-only storage, PII redaction in API responses, 5-minute signed URLs for documents, comprehensive audit logging.
4. **Complete guest-facing product** (Yael): 7-section portal, sophisticated two-gate self check-in, bidirectional messaging with AI copilot, extras ordering, pre-arrival automation.

### Cross-Role Convergence Pattern: Missing End-of-Journey Experiences

Multiple roles identified that the system handles entry well but lacks completion experiences:

1. **No payout persistence** (Victor, Miriam): The most important financial operation for owners has no audit trail.
2. **No guest checkout confirmation** (Yael): Guest journey ends silently — no thank you, no receipt, no feedback mechanism.
3. **No guest satisfaction capture** (Yael): No mechanism to learn whether guests were satisfied.
4. **Statement email delivery is placeholder** (Miriam): PDF exists but automated delivery to owners isn't wired.

### Open Questions — Final Status After Group C

| # | Question | Status After Group C |
|---|----------|---------------------|
| 1 | Deposit duplication guard | **ELEVATED** — Victor confirmed NO UNIQUE constraint on cash_deposits(booking_id, tenant_id). Duplication is structurally possible. Guard relies entirely on frontend wizard discipline. |
| 2 | Settlement endpoint authorization | **CLARIFIED** — Victor confirmed settlement endpoints are role-gated but NOT capability-gated. Two patterns coexist: financial reporting uses `require_capability("financial")`, settlement mutations use role guards only. Design question, not accidental gap. |
| 3 | Checkout/operational canonicality | **UNCHANGED** — All operational_status writes (check-in, checkout, cleaning, self check-in) are direct writes, not event-sourced. Settlement is also direct-write. If canonicality is questioned, it affects the entire operational layer, not just checkout. |
| 4 | Owner visibility enforcement | **RESOLVED** — Miriam confirmed: application-level filtering. Backend queries all data, filters in Python before response. Works correctly but is not defense-in-depth. SQL-level filtering recommended. |
| 5 | Worker disable/task safety | **EXPANDED** — Oren added: deactivation also doesn't appear to invalidate active JWT tokens. A deactivated worker may retain access until token expiry. Middleware `is_active` check needs verification. |

### Cross-Role Risk: Storage Bucket Configuration

Oren identified that the entire PII protection model (signed URLs, admin-only access, audit logging) depends on storage buckets being private. Bucket configuration is NOT visible in code — it's set in the Supabase dashboard. If any PII bucket (passport-photos, signatures, staff-documents, guest-documents) is public, URLs follow predictable patterns and could be enumerated. This is the single highest-priority runtime verification item.

## Combined A+B+C Assessment

After 14 role activations reading the real ihouse-core repository:

**What's stronger than expected:** The system has genuine product depth. It's not a prototype or MVP stub — it's a working multi-surface SaaS with event-sourced booking lifecycle, 7-state financial state machine, three distinct user shells, two-gate guest self check-in, token-gated guest portal, worker mobile with OCR, owner portal with epistemic confidence tiers, and comprehensive PII protection. The honesty rule (excluding unconfirmed payments from owner net) and confidence tiers are unusual for early-stage property management platforms.

**What's structurally sound:** Authentication (JWT + HMAC), role isolation (9 canonical roles, deny-by-default middleware), financial isolation (booking_state never contains financial data), PII protection (admin-only, signed URLs, audit logging), task automation (BOOKING_CREATED → 3 tasks), settlement terminal states, and the two-gate self check-in architecture.

**What needs structural fixes:** (1) Deposit UNIQUE constraint. (2) Payout persistence. (3) Storage bucket RLS verification. (4) Worker deactivation → task reassignment + session invalidation.

**What needs product completion:** (1) Guest checkout confirmation. (2) Guest satisfaction capture. (3) Owner notification system. (4) Statement email delivery. (5) Portal empty states for unconfigured properties.

**What needs design decisions:** (1) Settlement capability-gating: intentional role-only or should add financial capability? (2) Owner visibility: keep application-level or move to SQL-level? (3) Manager FULL_ACCESS in middleware: intentional trust or restrict to /manager/* prefixes?
