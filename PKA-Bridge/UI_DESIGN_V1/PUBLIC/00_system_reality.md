# Public UI — System Reality (Read Before Design)

**Read from:** ihouse-core real codebase + Team_Inbox screenshots (3 screenshots)
**Date:** 2026-04-03

> **Grounding key:** [BUILT] = confirmed in screenshots. [INFERRED] = from codebase. [V1 PROPOSAL] = new design.

---

## What Already Exists [BUILT]

### Architecture
- **Route:** `/` and other public routes under `(public)` layout group
- **Auth:** None required for main pages. Auth callback at `/auth/callback`.
- **Shell:** Minimal top bar — Domaniqo logo + nav links + Sign in + "Get Started" CTA
- **Theme:** Dark (same dark palette as internal app)

### Landing Page [BUILT — Screenshot 23.11.20]
**URL:** `/`

**Layout confirmed:**
- Top nav: Domaniqo logo | Platform | Channels | Pricing | About | Sign in | [Get Started] (green CTA)
- Hero section (centered): Domaniqo logo icon, "See every stay." (large serif headline), "The deep operations platform for modern hospitality. Calm command across operations, teams, finance, and guest experience." (subtitle)
- Two CTAs: [Onboard Your Property] (green filled) + [Sign in →] (outline)
- Dark background throughout (Phase 860 redesign)

### Public Pages Inventory [BUILT/INFERRED]

| Page | URL | Purpose |
|------|-----|---------|
| Landing | `/` | Marketing hero + CTAs [BUILT] |
| Platform | `/platform` | Platform overview [INFERRED] |
| Channels | `/channels` | Channel/OTA information [INFERRED] |
| Pricing | `/pricing` | Pricing page [INFERRED] |
| About | `/about` | About page [INFERRED] |
| Reviews | `/reviews` | Testimonials [INFERRED] |
| Privacy | `/privacy` | Legal/privacy policy [INFERRED] |
| Terms | `/terms` | Terms of service [INFERRED] |
| Get Started | `/get-started` | Property onboarding wizard [BUILT — see SUBMITTER] |
| Early Access | `/early-access` | Redirects to `/get-started` [INFERRED] |
| Staff Apply | `/staff/apply` | Public staff application form (773 lines) [INFERRED] |

### Welcome Page (Authenticated User) [BUILT — Screenshots 23.09.00, 23.15.53]
**URL:** `/welcome`

For authenticated users without a specific role assignment (identity-only, Phase 862):

**Layout:**
- Domaniqo logo, "Welcome, {name}", email
- 3 card tiles:
  - Profile & Settings — "Name, email, connected accounts, language"
  - My Pocket — "Saved stays, places, services, and details" + "Coming soon" badge
  - My Properties — "View submitted properties or draft submissions"
- Large CTA banner: "Get Started — Onboard a Property" with rocket icon, "Set up your first property on Domaniqo"
- Footer: "Domaniqo — Hospitality Operations"

### Profile [BUILT — Screenshot 23.09.09]
**URL:** `/profile`

- Fields: Email, Full Name, Phone, Language
- [Edit Profile] button (copper/amber)
- Linked Login Methods section: current method shown, "Link Google Account" button
- Account Status: "Identity only — no organization assigned"
- Internal ID shown at bottom (debug/reference)

### My Properties [BUILT — Screenshot 23.10.04]
**URL:** `/my-properties`

- Title: "My Properties", "Welcome back, {name}"
- DRAFTS section: property cards with photo, name, location, DRAFT badge, [Edit] + [Submit →] buttons
- SUBMITTED section: property cards with PENDING REVIEW badge (amber)
- [+ Add Another Property] button
- Draft auto-expiry: 90 days

---

## What Is Missing

1. **Marketing content on sub-pages** — Platform, Channels, Pricing, About pages exist as routes but content depth is unknown from screenshots
2. **No public property showcase** — No guest-facing property browsing
3. **My Pocket is "Coming soon"** — Placeholder card exists but no functionality
4. **No mobile-optimized public pages** — Landing page appears desktop-focused

---

## What Is Already Strong

1. **Clean landing** — Single message, two clear CTAs, professional tone
2. **Identity-first onboarding** — Users land at `/welcome` with clear next actions
3. **Property draft system** — Submit → review → approve lifecycle with visual status badges
4. **Staff application form** — Public hiring pipeline (773-line comprehensive form)
