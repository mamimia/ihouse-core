# Phase 860 — Landing Page UI Fixes & Tab Responsive Scrolling

**Status:** Closed
**Prerequisite:** Phase 859 (Admin Intake Queue + Property Submit API + Login UX + Draft Expiration)
**Date Closed:** 2026-03-21

## Goal

Resolve severe layout and styling bugs in the frontend application on narrow screens and in light mode. This includes preventing text overlap in the property menu tabs by enforcing valid horizontal scrolling, rectifying main layout breakouts caused by flex containers without wrap properties, fixing the global styling of date inputs so native calendar icons respond to dark/light themes correctly, and correcting landing page CSS specificity issues that rendered CTAs unreadable in light mode.

## Invariant (if applicable)

N/A

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/admin/properties/[propertyId]/page.tsx` | MODIFIED — added `flexWrap: 'wrap'` to the header and `flexShrink: 0` to tabs to fix layout overflow and enable native horizontal scrolling for tabs |
| `ihouse-ui/app/globals.css` | MODIFIED — stripped invalid SVG replacement for `::-webkit-calendar-picker-indicator` and replaced with native dark mode `filter: invert(1)` |
| `ihouse-ui/styles/tokens.css` | MODIFIED — injected `color-scheme: light` and `color-scheme: dark` into the theme specifiers to ensure system inputs conform to theme natively |
| `ihouse-ui/app/(app)/bookings/page.tsx` | MODIFIED — stripped hardcoded `colorScheme: 'dark'` overrides from date inputs to allow them to respect the active system theme |
| `ihouse-ui/app/(public)/page.tsx` | MODIFIED — scoped theme toggler logic specifically to `.domaniqo-landing` to prevent global DOM bleed and injected `!important` to CTA button colors to win the inheritance hierarchy against `a` tags in light mode |

## Result

**Deployed successfully to Vercel production.** Frontend UI issues on both narrow properties views and public landing pages fully remediated.
