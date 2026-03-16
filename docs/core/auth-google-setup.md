# Google Sign-In + Supabase Auth — Setup Guide

This document covers everything needed to activate Google sign-in in Domaniqo.

## Architecture

```
User clicks "Sign in with Google"
  → supabase.auth.signInWithOAuth({ provider: 'google' })
  → Browser redirects to Google consent screen
  → Google redirects to Supabase callback (Supabase-managed URL)
  → Supabase exchanges code for tokens, creates/finds user
  → Supabase redirects to our /auth/callback page
  → Our callback calls POST /auth/google-callback
  → Backend resolves tenant/role, issues iHouse JWT
  → User enters the app
```

## Step 1: Google Cloud Console

1. Go to https://console.cloud.google.com/apis/credentials
2. Create project (or use existing)
3. Create **OAuth 2.0 Client ID** → type: **Web application**
4. **Authorized redirect URI** (critical):
   - Production: `https://<YOUR_SUPABASE_REF>.supabase.co/auth/v1/callback`
   - Local dev:  `http://127.0.0.1:54321/auth/v1/callback`
5. Copy **Client ID** and **Client Secret**

## Step 2: Supabase Dashboard

1. Go to your project → **Auth** → **Providers** → **Google**
2. Toggle **Enable**
3. Paste Client ID + Client Secret from Step 1
4. Under **Auth** → **URL Configuration**:
   - Add to **Redirect URLs**:
     - Production: `https://your-app.com/auth/callback`
     - Local:      `http://localhost:8001/auth/callback`

## Step 3: Environment Variables

In `ihouse-ui/.env.local`:
```
NEXT_PUBLIC_SUPABASE_URL=https://<YOUR_SUPABASE_REF>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-anon-key>
```

In backend `.env` (already configured):
```
SUPABASE_URL=https://<YOUR_SUPABASE_REF>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
IHOUSE_JWT_SECRET=<your-jwt-secret>
```

## Local Development Setup

For local Supabase (`supabase start`):
```
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<local-anon-key-from-supabase-start>
```

The local callback URL is: `http://127.0.0.1:54321/auth/v1/callback`

Add this to Google Cloud Console authorized redirects for dev testing.

## What's Already Built

### Frontend
- `lib/supabaseClient.ts` — browser Supabase client (null-safe if env vars missing)
- `components/auth/GoogleSignInButton.tsx` — branded Google "G" button
- `/auth/callback/page.tsx` — handles redirect after Google consent
- Google button wired in: `/login`, `/login/password`, `/register/email`

### Backend
- `POST /auth/google-callback` — resolves tenant + role, issues iHouse JWT
- Uses existing `tenant_bridge.py` for tenant lookup/provision
- Uses existing `session.py` for server-side session creation

### Decision Logic in Callback
1. User completes Google sign-in → Supabase creates auth user
2. `/auth/callback` calls `POST /auth/google-callback` with Supabase user ID
3. Backend checks `tenant_permissions` table:
   - **Row exists** → user is known → issue JWT → redirect to dashboard
   - **No row (403)** → new Google user → redirect to `/register/profile?google=1`
4. Profile completion provisions tenant_permissions + issues JWT

## Verification Checklist

- [ ] Google Cloud OAuth credentials created
- [ ] Supabase Google provider enabled with credentials
- [ ] `NEXT_PUBLIC_SUPABASE_URL` set in `.env.local`
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY` set in `.env.local`
- [ ] Test: click "Sign in with Google" → reaches Google consent screen
- [ ] Test: complete Google sign-in → returns to `/auth/callback`
- [ ] Test: existing user → gets JWT → reaches dashboard
- [ ] Test: new user → redirects to `/register/profile?google=1`
