# Phase 257 — UI Rebrand (Domaniqo Design System)

**Status:** Closed
**Prerequisite:** Phase 256 (Codebase Brand Migration)
**Date Closed:** 2026-03-11

## Goal

Apply the Domaniqo brand identity system (from `docs/core/brand-handoff.md`) to all customer-facing UI surfaces. Replaces the dark iHouse/blue theme with warm-minimal Domaniqo identity: Midnight Graphite + Cloud White + Deep Moss + Signal Copper.

## Files Changed

| File | Change |
|------|--------|
| `ihouse-ui/styles/tokens.css` | REPLACED — full Domaniqo design system: Manrope+Inter fonts, Midnight Graphite/Stone Mist/Cloud White/Deep Moss/Quiet Olive/Signal Copper/Muted Sky palette, warm semantic roles |
| `ihouse-ui/app/layout.tsx` | MODIFIED — metadata title/description updated; Google Fonts import (Manrope+Inter); sidebar logo "iHouseCore" → "Domaniqo" with Manrope brand font + "Operations Platform" tagline |
| `ihouse-ui/app/login/page.tsx` | REPLACED — full Domaniqo login: Cloud White background, Midnight Graphite text, Deep Moss CTA button, 'Domaniqo' wordmark in Manrope 800, 'Calm command for modern hospitality.' tagline, 'See every stay.' footer |

## Brand Choices Applied

- **Background:** Cloud White `#F8F6F2` (replaces `#0d1117`)
- **Primary CTA:** Deep Moss `#334036` (replaces `#3b82f6` blue)
- **Text:** Midnight Graphite `#171A1F`
- **Tagline:** "Calm command for modern hospitality."
- **Footer:** "See every stay."
- **Typography:** Manrope 800 for brand wordmark, Inter for UI body

## Result

**~5,900 tests pass, 0 failures. Exit 0.**
(UI rebrand has no server-side contract tests — no new test file needed.)
