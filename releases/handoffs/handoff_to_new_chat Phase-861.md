> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 861 → Phase 862

**Date:** 2026-03-23
**Current Phase:** 862 (Next Phase — not yet scoped)
**Last Closed Phase:** 861 — Identity Merge & Auth Linking Closure

---

## What Phase 861 Accomplished

1. **Identity merge** — Two separate Supabase auth users for the same human (admin@domaniqo.com `25407914` + esegeve@gmail.com `736f4d6a`) were unified.
   - Canonical admin identity: `25407914-2071-4ee8-b8ae-8aa5967d8f20` (admin@domaniqo.com)
   - Deleted duplicate: `736f4d6a-4c75-470a-ae84-cad9581a1a44` (esegeve@gmail.com)
   - 2 rejected test property rows migrated before deletion
   - User manually linked Google identity via product UI — both email + google now on single UUID

2. **linkIdentity callback fix** — Callback at `/auth/callback` now preserves origin route via sessionStorage (`ihouse_linking_return`). Admin linking returns to `/admin/profile`, public linking returns to `/profile`.

3. **Profile UI improvements** — Both admin and public profiles now show:
   - "Currently logged in with: admin@domaniqo.com" (just email, no method label)
   - Provider pills with actual emails: "📧 Email/Password — admin@domaniqo.com"
   - Explicit "Unlink" button instead of cryptic ✕

4. **Backend provider details** — `GET /auth/profile` now returns `providers` as `[{provider, email}]` objects + `auth_method` + `auth_email` fields.

---

## Key Files Changed in Phase 861

| File | What Changed |
|------|-------------|
| `src/api/auth_router.py` | GET /auth/profile returns provider details with emails, auth_method, auth_email |
| `ihouse-ui/lib/identityLinking.tsx` | Stores `ihouse_linking_return` before linkIdentity redirect |
| `ihouse-ui/app/(public)/auth/callback/page.tsx` | Uses stored return route instead of hardcoded /profile |
| `ihouse-ui/app/(app)/admin/profile/page.tsx` | ProviderInfo interface, simplified login status, explicit Unlink, provider emails |
| `ihouse-ui/app/(public)/profile/page.tsx` | Same UI changes as admin profile |

---

## System State After Phase 861

### Canonical Admin Identity
- UUID: `25407914-2071-4ee8-b8ae-8aa5967d8f20`
- Email: admin@domaniqo.com
- Providers: email (admin@domaniqo.com) + google (esegeve@gmail.com)
- tenant_permissions row #24: admin role, "Elad Mami"

### Staging Deployment
- Frontend: `https://domaniqo-staging.vercel.app` (Vercel)
- Backend: Railway (auto-deploys from git push)
- Database: Supabase (`reykggmlcehswrxjviup`)
- Git branch: `checkpoint/supabase-single-write-20260305-1747` synced to `main`

### Deployment Rules
See `docs/core/BOOT.md` → deployment rules, and `.agent/workflows/deployment-rules.md`.

---

## Known Open Items / Deferred from This Session

| Item | Status | Notes |
|------|--------|-------|
| Language localization incomplete | 🟡 Deferred | Language save works in backend/localStorage/context. Sidebar responds. Most admin pages still hardcoded English. Multi-phase effort to localize all pages. |
| Phone field country-code selector | ✅ Done | Already uses country code picker in current profile UIs |
| Public Google linking | ✅ Fixed | Same shared linkGoogleAccount + callback return route |
| Duplicate identity prevention | 🟡 Open | `/auth/google-callback` should check for existing auth user with same email before creating duplicate tenant_permissions row |

---

## Next Objective Suggestions

1. **Language localization Phase A** — Start localizing admin pages (Profile → Dashboard → Intake → remaining)
2. **Duplicate identity prevention** — Add guard in `/auth/google-callback` to prevent future duplicate user creation
3. **Intake detail improvements** — Continue enriching the admin intake detail view with submitter context
4. **Product readiness audit** — Full walkthrough of all user flows on staging

---

## Document Authority Reminder

Read docs in this order:
1. `docs/core/BOOT.md`
2. Layer A (vision.md, system-identity.md, canonical-event-architecture.md)
3. `docs/core/governance.md`
4. `docs/core/current-snapshot.md`
5. `docs/core/work-context.md`
6. `docs/core/IDENTITY.md` (auth/identity model)
7. `docs/core/phase-timeline.md` (latest section)
