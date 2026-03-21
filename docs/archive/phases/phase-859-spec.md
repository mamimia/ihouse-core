# Phase 859 — Admin Intake Queue + Property Submit API + Login UX + Draft Expiration

**Date:** 2026-03-21
**Status:** ✅ Closed

## Objective

Implement the Priority A items identified in the Phase 858 follow-up audit — operational surfaces that were missing for the onboarding pipeline to function end-to-end.

## Items Implemented

### 1. Admin Intake Queue (NEW)
- **UI:** `app/(public)/admin/intake/page.tsx` — 694-line React component
  - Filterable table of submitted properties
  - Status filter (all, pending_review, approved, rejected)
  - Approve/reject actions with rejection reason modal
  - Displays: property name, address, type, rooms, submitted date, status
- **API:** `app/api/admin/intake/route.ts` — 204-line API route
  - `GET` — list properties by status (default: pending_review)
  - `POST` — approve or reject a property, with optional rejection reason
  - Admin role enforcement via JWT

### 2. Property Submit API (NEW)
- **API:** `app/api/properties/[propertyId]/submit/route.ts` — 97-line API route
  - `PATCH` — transitions a draft property to `pending_review`
  - Verifies user ownership of the property
  - Sets `submitted_at` timestamp
  - Auth enforcement

### 3. Login UX Redesign (MODIFIED)
- **File:** `app/(auth)/login/page.tsx`
- Google Sign-In button moved to top of authentication card (above email form)
- Added helper text: "Signed up with Google? Use this to sign back in."
- Divider updated to "OR SIGN IN WITH EMAIL"
- Email/password form remains below divider

### 4. 90-Day Draft Expiration (NEW logic in existing route)
- **File:** `app/api/properties/mine/route.ts`
- Lazy expiration: when a user fetches their properties, any draft older than 90 days from `created_at` is auto-marked as `expired`
- Fire-and-forget PATCH back to Supabase (non-blocking)
- Avoids need for cron job in MVP
- Sets `archived_at` and `archived_by: "system:90-day-expiration"`

## DB Schema Changes

```sql
ALTER TABLE properties ADD COLUMN submitted_at timestamptz DEFAULT NULL;
ALTER TABLE properties ADD COLUMN rejected_at timestamptz DEFAULT NULL;
ALTER TABLE properties ADD COLUMN rejected_by text DEFAULT NULL;
ALTER TABLE properties ADD COLUMN rejection_reason text DEFAULT NULL;

ALTER TABLE properties DROP CONSTRAINT IF EXISTS properties_status_check;
ALTER TABLE properties ADD CONSTRAINT properties_status_check
  CHECK (status IN ('draft','pending_review','pending','approved','active','rejected','expired','archived'));
```

## Verification Results

| Check | Result |
|-------|--------|
| Admin intake API auth enforcement | ✅ curl → "Unauthorized" |
| Property submit API auth enforcement | ✅ curl → "Not authenticated" |
| Login page Google-first layout (staging) | ✅ Screenshot confirmed |
| Admin intake route protection | ✅ Redirects to login |
| 90-day expiration logic | ✅ Code verified in route handler |

## Items Verified (Already Existed)

| Item | Status | Notes |
|------|--------|-------|
| iCal Feed Connection | ✅ Exists | `OtaSettingsTab.tsx` — functional for individual properties |
| Staff Onboarding Admin UI | ✅ Exists | `admin/staff/requests/page.tsx` — approve/reject/invite |
| Staff Photo Upload | ✅ Exists | `uploadPropertyPhoto` proxy pipeline functional |

## Items Deferred

| Item | Status | Reason |
|------|--------|--------|
| Email activation proof | 🟡 Manual | Requires human inbox verification |
| Property URL extraction | 🟡 Stub | UI field exists, no scraping engine |
| Staff photo bucket migration | 🟡 Partial | Upload works, 8 old files need migration |

## Files Created
- `ihouse-ui/app/(public)/admin/intake/page.tsx`
- `ihouse-ui/app/api/admin/intake/route.ts`
- `ihouse-ui/app/api/properties/[propertyId]/submit/route.ts`

## Files Modified
- `ihouse-ui/app/(auth)/login/page.tsx`
- `ihouse-ui/app/api/properties/mine/route.ts`
