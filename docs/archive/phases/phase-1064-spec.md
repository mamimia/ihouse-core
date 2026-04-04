# Phase 1064 — Guest Portal Empty States

**Status:** Implemented  
**Date:** 2026-04-04  
**Commit:** `fbb37d3`  
**File:** `ihouse-ui/app/(public)/guest/[token]/page.tsx`

---

## Audit: Current empty/under-configured behavior (before this pass)

| Section | Empty behavior (before) | Problem severity |
|---|---|---|
| **Home Essentials** | `SectionHeader` always rendered unconditionally. If wifi/times/emergency/rules/welcome all null → floating header above a completely empty gap | **High** — looks broken |
| **How This Home Works** | `return null` before data arrives AND after load with no content — both indistinguishable | Low — section silently disappears. Acceptable but has a flicker window |
| **Need Help** | Section always renders. If `/contact` endpoint returns but neither phone nor WhatsApp configured → only the note form, no explanation | Medium — incomplete feeling without context |
| **Around You** | Returns `null` when neither location nor extras configured | ✅ Intentional hide — correct |
| **Your Stay** | Returns `null` when `!hasAnything` | ✅ Intentional hide — correct |
| **Conversation Thread** | Returns `null` when no messages | ✅ Intentional hide — correct |
| **Welcome Header** | Always renders — holds booking status + dates even when some are null | ✅ Robust — uses fallbacks |

---

## Sections fixed

### 1. Home Essentials — empty state guard

**Before:** `<SectionHeader emoji="🏡" label="Home Essentials" />` rendered unconditionally on line 861. If the property had zero content configured (wifi, times, emergency, welcome message, house rules all null), the section header floated alone above a completely blank space.

**After:** The section is wrapped in an IIFE that computes `hasEssentials`:

```typescript
const hasEssentials = !!(
    data.welcome_message ||
    data.wifi_name || data.wifi_password ||
    data.check_in_time || data.check_out_time ||
    data.emergency_contact ||
    (data.house_rules && data.house_rules.length > 0)
);
```

When `hasEssentials === false`, the section header still shows (the guest needs orientation) but instead of blank space, a calm informational card appears:

> 🏡 Home information will be available here once your host has set it up.  
> *If you need anything right away, use the message box below.*

When `hasEssentials === true`, behavior is identical to before — all conditional items render normally.

### 2. Need Help — no contact method empty state

**Before:** When `/contact` returned a valid response but neither `phone` nor `whatsapp_link` were present, the section showed only the message note form with no explanation.

**After:** A calm card is shown directly above the message form when:
- `contact !== null` (endpoint has responded — not while still loading)
- `!contact.phone && !contact.whatsapp_link`

Card copy:  
> ✉️ **Contact your host**  
> Use the message box below to reach your host directly.

This prevents the guest from seeing a section that says "Need Help?" with nothing but a blank form and no context.

### 3. HowThisHomeWorks — load tracking fix

**Before:** The component returned `null` in two different cases that were indistinguishable:
- While the fetch was still in-flight (pre-load null)
- After load completed with no configured content (empty null)

**After:** Added `loaded: boolean` state, set via `.finally()` on the fetch chain. The guard is now:

```typescript
if (!loaded || available.length === 0) return null;
```

This eliminates a potential flicker where the section might briefly appear then vanish, and also makes the logic semantically cleaner. The non-null assertion `info![key]` is now safe because `!loaded` is checked first.

---

## Sections that intentionally return null (correct as-is)

These sections disappear entirely when empty. This is the right call because they are optional content — not baseline guest expectations:

| Section | Rationale for hiding |
|---|---|
| **Around You** | Both location map links and extras are optional add-ons. If neither is configured, there's nothing to show and no appropriate placeholder. |
| **Your Stay** | Guest count / deposit status / checkout notes — gaps here are visible in booking data elsewhere. Showing an empty card adds confusion. |
| **Conversation Thread** | No messages = nothing to display. The input form is always available below. |
| **How This Home Works** | Instructions are configured per-property. If none set, section hides. A placeholder here would be misleading (user expects actual appliance info). |

---

## What remains open

### 1. Check-in/out time fallback
When `check_in_time` and `check_out_time` are both null but `hasEssentials` is true for other reasons (e.g., wifi is set), the times simply don't appear. There is no fallback like "Contact your host for check-in instructions." This is acceptable for now but could be improved with a specific conditional card for missing times.

### 2. House rules — empty message in guidebook style
Some properties have no formal house rules but expect guests to behave appropriately. A future option would be a soft default rule set ("Be respectful of neighbours", "No smoking indoors") as a fallback when `house_rules` is null. Product decision — not implemented here.

### 3. HowThisHomeWorks — partial configuration
If a property has only 1 of 8 fields configured (e.g., only `pool_instructions`), the section shows just that one row. This is correct behavior — no change needed.

### 4. Around You — no empty state for "no location but has extras"
If extras exist but location (maps links) is null, the extras show and the maps card simply doesn't appear. This is fine.

---

## Files changed

- `ihouse-ui/app/(public)/guest/[token]/page.tsx`
- `docs/phases/phase-1064-guest-portal-empty-states.md` (this file)

## Checks

- `npx tsc --noEmit` → **0 errors** ✅
- `vercel --prod` → **exit 0** ✅
