> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 862 → Phase 863

**Date:** 2026-03-24
**Time (Bangkok):** 03:13
**Prepared by:** Antigravity session `156e5642`

---

## Current Phase

**Phase 863 — Next Phase** (not yet started)

## Last Closed Phase

**Phase 862 — Staff Onboarding Data Mapping Correction + Email Delivery UX**

Spec: `docs/archive/phases/phase-862-spec.md`
ZIP: `releases/phase-zips/iHouse-Core-Docs-Phase-862.zip`

---

## What Was Accomplished in This Session

### Phase 862 (full closure — 6 commits)

| Commit | Description |
|--------|-------------|
| `9a42c84` | Onboarding correction pass: mobile layout, name split, phone CC, comms validation, data mapping, first-access delivery |
| `e8a206f` | Precision mapping fix: DOB/ID/WP columns, role sub-roles, name split, approval send UX |
| `2d10d6d` | Staff card: Full Name + Nickname separated in Profile, header fixed |
| `1c5f9ea` | Mobile form: strip CC flags, DOB own row, emergency CC selector, grid overflow fixes |
| `069f670` | mailto Send by Email: invite generator (Link + QR) + staff card Access & Comms |
| `411db64` | Language-aware mailto templates: en/th/he for both invite and access link |
| `dff9904` | Phase 862 closure docs: spec, timeline, construction-log, snapshot, work-context, ZIP |

### Key Files Changed

| File | What Changed |
|------|-------------|
| `ihouse-ui/app/(public)/staff/apply/page.tsx` | CC flags stripped; Phone on own full-width row; DOB on own full-width row; Emergency Contact CC selector added (`ecCountryCode`); outer padding 16px; all date inputs `width:100%` + `boxSizing:border-box` |
| `ihouse-ui/app/(app)/admin/staff/requests/page.tsx` | `generatedForEmail` state; `Send by Email` after Generate Link + Generate QR when email exists; `MAILTO_ONBOARDING` dict (en/th/he); `getOnboardingMailto()` helper |
| `ihouse-ui/app/(app)/admin/staff/[userId]/page.tsx` | Profile tab: Full Name + Nickname as separate fields; header = Full Name; Documents tab reads from dedicated DB columns; `MAILTO_ACCESS` dict (en/th/he); `getAccessMailto()` + `Quick Send by Email` block in Access & Comms |
| `src/api/staff_onboarding_router.py` | `first_name`/`last_name`/`display_name` wired through submit → approval; magic link always returned; `_extract_action_link` hardened; `ApproveOnboardingRequest.worker_roles` default = `[]` |

---

## Staging Deployment

| Component | URL | Status |
|-----------|-----|--------|
| Frontend | `https://domaniqo-staging.vercel.app` | ✅ Live (latest deploy) |
| Backend | Railway | ✅ Live (auto-deploy from `checkpoint/supabase-single-write-20260305-1747`) |
| Database | Supabase `reykggmlcehswrxjviup` | ✅ Connected |

---

## Open Items / Deferred to Phase 863

> These items require a real human doing a fresh E2E onboarding run (photo upload cannot be automated):

| Item | What to Verify | How |
|------|---------------|-----|
| DOB mapping | Worker fills DOB → approve → staff card shows it | Fresh QR onboarding on phone + approve in admin |
| Passport ID/Expiry mapping | ID number + expiry date persisted and shown | Same fresh run |
| Work Permit mapping | WP number + expiry date persisted and shown | Same fresh run |
| Magic link click-through | Approved worker receives invite, logs in, sets password | Real inbox required |
| Staff photo bucket migration | 8 existing files in old bucket need migrating to `staff-documents` | DBA task or manual move |
| Resend .magic_link → mailto E2E | After Send Access Link, mailto prefills with real link | Manual test from admin card |

---

## Test Suite Status

- **7,765 backend tests** — pre-existing count (this phase: no new backend tests)
- **Pre-existing failures** (not introduced by this session):
  - `test_task_model_contract.py` — WorkerRole enum count mismatch (old test, enum evolved)
  - `test_notification_fullchain_integration.py` — dispatcher channel test
  - `test_properties_router_contract.py` — contract tests against old property shape
  - `test_wave4/6/7` — wave contract tests, not updated to match current model
  - `test_sla_task_integration.py` — chain integration
  - `test_whatsapp_escalation_contract.py` — per-worker routing test
- **0 new failures** from Phase 862 work

---

## Key Invariants to Remember

- `Full Name` = `display_name` DB column (real name, required)
- `Nickname` = `comm_preference.preferred_name` (optional)
- Compliance columns (`date_of_birth`, `id_number`, `id_expiry_date`, `id_photo_url`, `work_permit_number`, `work_permit_expiry_date`, `work_permit_photo_url`) are canonical — do NOT fall back to `comm_preference`
- mailto email copy is language-keyed: `genLanguage` (invite) / `language` state (staff card) → `en` fallback
- Hebrew body lines get U+200F (RLM) prefix for RTL rendering
- All mailto is **temporary** — replace with Resend backend when email infra is provisioned

---

## Immediate Next Steps for Phase 863

1. **Manual E2E onboarding run** — do a fresh QR scan on real phone, fill all fields including photo, approve, verify every field on staff card
2. **Decide on Resend integration** — replace mailto with proper backend email sending (`src/api/staff_onboarding_router.py` + staff card resend)
3. **Pre-existing test failures** — decide whether to fix the stale test contracts or leave as known-deferred
4. **Staff photo bucket migration** — migrate 8 files from old bucket to `staff-documents`

---

## Branch

`checkpoint/supabase-single-write-20260305-1747`
Latest commit: `dff9904` (Phase 862 closure docs)
