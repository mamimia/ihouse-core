# Theme System

## Core Principle
Dark mode is the default.
Light mode is optional user preference.
Theme does not change system logic.

---

## Default Behavior

1. All new users start in Dark mode.
2. Theme preference is stored per user.
3. Admin cannot force theme globally.
4. Switching theme must not affect layout or spacing.

---

## Dark Mode Style Rules

Background:
Near black #0F1115

Card surface:
#151821

Primary text:
#FFFFFF

Secondary text:
#A0A6B2

Accent color:
Controlled blue or warm amber
Never neon.

Critical state:
Red border + subtle glow
Never blinking.

---

## Light Mode Style Rules

Background:
#F4F6F9

Card surface:
#FFFFFF

Primary text:
#111111

Secondary text:
#6B7280

Accent:
Same hue family as dark.

---

## UX Invariants

1. No gradients.
2. No glass blur.
3. No excessive shadows.
4. Cards must feel solid and structured.
5. Typography weight hierarchy:
   H1 bold
   H2 medium
   Body regular
   Meta light

---

## Interaction Rules

1. Critical states override theme colors.
2. AtRisk shows amber border.
3. Blocked shows red border.
4. Ready shows subtle green indicator.
5. Theme toggle in user profile only.