# Domaniqo Design System — V1 Foundation

**Phase:** 974
**Status:** Active foundation — evolves as role designs are added
**Principle:** One product system, mobile-first, coherent across all roles

> **2026-04-03 Correction:** After screenshot inspection, the following elements were clarified:
> - **Card style (BUILT):** Dark background cards with subtle borders and rounded corners. No left-accent border in the deployed product. The left-accent pattern exists only in HTML prototypes.
> - **Bottom nav (BUILT):** Single-role workers have 4 tabs (Home | Work | Tasks | Settings), not 3.
> - **Worker Home (BUILT):** Every single-role worker has a shared `/worker` home page with Welcome + MY STATUS + WORK CTA + NEXT UP.
> - **Countdown format (BUILT):** Precise "XXh XXm XXs" format, ticking every second.
> - **Acknowledge flow (BUILT):** Two-step: Acknowledge (outline) → Start (filled colored CTA).
> - **Navigate button (BUILT):** Appears on Home NEXT UP cards, pink/copper, opens maps.
> - **Left-accent card pattern** remains a V1 PROPOSAL for the new design direction, but must be clearly tagged as such — not presented as current reality.

---

## 1. Core Philosophy

Domaniqo is roughly 80% mobile-first. Workers operate on phones in the field. Admin and Ops Manager regularly use desktop, but the phone experience must be complete for everyone.

Design logic:
- Mobile-first in structure, spacing, navigation, and screen layout
- Desktop is a responsive expansion of the same system, not a separate product
- All roles share one visual language with role-appropriate personality
- Urgency, state, and progress are expressed through a shared vocabulary

---

## 2. Typography

| Use | Font | Size | Weight | Notes |
|-----|------|------|--------|-------|
| Page title | Manrope | 14–20px | 800 | letter-spacing: -0.01em |
| Card title / Property name | Manrope | 11.5–13px | 800 | |
| Section header | Manrope | 8–9px | 800 | uppercase, letter-spacing: 0.08–0.1em |
| Badge / pill | Manrope | 7.5–8px | 700–800 | uppercase, letter-spacing: 0.06–0.09em |
| Body text | Inter | 9.5–11px | 400–500 | |
| Metadata / timestamp | Inter | 8.5–9px | 500 | color: mid-gray |
| Button label | Manrope | 9–10px | 700 | |
| Nav label (bottom) | Manrope | 8–9px | 600 | |
| KPI number | Manrope | 16px | 800 | |

---

## 3. Color Palette

### Brand Colors
| Token | Hex | Use |
|-------|-----|-----|
| deep-moss | #334036 | Primary action, completion, check-in/arrivals |
| signal-copper | #B56E45 | Active urgency, departures, maintenance accent |
| midnight | #171A1F | Text, dark backgrounds, app header |
| stone-mist | #EAE5DE / #EDEAE6 | Page background (light) |
| white | #FFFFFF | Cards, content areas |

### Semantic Colors
| Token | Hex | Use |
|-------|-----|-----|
| red | #DC2626 | Overdue, critical, error |
| red-light | #FEE2E2 | Red badge background |
| red-bg | #FFF4F4 | Red card background tint |
| amber | #F59E0B | Warning, approaching, at-capacity |
| amber-dark | #92400E | Amber text on light backgrounds |
| amber-bg | #FFFCF0 | Amber card background tint |
| green | #4ADE80 / #22C55E | Success, done, on-time |
| green-dark | #15803D / #166534 | Green text on light backgrounds |
| green-bg | #DCFCE7 | Green badge background |
| blue | #3B82F6 / #1D4ED8 | Info, upcoming, link actions |
| blue-bg | #EFF6FF | Blue badge background |
| mid-gray | #6B7280 | Secondary text |
| light-gray | #9CA3AF | Tertiary text, inactive nav |
| border | #E5E7EB | Card borders, dividers |
| surface | #FAFAFA | Subtle section backgrounds |

---

## 4. Urgency System (Shared Across All Roles)

The urgency system uses **left-accent borders + subtle background tints**. No heavy overlays.

| Level | Left Border | Card Background | Text Color | Animation |
|-------|-------------|-----------------|------------|-----------|
| Safe / Normal | #D1D5DB | #FFFFFF | default | none |
| Approaching | #F59E0B | #FFFCF0 | #92400E | none |
| Imminent | #B56E45 | #FBF1EC | #B56E45 | pulse (0.95s) |
| Overdue / Critical | #DC2626 | #FFF4F4 | #DC2626 | blink (1.1s) |
| Done / Complete | #334036 | #F9FBF9 | #334036 | none |

Animations are reserved for imminent and overdue only. No gratuitous motion.

---

## 5. Component Patterns

### Task / Job Card
```
┌─────────────────────────────────┐
│ ▌ [Left accent 3px]              │
│   Property Name        [Badge]   │
│   Meta: worker · time · status   │
│   [Full-width CTA button]        │
└─────────────────────────────────┘
```
- Border: 1.5px solid #E5E7EB (left: 3px, colored by urgency)
- Border-radius: 10px
- Padding: 8–10px (left: 12–13px for accent spacing)
- Background: white (or tinted by urgency)

### Badge / Pill
- Border-radius: 3–6px
- Padding: 2px 6–8px
- Font: 7.5–8px Manrope 700–800, uppercase
- Colors follow semantic palette

### KPI Strip
- Dark background (#0F1115)
- Flex row, equal columns
- Number: 16px Manrope 800 (colored by state)
- Label: 7.5px Manrope 700, uppercase, muted

### Detail Block
- White background, 9px border-radius
- Header: #FAFAFA background, section title (7.5px uppercase)
- Rows: key-value pairs, separated by subtle borders

### CTA Buttons
- Primary: deep-moss (#334036) or signal-copper (#B56E45), white text
- Danger: red (#DC2626), white text
- Warning: amber (#F59E0B), white text
- Ghost: transparent, 1.5px colored border
- Height: 26–35px, border-radius: 6–8px
- Full-width within cards

---

## 6. Navigation Model

### Mobile (All Roles)
- **Bottom navigation bar**: 56px height, dark background (#171A1F)
- **4 primary tabs** + optional "More" overflow
- Active tab: white icon + label. Inactive: rgba(255,255,255,.28)
- Alert badge: 7px red dot with border
- Icons: 17px, stroke-based, 1.7px weight

### Desktop (Admin / Ops Manager Only)
- **Left sidebar**: 220px (full) or 64px (collapsed rail)
- Same items as bottom nav, expanded with labels and section headers
- Mode indicators (Preview / Act-As) in footer

### Mobile Staff Shell (Workers)
- Full-screen, forced dark theme
- No sidebar — bottom nav only
- Safe area handling for notched devices

### Shell Assignment
| Role | Mobile Shell | Desktop Shell |
|------|-------------|---------------|
| admin | Standard Sidebar → BottomNav | Standard Sidebar (220px) |
| manager | OMBottomNav | OMSidebar (220px / 64px rail) |
| ops | MobileStaffShell | — (mobile-only) |
| worker / cleaner / checkin / checkout / maintenance | MobileStaffShell | — (mobile-only) |
| owner | Standard (light) | Standard Sidebar (light) |
| guest | Public shell (no auth nav) | Public shell |

---

## 7. App Header

### Dark Header (Workers / Manager Mobile)
- Height: 50px, background: #171A1F
- Title: 12.5px Manrope 800, white
- Subtitle: 9px, rgba(255,255,255,.38)
- Avatar: 28px circle, white initials

### Light Header (Admin / Owner)
- Height: 50px, background: #FFFFFF
- Title: 13px Manrope 800, #334036 (deep-moss brand)
- Border-bottom: 1px solid #E5E7EB

### Back Header (Detail Screens)
- Height: 42px, dark background (matches context)
- Back arrow + label (8px uppercase)
- Screen title right-aligned

---

## 8. Responsive Strategy

| Breakpoint | Behavior |
|------------|----------|
| < 768px | Mobile layout: bottom nav, stacked cards, full-width components |
| 768–1023px | Tablet: collapsed sidebar rail (64px), wider cards |
| ≥ 1024px | Desktop: full sidebar (220px), multi-column layouts where appropriate |

Within any breakpoint, the structural logic (card shapes, urgency expression, navigation hierarchy) stays the same. Desktop adds space and sometimes parallel columns — it does not add new conceptual surfaces.

---

## 9. State Patterns

### Loading
- Center spinner (role-appropriate color)
- No skeleton screens in V1 (simplicity)

### Empty
- Centered icon + heading + subtitle
- Muted colors, no dramatic visuals
- Example: "No active alerts" with green checkmark (positive empty state)

### Error
- Red banner at top of content area
- Brief message + retry if applicable

### Warning
- Amber inline banner
- Contextual, not blocking

---

## 10. Role Personality Within System Consistency

Each role has a personality, but all stay within the same design system:

| Role | Personality | Key Visual Cues |
|------|-------------|-----------------|
| Ops Manager | Command center, oversight | Dark cockpit, KPI strips, team cards, alert severity |
| Check-In Staff | Time-driven, guest-facing | Deep-moss accent, countdown pills, step wizard |
| Check-Out Staff | Time-driven, departure-focused | Signal-copper accent, overdue alerts, settlement steps |
| Cleaner | Space-driven, evidence-focused | Room dots, photo badges, "Property Ready" completion |
| Maintenance | Priority-driven, access-focused | Priority badges, access codes, before/after photos |
| Admin | Full control, configuration | Neutral palette, tables, forms, wide layouts |
| Owner | Financial clarity, trust | Light palette, statement cards, confidence tiers |
| Guest | Hospitality, simplicity | Warm tones, minimal chrome, section-based portal |
