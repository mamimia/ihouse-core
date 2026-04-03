# OPS Manager — States & Edge Cases (V1)

---

## Global States

### Loading State
- Center spinner (white on dark background for OM screens)
- Replaces scroll content area, not the full screen
- Header and nav remain visible during load
- No skeleton screens in V1

### Error State
- Red banner at top of content area
- "Something went wrong — tap to retry"
- Does not block navigation to other tabs

### Offline / Connection Lost
- Amber banner at top: "Connection lost — data may be outdated"
- Last-fetched timestamp shown
- Auto-retry on reconnect
- No offline-first storage (V1 limitation — documented, not hidden)

---

## Per-Screen States

### Hub (S01)
| State | Trigger | Appearance |
|-------|---------|------------|
| Morning calm | All tasks done or on-track | Briefing card 100% green, no attention section |
| Attention needed | 1+ overdue or SLA risk | Attention section visible, red/amber cards |
| Heavy day | 20+ tasks | KPI strip shows high numbers, all 4 streams populated |
| No tasks | Weekend or off-day | "No operations scheduled today" centered message |
| Takeover active | Manager executing a task | Execution drawer visible (desktop: right panel; mobile: full-screen) |

### Alerts (S17)
| State | Trigger | Appearance |
|-------|---------|------------|
| No alerts | Nothing critical | Green checkmark + "No active alerts" — this is a GOOD state |
| Some alerts | 1+ escalation | Color-coded list, stat cards show counts |
| Many alerts | 5+ critical | Stat cards turn red, list scrolls |

### Stream (S08)
| State | Trigger | Appearance |
|-------|---------|------------|
| Empty lane | No tasks in selected stream | "No [stream] tasks today" centered |
| Active | Tasks present | Canonical-ordered list |
| All done | All tasks in stream complete | Green status strip, "All [stream] complete" banner |
| Mixed urgency | Some overdue, some on-time | Red items sort to top within canonical order |

### Team (S18)
| State | Trigger | Appearance |
|-------|---------|------------|
| Full coverage | All lanes covered | Green "Full Coverage" stat |
| Gaps detected | Missing primary in any lane | Red gap pills on property cards |
| No properties | Manager not assigned to properties | "No properties assigned yet" + legend |
| Worker overloaded | Load exceeds threshold | Worker card with red ring + OVERLOADED tag |

### Bookings (S22)
| State | Trigger | Appearance |
|-------|---------|------------|
| No results | Search returns nothing | "No bookings found" |
| Active stays | Normal state | Collapsible booking cards |
| Early C/O pending | Guest requested early checkout | Amber badge on booking card |

### Calendar (S26)
| State | Trigger | Appearance |
|-------|---------|------------|
| Empty day | No bookings/tasks on selected date | "No bookings or tasks this day" |
| Busy day | Many tasks | Task dots overflow with "+N" |
| Today | Current date | Highlighted cell |

### Profile (S27)
| State | Trigger | Appearance |
|-------|---------|------------|
| Loaded | Normal | All sections populated |
| No capabilities | Nothing delegated | Message: "No additional capabilities delegated by admin" |
| No properties | Not assigned | Message: "No properties currently assigned" |

---

## Edge Cases

### 1. Manager Takeover Mid-Wizard
**Scenario:** Manager takes over a check-in task, starts the 7-step wizard, then receives a critical alert.
**Behavior:** Alert notification appears as a banner over the execution drawer. Manager can dismiss to continue wizard or tap to navigate to alert (wizard state is preserved in background on desktop, lost on mobile).
**V1 Decision:** On mobile, wizard state is NOT preserved if navigating away. Document this limitation.

### 2. Worker Reassignment While Task In-Progress
**Scenario:** Manager reassigns a task that the current worker has already started.
**Behavior:** Confirmation modal: "Worker has already started this task. Reassigning will reset progress. Continue?"
**V1 Decision:** Warn but allow. The reassigned worker starts from scratch.

### 3. Multiple Alerts for Same Property
**Scenario:** Both checkout overdue AND maintenance SLA risk for the same property.
**Behavior:** Two separate alert cards on hub. Alert detail for each shows cross-references: "Related alert: [other alert type] for this property."
**V1 Decision:** No merged alert view in V1. Each alert is independent.

### 4. Stream Task Canonical Ordering with Gaps
**Scenario:** A property has checkout + checkin tasks but no cleaning task (cleaning template not set up).
**Behavior:** Turnover chain shows: Checkout → [No cleaning task] → Check-in. Gap is visually indicated with dashed line and "No cleaning scheduled" label.
**V1 Decision:** Show the gap, don't auto-create missing tasks.

### 5. Preview Mode Limitations
**Scenario:** Admin previewing as manager tries to take over a task.
**Behavior:** Preview mode is read-only. Takeover button shows "Preview — Actions Disabled" tooltip. Button is visually dimmed.
**V1 Decision:** All mutation buttons dimmed in preview mode with consistent tooltip.

### 6. 30-Second Alert Refresh During Active Intervention
**Scenario:** Manager is in the middle of reassigning a worker when the 30s alert refresh fires.
**Behavior:** Refresh updates the background list but does NOT interrupt the active drawer/modal.
**V1 Decision:** Background refresh only; no interruption of active user flows.

---

## Animation Inventory

| Animation | Trigger | Duration | Used On |
|-----------|---------|----------|---------|
| Pulse | Card urgency = imminent | 0.95s ease-in-out infinite | Alert cards, stream rows |
| Blink | Card urgency = overdue, live dot | 0.8–1.1s ease-in-out infinite | Time displays, LIVE badge dots |
| Slide-in | Drawer opens | 200ms ease-out | Execution drawer, reassign picker |
| Fade | Modal appears | 150ms | Escalation form, note modal |
| None | Everything else | — | No gratuitous animations |
