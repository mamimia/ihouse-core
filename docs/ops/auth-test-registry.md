# auth-test-registry.md
# iHouse Core — Auth & Test Identity Registry
# ============================================
# Phase 839 — Canonical source of truth for all login identities and auth flows.
# BOOT protocol points here. Do NOT duplicate this data in BOOT.
#
# SECURITY: Passwords here are dev/staging only. Never use in production.
# Last updated: 2026-03-18

---

## A. Test Identity Registry

### Confirmed Existing Users (Supabase Auth — Staging/Dev)

| Role    | Email                      | Password    | Tenant                   | Login Route       | Expected Landing        | Status        | Notes |
|---------|----------------------------|-------------|--------------------------|-------------------|-------------------------|---------------|-------|
| admin   | admin@domaniqo.com         | Admin123!   | tenant_mamimia_staging   | /login            | /dashboard              | ✅ browser-proven | Phase 839. Supabase UUID: 25407914. tenant_permissions row id=24 inserted. |
| manager | manager@domaniqo.com       | Manager123! | tenant_mamimia_staging   | /login            | /dashboard              | ✅ proven         | Supabase UUID: ecc69a1a. tenant_permissions row id=25 inserted. Password not browser-proven yet. |
| worker  | worker@domaniqo.com        | Worker123!  | tenant_mamimia_staging   | /login            | /worker                 | 🟡 password unknown | Supabase UUID: 19f9f4ed. tenant_permissions row id=26 inserted (role=worker, worker_role=cleaner). Reset password via Supabase admin if needed. |
| cleaner | —                          | —           | —                        | invite flow only  | /worker (cleaner role)  | ⬜ not created | Must be created via invite. No direct email/password exists yet. |
| check-in| —                          | —           | —                        | invite flow only  | /checkin                | ⬜ not created | Must be created via invite. |
| checkout| —                          | —           | —                        | invite flow only  | /checkout               | ⬜ not created | Must be created via invite. |
| maintenance | —                      | —           | —                        | invite flow only  | /worker (maintenance)   | ⬜ not created | Must be created via invite. |
| owner   | —                          | —           | —                        | invite flow only  | /owner                  | ⬜ not created | Must be created via invite. |
| guest   | n/a (token-based)          | n/a         | n/a                      | /guest/{token}    | /guest/{token}          | ✅ proven     | No email/password. Access via UUID token or QR link only. |

### Notes
- **worker@domaniqo.com password unknown** — reset it via Supabase Admin if needed: `supabase.auth.admin.update_user_by_id(uid, {password: 'Worker123!'})`
- Role for worker/cleaner determined by `permissions` table `worker_role` field, not Supabase role.
- All operational users (worker, cleaner, checkin, checkout, maintenance, owner) should be created via the invite flow (`/invite/{token}`) for production-like setup.

---

## B. Login Flow Truth

### When to use /login (email + password)
- Admin testing, manager testing, any user with a known Supabase email+password.
- Route: `/login` → email step → `/login/password` → JWT issued → redirected by `getRoleRoute(token)`.
- Requires backend alive on `:8000`.

### When to use /auth/dev-login (deprecated — do not use)
- Was used pre-Phase 795 for dev-mode API key login.
- Now disabled/renamed. Do NOT use for any proof or testing.
- If it still exists in code: it's legacy. Ignore it.

### When to use invite flow
- For all operational roles (worker, cleaner, check-in, checkout, maintenance, owner).
- Admin creates invite → user receives link `/invite/{token}` → sets password → account created.

### When to use guest token / QR link
- Guest access only. No Supabase account required.
- Link: `/guest/{token}` where token is a UUID from `guest_tokens` table.
- Token auto-generated from booking on booking creation.
- QR image generated from the link.

### What is forbidden
- Do NOT guess passwords. If unknown, reset via Supabase Admin or use invite flow.
- Do NOT try `/auth/dev-login` for real session proofs.
- Do NOT use Google OAuth for automated browser proofs (requires OAuth consent screen).

---

## C. Deterministic Login Runbook

```
1. CLEAR stale session
   - Run in browser console: localStorage.clear()
   - Or navigate to /login directly (middleware will clear if token invalid)

2. USE exact identity from registry above
   - admin@domaniqo.com / Admin123!  ← preferred for most proofs

3. USE exact route
   - Navigate to: http://localhost:3000/login
   - Enter email → Continue → enter password → Sign In

4. VERIFY landing route
   - Admin/manager → should land on /admin or /dashboard
   - Worker → /worker
   - Guest → /guest/{token} (separate flow, no login)

5. IF login fails
   A. Check backend alive: curl -s --max-time 3 http://localhost:8000/health
   B. Check CORS: OPTIONS /auth/login should return 200 with Access-Control-Allow-Origin
   C. Check password: Admin123! (capital A, ends with !)
   D. Report exact error from browser console, not assumption
```
