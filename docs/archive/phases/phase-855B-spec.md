# Phase 855B — Google OAuth Staging Setup

**Status:** Closed
**Prerequisite:** Phase 855A (Staging Runtime Verification)
**Date Closed:** 2026-03-20

## Goal

Configure Google OAuth provider in Supabase for the staging environment and verify the redirect flow from staging frontend through Supabase to Google and back.

## Design / Files

| File | Change |
|------|--------|
| Supabase Dashboard | MODIFIED — Site URL set to `https://domaniqo-staging.vercel.app`, Redirect URL set to `https://domaniqo-staging.vercel.app/auth/callback` |
| Google Cloud Console | MODIFIED — OAuth 2.0 Client created with authorized JS origin `https://domaniqo-staging.vercel.app` and redirect URI `https://reykggmlcehswrxjviup.supabase.co/auth/v1/callback` |
| Supabase Auth Providers | MODIFIED — Google provider enabled with client ID and client secret |

## Result

Google OAuth redirect flow proven:
- Staging frontend → Supabase → Google consent screen → Supabase callback → staging frontend `/auth/callback`
- No CORS, provider, or redirect URI blockers present
- Setup-proven (redirect works), not yet end-to-end-proven (full sign-in not yet tested)
