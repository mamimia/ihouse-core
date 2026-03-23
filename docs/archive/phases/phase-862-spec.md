# Phase 862 — Staff Onboarding Data Mapping Correction + Email Delivery UX

**Status:** Closed
**Prerequisite:** Phase 861 (Identity Merge & Auth Linking Closure)
**Date Closed:** 2026-03-24

## Goal

Completed a full correction pass on the staff onboarding → approval → staff-card data flow. All field mapping gaps identified in a live staging audit were resolved: Date of Birth, Passport/ID fields, Work Permit fields, role sub-selection, Full Name vs Display Name hierarchy. The mobile onboarding form received layout fixes (CC selector no flags, DOB on own row, emergency contact CC). Approval UX was upgraded with delivery status feedback and direct send shortcuts. Language-aware mailto templates added for admin email delivery (en/th/he) in both the invite generator and staff card resend flow.

## Invariant (if applicable)

- `Full Name` (real name) maps to `display_name` DB column; `Nickname/Display Name` maps to `comm_preference.preferred_name`
- Dedicated columns (`date_of_birth`, `id_number`, `id_expiry_date`, `work_permit_photo_url`, `work_permit_number`, `work_permit_expiry_date`, `id_photo_url`) are the canonical source of truth for compliance data — never `comm_preference` fallback
- Email copy for admin mailto flows is language-keyed (en/th/he) — falls back to `en` for unknown languages

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(public)/staff/apply/page.tsx` | MODIFIED — Mobile layout fixes: CC flags stripped, phone on own full-width row, DOB on own full-width row, emergency contact CC selector added (`ecCountryCode` state), `width:100%` + `boxSizing:border-box` on all date inputs, outer padding 16px, `MAILTO_TEMPLATES` not applicable here |
| `ihouse-ui/app/(app)/admin/staff/requests/page.tsx` | MODIFIED — `generatedForEmail` state tracks email used at generation; `Send by Email` button shown after Link/QR generate when email present; `MAILTO_ONBOARDING` dict with en/th/he templates; `getOnboardingMailto()` helper; approval success block with delivery status + WhatsApp/Telegram/Email/SMS send shortcuts |
| `ihouse-ui/app/(app)/admin/staff/[userId]/page.tsx` | MODIFIED — Profile tab: Full Name + Nickname as separate fields; header shows Full Name; Documents tab load uses dedicated DB columns (`id_number`, `id_expiry_date`, `work_permit_expiry_date`); Access & Comms tab: `Quick Send by Email` mailto block with `MAILTO_ACCESS` en/th/he templates; `getAccessMailto()` helper; resend result with magic link prefills mailto body |
| `src/api/staff_onboarding_router.py` | MODIFIED — `first_name`, `last_name`, `display_name` added to submit model; approval maps DOB, full name, all compliance columns; magic link always generated and returned; `_extract_action_link` hardened; `ApproveOnboardingRequest` default worker_roles changed to `[]` |

## Result

**7,765 backend tests — pre-existing count (no new tests added this phase; all session work is frontend + backend mapping fixes).**

Pre-existing test failures in unrelated areas (task model enum, wave contracts, notification chain integration) — none introduced by this session. All session-modified files compile cleanly (Next.js build: 0 TypeScript errors). Deployed to `domaniqo-staging.vercel.app` (Vercel) and Railway (auto). 6 commits pushed to `checkpoint/supabase-single-write-20260305-1747`.

### Commits This Phase
- `9a42c84` — Onboarding correction pass: mobile layout, name split, phone CC, comms validation, data mapping, first-access delivery
- `e8a206f` — Precision mapping fix: DOB/ID/WP columns, role sub-roles, name split, approval send UX
- `2d10d6d` — Staff card: add Full Name + separate Nickname field in Profile, fix header to show real name
- `1c5f9ea` — Mobile form: strip CC flags, DOB own row, emergency CC selector, grid overflow fixes
- `069f670` — mailto Send by Email: invite generator + staff card Access & Comms
- `411db64` — Language-aware mailto templates: en/th/he for invite + access link

### Pending (moved to deferred registry)
- Fresh E2E onboarding proof with photo upload (blocked by automated browser photo restriction)
- DOB/ID/WP mapping proof on a freshly approved record (requires manual QR scan + approval)
- Resend magic link direct send proof from staff card
