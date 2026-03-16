> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Auth Flow Redesign (Post-Phase 801)

**Date:** 2026-03-16
**Last Closed Phase:** Phase 812 — PMS Pipeline Proof (48/48 passed)
**Current State:** Auth Flow Redesign complete (cross-cutting). Phases 801–812 closed with specs + ZIPs.

---

## 1. Auth Architecture (Important — Read This)

```
                    Supabase Auth (hosted: reykggmlcehswrxjviup)
                   (identity layer only)
                    /          \
          email+pw             Google OAuth
               \                  /
            Python Backend (/auth/login or /auth/google-callback)
                        |
              lookup_user_tenant(user_id)
                        |
                tenant_id + role
                        |
               iHouse JWT ← THIS IS THE SESSION
              {sub, tenant_id, role, exp=24h}
                        |
          ┌─────────────┼──────────────┐
          │             │              │
     ihouse_token   middleware.ts   getRoleRoute()
       cookie        route guard     landing page
```

- **Supabase handles identity** — both email/password and Google sign-in go through Supabase Auth
- **Backend resolves tenant + role** — `lookup_user_tenant()` against `tenant_permissions` table
- **iHouse JWT is the real app session** — stored in `ihouse_token` cookie, read by middleware
- **Both auth paths converge** — same JWT claims, same cookie, same middleware, same role routing

---

## 2. Auth Status — Precise Breakdown

### Proven now
- Email/password login end-to-end (backend → Supabase Auth → tenant → JWT → cookie → middleware → role surface)
- All 7 auth UI screens render correctly, LTR-aligned
- Smart country auto-detect + phone prefix + currency auto-fill (timezone heuristic, proven: Thailand → +66 → ฿ THB)
- Registration `signUp()` — creates real user in Supabase `auth.users` (verified via DB query)
- Forgot password `resetPasswordForEmail()` — API call succeeds, shows "Check your email"
- Supabase frontend client alive — `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` set in `.env.local`

### Partially proven (identity creation only, not full loop)
- Registration: `signUp()` creates identity, redirects to profile Step 3 — but Step 3 "Continue" → backend POST not tested (needs Python backend running)
- Forgot password: send confirmed, but email delivery, reset link, and `updateUser({password})` never tested (needs real inbox)

### Built but still unproven
- Google sign-in: all code paths exist (button → OAuth → callback → backend → JWT), but provider is not enabled in Supabase Dashboard
- `/auth/callback` page: reads Supabase session, POSTs to backend for JWT — never fired
- New vs existing Google user routing: existing → JWT, new → 403 → `/register/profile?google=1` — code ready, never tested
- Password reset full loop: token parsing, `updateUser()`, expired link detection — all code exists, never tested

### Blocked by your account access
- **Google Cloud OAuth**: create client ID + secret at console.cloud.google.com
- **Supabase Dashboard**: enable Google provider with OAuth credentials + set Redirect URI `https://reykggmlcehswrxjviup.supabase.co/auth/v1/callback`
- **Supabase Site URL**: verify it's set to `http://localhost:8001` (for dev) — needed for password reset redirect

### Placeholder or misleading only
- **Host users link**: `/login?role=host` — URL marker, zero behavior
- **Remember Me**: email saved to localStorage + 30-day cookie, but JWT expires 24h — no real persistent session. Backend returns `supabase_refresh_token` (line 202 of `auth_login_router.py`) but frontend ignores it
- **`provision_user_tenant()`**: uses hardcoded `DEFAULT_TENANT_ID` — not real multi-tenant

---

## 3. Repository State

### Files that changed (code)
| File | Type | Change |
|------|------|--------|
| `ihouse-ui/middleware.ts` | Modified | Added `/register`, `/auth` to PUBLIC_PREFIXES |
| `ihouse-ui/components/auth/AuthCard.tsx` | Modified | LTR lock + left-aligned forms |
| `ihouse-ui/app/(public)/login/page.tsx` | Modified | Host users link → `/login?role=host`, Google button |
| `ihouse-ui/app/(public)/login/password/page.tsx` | New | Email display + password + Sign In |
| `ihouse-ui/app/(public)/login/forgot/page.tsx` | New | Email input → `resetPasswordForEmail()` |
| `ihouse-ui/app/(public)/login/reset/page.tsx` | New | Token from hash → `updateUser({password})` |
| `ihouse-ui/app/(public)/register/email/page.tsx` | New | Email + password + portfolio → `signUp()` |
| `ihouse-ui/app/(public)/register/profile/page.tsx` | New | Smart country/phone/currency + profile POST |
| `ihouse-ui/app/(public)/auth/callback/page.tsx` | New | Google OAuth → session → backend → JWT |
| `ihouse-ui/components/auth/CountrySelect.tsx` | New | Searchable country picker |
| `ihouse-ui/lib/countryData.ts` | New | 200+ countries with phone/currency/timezone |
| `ihouse-ui/lib/supabaseClient.ts` | New | Supabase browser client (returns null if env missing) |

### Files that changed (config)
| File | Type | Change |
|------|------|--------|
| `ihouse-ui/.env.local` | Modified | Added `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` |
| `ihouse-ui/package.json` | Modified | Added `@supabase/supabase-js` dependency |

### Files that changed (docs)
| File | Type | Change |
|------|------|--------|
| `docs/core/phase-timeline.md` | Appended | Auth Flow Redesign entry |
| `docs/core/construction-log.md` | Appended | Auth Flow Redesign entry |
| `docs/core/auth-google-setup.md` | New | Google OAuth setup instructions |

### Not committed yet
All changes are local only. No git commit has been made in this session.

---

## 4. .env.local and Git Safety

- `.env.local` is in `.gitignore` ✅ — will NOT be committed
- `.env`, `.env.staging`, `.env.production` — all in `.gitignore` ✅
- `.venv/` — in `.gitignore` ✅
- **No secrets at risk** in git status
- **Nothing staged** — clean working tree with only unstaged changes

### .venv Note
`.venv` is the Python virtual environment. It was not used in this session and does not block git commit or push. It's procedural context only — activate when running/testing the Python backend, deactivate after. In `.gitignore`, will never enter the repository.

---

## 5. Documents Audited and Updated

| Document | Action | Status |
|----------|--------|--------|
| `docs/core/BOOT.md` | Read, followed protocol | No changes needed |
| `docs/core/current-snapshot.md` | Read | Not updated — auth work is cross-cutting, not a numbered phase. Snapshot reflects Phase 800/801 state. |
| `docs/core/work-context.md` | Read | Phase E (Mobile Cleaner Flow) still listed as next. Auth work is between Phase D and E. |
| `docs/core/phase-timeline.md` | **Appended** | Auth Flow Redesign entry added (append-only) |
| `docs/core/construction-log.md` | **Appended** | Auth Flow Redesign entry added (append-only) |
| `docs/core/auth-google-setup.md` | Created (previous session) | Google OAuth setup guide |
| Layer A docs (vision, system-identity, canonical-event-architecture) | Not touched | Immutable — no changes needed or allowed |
| `docs/core/governance.md` | Not touched | No changes needed |

### Documentation gap
`current-snapshot.md` and `work-context.md` do not mention the auth flow redesign or the `.env.local` Supabase config addition. This is acceptable because it's cross-cutting work, not a numbered phase. The next numbered phase closure should update these docs if auth state is referenced.

---

## 6. Git Commit Guidance

### Is repo clean enough to commit?
**Yes.** All changes are meaningful and coherent (auth flow redesign).

### What should be committed
```
ihouse-ui/middleware.ts
ihouse-ui/components/auth/AuthCard.tsx
ihouse-ui/components/auth/CountrySelect.tsx
ihouse-ui/lib/countryData.ts
ihouse-ui/lib/supabaseClient.ts
ihouse-ui/app/(public)/login/page.tsx
ihouse-ui/app/(public)/login/password/
ihouse-ui/app/(public)/login/forgot/
ihouse-ui/app/(public)/login/reset/
ihouse-ui/app/(public)/register/
ihouse-ui/app/(public)/auth/
ihouse-ui/package.json
ihouse-ui/package-lock.json
docs/core/phase-timeline.md
docs/core/construction-log.md
docs/core/auth-google-setup.md
releases/handoffs/handoff_to_new_chat_Auth-Flow-Redesign.md
```

### What must NOT be committed
- `ihouse-ui/.env.local` — already in `.gitignore`, will be excluded automatically
- `.env` files — all in `.gitignore`
- `.venv/` — in `.gitignore`

### Other modified files (from other sessions, review before committing)
```
.agent/workflows/session-start.md
docs/core/roadmap.md
docs/core/work-context.md
ihouse-ui/app/(app)/admin/page.tsx
ihouse-ui/app/(app)/admin/properties/[propertyId]/page.tsx
ihouse-ui/app/(app)/admin/staff/page.tsx
ihouse-ui/app/(app)/dashboard/page.tsx
ihouse-ui/app/(app)/ops/checkin/page.tsx
ihouse-ui/app/(app)/settings/page.tsx
src/api/auth_login_router.py
src/api/booking_checkin_router.py
```
These were modified in previous sessions. Review them before including in a commit.

### Is push needed now?
**Commit yes, push optional.** There's no deployment urgency. A local commit preserves the work. Push when ready.

---

## 7. Next Chat — Two Paths

### Path A: Close Google Auth
**What's needed from you:**
1. Go to [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → OAuth Consent Screen → Create
2. Create OAuth client (Web application) → Authorized redirect URI: `https://reykggmlcehswrxjviup.supabase.co/auth/v1/callback`
3. Copy Client ID + Client Secret
4. Go to [Supabase Dashboard](https://supabase.com/dashboard/project/reykggmlcehswrxjviup/auth/providers) → Auth → Providers → Google → Enable → Paste Client ID + Secret
5. Verify Site URL is `http://localhost:8001` and Redirect URLs include `http://localhost:8001/auth/callback`

**What I can do after that:**
- Test Google sign-in end-to-end
- Verify callback → backend → JWT → role routing
- Verify new user → register flow
- Verify existing user → app entry

**Proof of completion:** User logs in with Google → lands on correct role surface with valid iHouse JWT.

### Path B: Start Phase E — Mobile Cleaner Flow
**System readiness:**
- Phase D (Mobile Check-in) complete: 6-step flow, 50 real bookings, tenant-wide scope
- Backend task system exists: task_model, task_automator, task_writer, sla_engine
- Worker task API: GET /tasks, PATCH /acknowledge, PATCH /complete
- Properties seeded in Supabase (3 properties, 7 channel mappings)

**What needs definition before starting:**
- Cleaner flow scope: what are the steps? (property arrival → checklist → photo evidence → completion?)
- Mobile-first or responsive?
- Connected to existing task system or new flow?
- Real backend wiring or UI-only Phase D style?

---

## 8. Final Summary

### 1. What is truly working now
- Email/password login e2e through Supabase Auth + backend + JWT + cookie + middleware + role routing
- All 7 auth UI screens render correctly
- Smart country/phone/currency auto-fill
- Supabase frontend client is connected and functional

### 2. What is only partially proven
- Registration: identity creation works, profile → backend POST not tested
- Forgot password: API send works, email delivery + reset page not tested
- Remember Me: email convenience works, session persistence does not (JWT 24h)

### 3. What is blocked externally
- Google sign-in: needs Google Cloud OAuth client + Supabase provider setup (your accounts)
- Forgot password full loop: needs real inbox or Supabase Dashboard email template check
- Remember Me real persistence: needs product decision + refresh token implementation

### 4. What is misleading or placeholder only
- Host users link — URL marker, zero behavior
- Remember Me — 30-day cookie holding a 24h JWT
- `provision_user_tenant()` — hardcoded single tenant
- Expired-link detection — string matching, not error codes

### 5. What the next chat must do first
- Decide: **Path A** (close Google auth) or **Path B** (start Phase E Mobile Cleaner Flow)
- If Path A: you provide Google Cloud OAuth credentials first
- If Path B: define cleaner flow scope and steps
- Either way: consider doing `git commit` on auth work before starting new work
