# Screenshot Grounding — Current Product Visual Reality

**Source:** Team_Inbox screenshots (app running on domaniqo-staging.vercel.app)
**Inspected:** 2026-04-03
**Screenshot count by role:** Check-In Staff (4), Check-Out Staff (3), Cleaner (3), Maintenance (3), Check-In & Check-Out (5), Guest (2), OPS Manager (4), Owner (2), Admin (80+), Public (3), Submitter (15+)

---

## Shared Worker Shell Pattern (All Single-Role Workers)

Every single-role field worker (check-in, check-out, cleaner, maintenance) shares an identical structural shell. This is the **real product today** — not proposal.

### Screen 1: Home (`/worker`)
- **Header:** Dark background, "Home" title, language selector (EN), Sign Out link
- **Welcome block:** "Hello, {name}" with role badge chip (e.g., "Check-in Staff", "Cleaner")
- **MY STATUS strip:** 3 counters in a horizontal row:
  - Open (yellow folder icon) — number
  - Overdue (green dot icon) — number
  - Today (orange calendar icon) — number
- **WORK section:** Single CTA card with role icon, "{Go to [Work Area]}" title, "{N tasks waiting}" or "No open tasks" subtitle, chevron right
- **NEXT UP section:** Preview of upcoming task cards (when tasks exist). Each card shows:
  - Task type badge (CHECKIN / CHECKOUT / CLEANER)
  - Task name ("Check-in Prep" / "Checkout Verification" / "Cleaning")
  - Priority badge (HIGH / MEDIUM) — right aligned
  - Status ("Pending" / "Acknowledged") — right aligned
  - Property name with house icon
  - Date with calendar dot icon
  - **Navigate button** (pink/copper, navigates to property location via Waze/Maps)

### Screen 2: Work List (role-specific URL)
- **Breadcrumb:** "Home > Operations > [Role Name]"
- **Title block:** Role name, date (WEDNESDAY, MARCH 25), heading ("Arrivals" / "Check-out" / "Today's Tasks" / "Maintenance"), subtitle where applicable
- **Summary strip:** 3 counters (labels vary per role — see per-role sections)
- **Task cards:** Dark background, subtle border. Each card contains:
  - Property name (bold, left) + countdown timer (right, e.g., "15h 36m 38s")
  - KPG property code (dimmed, below name)
  - Status badge ("PENDING" / "UPCOMING") — right aligned
  - Task type + date badges (left)
  - Task reference where available (e.g., "CHECKIN_PREP — KPG-500")
  - Action buttons: [Acknowledge] (outline) + [Start {Action} →] (filled, colored)
  - Priority star icon (right edge, amber/orange)
- **Section grouping:** Cards grouped by urgency: OVERDUE → TODAY → UPCOMING

### Screen 3: My Tasks (`/tasks`)
- **Title:** "My Tasks" with date subtitle
- **Tab toggle:** [Pending] / [Done] — horizontal pill toggle
- **Task cards:** Same dark card pattern as work list but showing ALL task types for the role
- **Empty state:** Party emoji + "All clear! No pending tasks assigned to you right now."

### Bottom Navigation (Single-Role Workers)
**4 tabs** (not 3 as I previously designed):
1. Home (house icon)
2. [Role Work] (role-specific icon: clipboard/broom/wrench)
3. Tasks (checkmark icon)
4. Settings (gear icon)

**Visual:** Dark bar, icons with labels below, active tab highlighted

### Card Visual Style
- **Background:** Dark (#1C1F24 or similar), slightly lighter than page background
- **Border:** Subtle, rounded corners (~12px)
- **No left-accent border visible** in current product (I invented this in my designs — it exists only in HTML prototypes)
- **Action buttons:** "Start X →" is the primary CTA (green/teal for check-in, copper/brown for check-out, green for cleaner). "Acknowledge" is a secondary outline button.
- **Countdown:** Right-aligned, dimmed, precise format "XXh XXm XXs" with "Upcoming" label
- **Priority star:** Amber star icon at far right of action row

### Acknowledge → Start Flow (Two-Step)
- PENDING tasks: Show both [Acknowledge] + [Start X →]
- ACKNOWLEDGED tasks: Show only [Start X →] as primary
- This is a real product pattern, not proposal

---

## Per-Role Observations

### CHECK-IN STAFF
**Screenshots:** 4 (Home, Arrivals list ×2, My Tasks)
**Summary strip:** Today | Upcoming | Next (with countdown to specific time, e.g., "in 15h 36m, by 14:00")
**Work page title:** "Arrivals" — subtitle "Today + next 7 days"
**Cards show:** Check-in badge, property name, KPG code, date, CHECKIN_PREP task reference
**CTA button:** "Start Check-in →" (dark green/teal)
**Bottom nav:** Home | Check-in | Tasks | Settings (4 tabs, check-in icon is clipboard)

### CHECK-OUT STAFF
**Screenshots:** 3 (Home, Departures list, My Tasks)
**Summary strip:** Overdue | Today | Next (with countdown, e.g., "in 2d, checkout 11:00")
**Work page title:** "Check-out" — subtitle "Departures · task world"
**Cards show:** Check-out badge, property name, KPG code, date
**CTA button:** "Start Check-out →" (copper/brown)
**Bottom nav:** Home | Check-out | Tasks | Settings (4 tabs)

### CLEANER
**Screenshots:** 3 (Home, Today's Tasks, My Tasks)
**Summary strip:** Tasks | Done | Next (with countdown)
**Work page title:** "Today's Tasks" — subtitle "Cleaning tasks assigned to you"
**Cards show:** Cleaning badge (green/yellow), property name, KPG code, date, task reference (e.g., "Pre-arrival cleaning for ICAL-...")
**CTA button:** "Start Cleaning →" (green)
**Task references visible:** Include booking source (ICAL, MAN) linking task to specific booking
**Bottom nav:** Home | Cleaner (broom icon) | Tasks | Settings (4 tabs)

### MAINTENANCE
**Screenshots:** 3 (Home, Maintenance list, My Tasks)
**Summary strip:** Open Issues | Critical | Tasks
**Work page title:** "Maintenance"
**Empty state (work list):** Green checkmark icon + "No open issues"
**Empty state (tasks):** Party emoji + "All clear! No pending tasks assigned to you right now."
**CTA card on home:** "Go to Maintenance · No open tasks"
**Bottom nav:** Home | Maintenance (wrench icon) | Tasks — possibly 3 tabs (Settings not clearly visible in screenshot)
**Note:** All 3 screenshots show EMPTY states. No populated maintenance cards are visible. The real card layout for maintenance issues (with categories, SLA, etc.) is NOT visible in these screenshots.

### CHECK-IN & CHECK-OUT (Combined)
**Screenshots:** 5 (Hub, My Tasks, Home, Arrivals list, Departures list)

**Hub page (`/ops/checkin-checkout`):**
- Breadcrumb: "Home > Operations > Checkin Checkout"
- Title: "Check-in & Check-out"
- Date + heading: "Your Shifts"
- Subtitle: "Check-ins (7 days) & Check-outs (task world)"
- **Check-in block:** Icon + "Check-in" label, "Next 7 days · task world", count (10), next arrival countdown, CTA: "Start Check-Ins (10 pending) →" (green)
- **Check-out block:** Icon + "Check-out" label, "Task world", count ("8 upcoming" in large text), next checkout countdown, CTA: "Process Check-outs (8) →" (copper)
- **Profile & Settings:** Link row at bottom
- Bottom nav: Today(📅17) | Arrivals | Departures | Tasks

**Home page (separate from hub):**
- Same shared worker Home pattern
- Role badge: "Check-in & Check-out"
- WORK CTA: "Go to Check-in & Check-out · Your combined operations hub"
- MY STATUS strip (Open/Overdue/Today)
- No NEXT UP section visible in this screenshot

**My Tasks (merged):**
- Mixed list showing BOTH check-in and check-out cards interleaved
- Check-in cards have check-in badge + green accent
- Check-out cards have check-out badge + copper accent
- Both types show Acknowledge + Start buttons
- Cards sorted by countdown (most urgent first)

**Arrivals tab:** Identical to CHECK-IN STAFF arrivals list
**Departures tab:** Identical to CHECK-OUT STAFF departures list

### GUEST PORTAL
**Screenshots:** 2 (Welcome + Home Essentials + How Home Works, Need Help)
- **Dark theme** (very dark navy/midnight background)
- **Welcome card:** Green "Active" badge, "Welcome, Bon", KPG-500 code
- **HOME ESSENTIALS section:** Check-in time (15:00), Check-out time (11:00) — simple info rows with icons
- **HOW THIS HOME WORKS section:** List of amenity/instruction rows:
  - Air Conditioning: "main AC in living room"
  - Hot Water: "24 h"
  - Stove/Kitchen: "use plastic spoon"
  - Parking: "2 bikes or a car"
  - Pool: "use with safe"
  - Laundry: "call us for pickup"
  - TV/Entertainment: "use remote"
  - Extra Notes: "have fun"
- **NEED HELP section:** "Send a message to your host" with text input + "Send Message" button (blue)
- **Footer:** Domaniqo logo + "Powered by Domaniqo · info@domaniqo.com"
- **No bottom nav** — guest portal is a single scrollable page, not a multi-tab app
- **No sidebar** — standalone page accessed via token URL

---

## Corrections Needed in Existing Design Files

### Critical Corrections (Applies to ALL field-worker roles)

1. **MISSING HOME SCREEN:** Every single-role worker has a `/worker` Home page that I omitted from all designs. This is a BUILT screen, not proposal. Must be documented.

2. **BOTTOM NAV IS 4 TABS, NOT 3:** All single-role workers have Home | [Work] | Tasks | Settings. My designs showed 3 tabs. Must correct.

3. **CARD STYLE MISMATCH:** My designs described a "left-accent card" pattern (3px colored left border). The current product uses plain dark cards with subtle borders and no left accent. The left-accent pattern exists only in HTML prototypes (Team_Inbox .html files), not in the deployed product. Must clearly separate what IS built from what IS proposed.

4. **COUNTDOWN FORMAT:** Real product shows precise "XXh XXm XXs" format. My designs described generic countdowns. Must note the real format.

5. **ACKNOWLEDGE FLOW:** Two-step Acknowledge → Start is a real, built pattern. My designs mentioned it inconsistently. Must standardize.

6. **NAVIGATE BUTTON:** Exists on Home page NEXT UP cards (pink/copper button). Not documented in my designs.

7. **PREVIEW MODE BANNER:** Yellow banner at top when viewing via admin Preview As. Not relevant to worker's own view, but important for testing/demo context.

### Per-Role Specific Corrections

See individual role revision files.
