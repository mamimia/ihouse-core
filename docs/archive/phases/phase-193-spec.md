# Phase 193 — Guest Profile UI

**Opened:** 2026-03-10
**Closed:** 2026-03-10
**Status:** ✅ Closed

## Goal

UI surface for Phase 192's `guests` API. Two Next.js pages, zero backend changes.

## New / modified files

| File | Change |
|------|--------|
| `ihouse-ui/lib/api.ts` | + `Guest`, `GuestListResponse` types + 4 API methods |
| `ihouse-ui/app/layout.tsx` | + Guests nav link (👤) |
| `ihouse-ui/app/guests/page.tsx` | NEW — `/guests` list page |
| `ihouse-ui/app/guests/[id]/page.tsx` | NEW — `/guests/[id]` detail page |

## Features

**`/guests` (static route):**
- Debounced live search bar (`?search=`)
- Guest table: full_name, email, phone, nationality, created_at, View → link
- "New Guest" slide-in create panel — full_name required, optional: email, phone, nationality
- PII notice banner
- Loading skeleton rows / empty state

**`/guests/[id]` (dynamic route):**
- Displays UUID, created_at, updated_at
- ✎ Edit → inline editable FieldRow grid → Save Changes (PATCH) / Cancel
- `full_name` required validation
- PII notice banner; 404 shown gracefully

## Build

```
npm run build
  ○ /guests       (static)
  ƒ /guests/[id]  (dynamic)
→ Exit code: 0. 0 regressions.
```
