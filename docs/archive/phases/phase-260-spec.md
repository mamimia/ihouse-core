# Phase 260 — Language Switcher + Thai/Hebrew RTL UI

**Status:** Closed
**Prerequisite:** Phase 259 (Bulk Operations)
**Date Closed:** 2026-03-11

## Goal

Full app-wide language switching: English (default), Thai (worker priority), Hebrew (RTL demo). Language persists in `localStorage`. Direction (`dir`) auto-applied to `<html>`.

## Files Changed

| File | Change |
|------|--------|
| `ihouse-ui/lib/LanguageContext.tsx` | NEW — `LanguageProvider`, `useLanguage()`, `t()` function, localStorage persistence, RTL auto-application for Hebrew |
| `ihouse-ui/lib/translations.ts` | NEW — 80 translation keys × 3 languages (en/th/he). Worker screen strings are Thai-complete and production-quality |
| `ihouse-ui/components/LanguageSwitcher.tsx` | NEW — Compact 3-button selector (🇬🇧/🇹🇭/🇮🇱) with Domaniqo palette. Renders in sidebar. |
| `ihouse-ui/components/Sidebar.tsx` | NEW — Client component extracted from layout.tsx to use `useLanguage()` for translated nav links |
| `ihouse-ui/app/layout.tsx` | MODIFIED — Wraps app in `<LanguageProvider>`, uses `<Sidebar>` client component |
| `ihouse-ui/app/worker/page.tsx` | MODIFIED — Imports `useLanguage()`, tab labels, header, channel tab labels, status labels all translated |

## Architecture

```
layout.tsx (Server Component)
  └── <LanguageProvider> (Client boundary)
        ├── <Sidebar> (Client — t() for nav links)
        │     └── <LanguageSwitcher> (Client — setLang)
        └── <main>
              └── worker/page.tsx (uses useLanguage() for worker screen)
```

## RTL Behaviour

When Hebrew is selected:
- `document.documentElement.dir = 'rtl'`
- `document.documentElement.lang = 'he'`
- All flex/text layout responds to CSS logical properties

## Verification

`npx tsc --noEmit` → **0 errors, 0 warnings**
