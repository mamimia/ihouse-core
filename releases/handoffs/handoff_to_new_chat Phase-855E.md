> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff Document — Phase 855E → Phase 856

**Date:** 2026-03-20
**Last Commit:** `f53cc68` on branch `checkpoint/supabase-single-write-20260305-1747`
**Repo:** `github.com/mamimia/ihouse-core`

---

## BOOT Protocol

Before doing anything, read `docs/core/BOOT.md` — it defines the mandatory closure protocol for every phase. Key rules:
- Every phase closure MUST update: `phase-timeline.md` (append-only), `construction-log.md` (append-only), `current-snapshot.md`, `work-context.md`
- Phase specs go in `docs/archive/phases/phase-{N}-spec.md`
- ZIP archive of `docs/core/` at closure
- Git commit + push before starting next large task

---

## 1. What Is This Project

**iHouse Core** (branded **Domaniqo**) is a property management platform for short-term rental operators in Thailand. It manages:
- Multi-OTA booking ingestion (14 adapters: Booking.com, Airbnb, Expedia, Agoda, etc.)
- Event-sourced booking lifecycle (append-only `event_log`, single write gate `apply_envelope`)
- Task automation for workers (cleaners, check-in staff, maintenance)
- Financial tracking (commission extraction, owner statements, reconciliation)
- Multi-channel notifications (LINE, Telegram, WhatsApp, SMS, Email)
- Staff onboarding with admin approval pipelines

### Tech Stack
- **Backend:** Python FastAPI, deployed on **Railway** (staging)
- **Frontend:** Next.js (App Router), deployed on **Vercel** (staging)
- **Database:** Supabase (PostgreSQL + Auth + Storage)
- **Staging URL:** `https://domaniqo-staging.vercel.app`
- **Supabase project:** `reykggmlcehswrxjviup`

---

## 2. Current System State

### What Is Proven & Live

| Item | Status |
|------|--------|
| Staging frontend (Vercel) | ✅ Live |
| Staging backend (Railway) | ✅ Live |
| Supabase connectivity | ✅ Proven |
| CORS configuration | ✅ Correct |
| Password auth E2E | ✅ Proven (`admin@domaniqo.com` / `Admin123!`) |
| Google OAuth E2E | ✅ Proven (test account `esegeve@gmail.com`) |
| Dashboard with real data | ✅ Proven |
| `/admin/properties` authenticated | ✅ Proven — no loop, no crash |
| LINE integration | ✅ E2E proven (webhook + dispatch) |
| Telegram integration | ✅ E2E proven |
| Two onboarding pipelines | ✅ Audited and documented |

### What Is Open / Broken

| Item | Priority | Detail |
|------|----------|--------|
| **Auto-provision vulnerability** | 🔴 CRITICAL | `/auth/register/profile` endpoint (in `src/api/auth_login_router.py`, around line 345-420) auto-provisions ANY Google user as `manager` role on the default tenant. Any person who signs in with Google gets full manager access without admin approval. This MUST be closed. |
| **Admin email mismatch** | 🟠 HIGH | The existing admin account in Supabase Auth uses `admin@domaniqo.com` (email/password). The owner's real Google account is `esegeve@gmail.com`. These are different emails. Google sign-in cannot see the existing admin's `tenant_permissions` row. **Recommended fix:** change the admin's Supabase Auth email to their Gmail, so Google login finds the existing binding. |
| **Orphan tenant_permissions row** | 🟡 MEDIUM | During Google OAuth testing, a manual `tenant_permissions` row was inserted for `esegeve@gmail.com`. This should be **deleted** after the admin email is changed to Gmail (which will make the original row usable). |
| **Linked identity tables** | ⏸ DEFERRED | A full identity architecture was designed (see `auth_identity_architecture.md` artifact in previous conversation) with `internal_users`, `linked_identities`, `leads` tables. The audit concluded this is **over-engineered for current scope**. Keep existing system. Revisit only when there's a real use case for linking different-email identities. |

---

## 3. Key Files You Must Know

### Auth & Identity (the area with open work)

| File | What It Does |
|------|-------------|
| `src/api/auth_login_router.py` | Main auth router. Contains `/auth/login` (email/password), `/auth/google-callback` (Google OAuth), `/auth/register/profile` (🔴 THE VULNERABILITY — auto-provisions users). Lines ~220-340 = Google callback, lines ~345-420 = register/profile. |
| `src/services/tenant_bridge.py` | Bridges Supabase Auth UUID → iHouse tenant. `provision_user_tenant()` creates `tenant_permissions` rows. `lookup_user_tenant()` finds existing bindings. |
| `src/api/invite_router.py` | **Pipeline A** — Simple invite flow. Admin creates token → user validates → accepts → gets account. Phase 401. |
| `src/api/staff_onboarding_router.py` | **Pipeline B** — Rich staff self-onboarding. Admin generates link/QR → candidate fills form (name, phone, DOB, selfie, ID, roles, channels) → admin approves → magic link activation. Phase 844. |
| `src/services/access_token_service.py` | Universal HMAC-SHA256 token system for invites and onboarding. |
| `ihouse-ui/app/(auth)/login/page.tsx` | Login page with email/password + Google OAuth button |
| `ihouse-ui/app/(public)/auth/callback/page.tsx` | OAuth callback handler (receives code from Supabase, calls backend) |
| `ihouse-ui/lib/roleRoute.ts` | Role-based routing after login (manager→dashboard, worker→worker, owner→owner) |
| `ihouse-ui/middleware.ts` | Next.js edge middleware — route protection, auth redirects |

### Frontend Key Pages

| Route | Description |
|-------|-------------|
| `/dashboard` | Operations dashboard — portfolio grid, 60s auto-refresh |
| `/admin/properties` | Property management list |
| `/admin/properties/[id]` | Property detail (6-tab: Overview, House Info, Photos, Tasks, Issues, Audit) |
| `/admin/staff/*` | Staff management (list, detail, invite, pending requests) |
| `/worker/*` | Worker mobile app (Home, Tasks, Done, Profile tabs) |
| `/ops/checkin` | Mobile check-in flow (6 steps) |
| `/ops/checkout` | Mobile checkout flow |
| `/ops/cleaner` | Cleaner task view |
| `/ops/maintenance` | Maintenance task view |
| `/owner` | Owner portal |
| `/staff/apply` | Public staff self-onboarding form |
| `/invite/[token]` | Public invite acceptance page |

### Core Documents

| File | Purpose |
|------|---------|
| `docs/core/BOOT.md` | Closure protocol — READ FIRST |
| `docs/core/current-snapshot.md` | Current phase state + system status |
| `docs/core/work-context.md` | Active context for resuming work |
| `docs/core/phase-timeline.md` | Append-only phase chronicle |
| `docs/core/construction-log.md` | What was actually built, in order |
| `docs/core/live-system.md` | Technical architecture + full API surface |

---

## 4. The Two Onboarding Pipelines (DO NOT BREAK)

### Pipeline A — Simple Invite (`invite_router.py`)
```
Admin creates invite token (role + tenant)
→ Candidate opens /invite/[token]
→ Sees role + org → clicks Accept
→ Creates email/password account
→ Token consumed → tenant_permissions created
→ Redirected to login
```

### Pipeline B — Staff Self-Onboarding (`staff_onboarding_router.py`)
```
Admin generates invite link/QR
→ Candidate opens /staff/apply?token=...
→ Fills rich form (name, phone, DOB, selfie, ID photo, emergency contact, 
   worker roles, preferred channel: LINE/WhatsApp/Telegram)
→ Submission lands in Pending Approval
→ Admin reviews in /admin/staff/requests
→ Approve → magic link sent → account activated → tenant_permissions created
→ Reject → candidate notified
```

**Neither pipeline should be modified unless specifically requested.**

---

## 5. Google OAuth Configuration (Current State)

| Setting | Value |
|---------|-------|
| Supabase Site URL | `https://domaniqo-staging.vercel.app` |
| Supabase Redirect URL | `https://domaniqo-staging.vercel.app/auth/callback` |
| Google OAuth Client ID | `406629033916-cbh4h6sdp9eldblrtfnjavd94h1fg2m0.apps.googleusercontent.com` |
| Google Authorized JS Origin | `https://domaniqo-staging.vercel.app` |
| Google Authorized Redirect URI | `https://reykggmlcehswrxjviup.supabase.co/auth/v1/callback` |
| Provider Status | ✅ Enabled in Supabase |

**DO NOT** add `staging.domaniqo.com` or any custom domain redirect URLs yet — DNS is not connected.

---

## 6. The Auto-Provision Vulnerability (CRITICAL)

**Location:** `src/api/auth_login_router.py` → `/auth/register/profile` endpoint

**What happens today:**
1. Any person signs in with Google
2. If they have no `tenant_permissions` row, they get redirected to `/register/profile`
3. The profile form collects basic info and calls `/auth/register/profile`
4. That endpoint calls `tenant_bridge.provision_user_tenant()` which creates a `tenant_permissions` row with **role = manager** on the **default tenant**
5. The person now has full manager access to the system

**What should happen:**
- If a Google user has no existing `tenant_permissions` binding, they should NOT be auto-provisioned
- They should either:
  - Be shown a "no access" / "contact your administrator" page, OR
  - Be redirected to an intake/request-access form that enters a pending approval queue
- Only admin-approved flows (Pipeline A invite or Pipeline B onboarding) should create `tenant_permissions`

**Recommended minimal fix:**
- Remove the auto-provisioning logic from `/auth/register/profile`
- Return a clear "no access" response for unbound Google users
- Keep the endpoint functional for the existing email/password registration flow if needed

---

## 7. Recommended Next Actions (Priority Order)

### Immediate (Phase 856)
1. **Fix auto-provision vulnerability** — Modify `/auth/register/profile` to stop creating `tenant_permissions` for arbitrary Google users
2. **Change admin email** — Update the admin's Supabase Auth email from `admin@domaniqo.com` to `esegeve@gmail.com` (user must confirm they want this)
3. **Delete orphan row** — Remove the test `tenant_permissions` entry for `esegeve@gmail.com` Supabase Auth UUID

### Soon After
4. **HMR flicker fix** — There's a known infinite HMR loop issue in the Next.js frontend (referenced in conversations `c8d7b084` and `a4f5b88c`). Related to `middleware.ts`. May need investigation.
5. **Worker router fixes** — Some contract tests were being fixed (conversation `0e9775e6`), specifically around `TypeError: Object of type MagicMock is not JSON serializable`

### Deferred
6. Custom domain setup (Namecheap DNS)
7. LINE/WhatsApp auth flows
8. Linked identity tables (`internal_users`, `linked_identities`, `leads`)

---

## 8. Git State

```
Branch: checkpoint/supabase-single-write-20260305-1747
Last commit: f53cc68
Remote: origin (github.com/mamimia/ihouse-core)
Status: CLEAN (no uncommitted changes)
```

---

## 9. Test State

- **Backend:** 7,765+ tests, 0 failed, 12 skipped, 281 test files
- **Frontend:** TypeScript 0 errors (as of Phase 390 checkpoint)
- **RLS:** 48 protected tables
- **Storage:** 4 Supabase buckets

---

## 10. User Preferences (Important)

- **Language:** The user communicates in Hebrew and English interchangeably. Respond in the language they use.
- **BOOT protocol:** Follow `docs/core/BOOT.md` strictly. The user cares deeply about clean phase closures.
- **No premature config:** Don't add future-state URLs or DNS entries before they're connected.
- **No secrets in chat:** Don't paste OAuth client secrets or API keys into chat messages.
- **Audit before redesign:** Always audit existing systems before proposing architecture changes. The existing onboarding pipelines are already more capable than they might seem at first glance.
- **Minimize over-engineering:** The user explicitly rejected the full linked-identity architecture (Phase 855D) as over-engineered. Keep things simple and functional.
- **External branding:** The product name for all outbound/external communication is **Domaniqo**, not iHouse.

---

## 11. Conversation Artifacts (Previous Session)

These artifacts were created in the conversation that produced this handoff. They're in the Antigravity brain directory for that conversation (`4fda3700-0dc3-4f63-a6fa-99dba9646792`):

| Artifact | Description |
|----------|-------------|
| `auth_identity_architecture.md` | Full identity model design — DEFERRED, keep as reference only |
| `onboarding_pipeline_audit.md` | Audit of both onboarding pipelines + Google OAuth conflict analysis |
| `implementation_plan.md` | Closure plan that was executed |
| `walkthrough.md` | Closure report with commit details |

---

## 12. Supabase Tables (Auth-Related)

| Table | Purpose |
|-------|---------|
| `auth.users` | Supabase Auth managed — login identities (email/password + Google) |
| `tenant_permissions` | iHouse managed — maps Supabase Auth UUID → tenant_id + role + permissions + profile data |
| `access_tokens` | HMAC-SHA256 tokens for invites/onboarding (types: INVITE, ONBOARD, GUEST) |
| `tenant_integrations` | Per-tenant API keys for LINE, Telegram, WhatsApp, SMS |
| `notification_channels` | Per-worker channel preferences for notification routing |

The **authoritative identity today** is: `Supabase Auth UUID` → looked up in `tenant_permissions` → returns `tenant_id`, `role`, `display_name`, and all profile/permissions data.

---

## TL;DR for the Next Chat

1. Read `docs/core/BOOT.md` and `docs/core/work-context.md`
2. The staging is live and proven
3. Google OAuth works but has a security hole — fix `/auth/register/profile` first
4. Don't touch the existing onboarding pipelines
5. The linked-identity architecture is deferred — don't build it
6. Follow BOOT protocol for any phase closure
