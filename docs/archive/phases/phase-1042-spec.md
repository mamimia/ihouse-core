# Phase 1042 — Morning Briefing Data Audit

**Status:** CLOSED
**Prerequisite:** Phase 1041
**Date closed:** 2026-04-02
**Branch:** `checkpoint/supabase-single-write-20260305-1747`

---

## Scope

End-to-end data audit of the Morning Briefing before accepting it as valid Operational Manager product truth.

Three issues triggered the audit:
- A. "30 open tasks" may be misleading
- B. "DLQ alert: 7 unprocessed OTA events" is not credible in this iCal-first tenant context
- C. No clear operator action path

---

## 1. Morning Briefing Data-Source Audit

All data is assembled by `src/api/manager_copilot_router.py` which calls helpers in `src/api/ai_context_router.py`.

### 1.1 Check-ins count
| Item | Truth |
|------|-------|
| **Source** | `booking_state` table |
| **Filter** | `status = 'active'` AND `check_in = today` |
| **Scope** | `tenant_id = <jwt tenant>` |
| **Property-scoped?** | No — across ALL properties for this tenant |
| **Date-bounded?** | Yes — strictly today only |
| **Verdict** | ✅ **TRUSTWORTHY.** Correct and tight. |

### 1.2 Check-outs count
| Item | Truth |
|------|-------|
| **Source** | `booking_state` |
| **Filter** | `status = 'active'` AND `check_out = today` |
| **Scope** | tenant-scoped |
| **Date-bounded?** | Yes — today only |
| **Verdict** | ✅ **TRUSTWORTHY.** |

### 1.3 Cleanings count
| Item | Truth |
|------|-------|
| **Source** | Derived from departures: `cleanings_due = len(departures)` |
| **Logic** | 1 departure = 1 assumed cleaning needed |
| **Verdict** | ✅ **ACCEPTABLE** — heuristic but sound. Should be noted it is an assumption, not a task query. |

### 1.4 Active bookings count
| Item | Truth |
|------|-------|
| **Source** | `booking_state` |
| **Filter** | `status = 'active'` — NO date filter |
| **Scope** | tenant-scoped |
| **Date-bounded?** | **No** — includes all currently active bookings regardless of date |
| **Verdict** | ✅ **TRUSTWORTHY** for "active stays right now" but wording "13 active booking(s)" is meaningful and correct. |

### 1.5 Open tasks count — THE KEY PROBLEM

| Item | Truth |
|------|-------|
| **Source** | `tasks` table |
| **Filter** | `status IN ('PENDING', 'ACKNOWLEDGED', 'IN_PROGRESS')` |
| **Scope** | `tenant_id = <jwt tenant>` |
| **Property-scoped?** | No — ALL properties |
| **Date-bounded?** | **NO DATE FILTER WHATSOEVER** |
| **DB verification** | 30 tasks, due_today=0, overdue=0, **future=30, critical=0** |

**This is the confirmed problem.** All 30 tasks are future scheduled work — check-in preps, checkout verifications, cleanings — the nearest due today = 0, the earliest due is April 5, the farthest due is March 2027.

The briefing line `"30 open task(s) — 13 high/critical priority"` is **materially misleading**. It sounds like 30 active operational problems requiring immediate attention. In truth: 0 problems exist today. All 30 are properly scheduled, future-dated task queue entries.

*The 13 "high/critical" are the CHECKIN_PREP tasks (priority=HIGH), all dated weeks to months away. These are not crises. They are the normal advance scheduling of check-in prep work.*

### 1.6 High/critical count
| Item | Truth |
|------|-------|
| **Source** | `by_priority` dict from tasks query — counts HIGH + CRITICAL |
| **Date-bounded?** | No — same no-date-filter problem |
| **DB verification** | HIGH=13, CRITICAL=0 — all are scheduled CHECKIN_PREP tasks for future dates |
| **Verdict** | ❌ **MISLEADING.** "13 high/critical" implies urgent operational pressure. Reality: all future, none critical, none past SLA. |

### 1.7 DLQ alert count — THE SECOND PROBLEM

| Item | Truth |
|------|-------|
| **Source** | `ota_dead_letter` table |
| **Filter** | `replay_result IS NULL` (no replay attempted) |
| **Scope** | **GLOBAL — no tenant_id column exists in this table** |
| **DB verification** | 9 total rows, 7 unprocessed (replay_result=null) |
| **Breakdown of 7 unprocessed** | 2 = dev/test entries (provider='test', 'test-phase39') from March 8; 1 = ordering buffer test (March 8); 2 = real Booking.com API errors (March 15, BOOKING_NOT_FOUND + OVERLAP_NOT_ALLOWED); 1 = Airbnb TENANT_ID_REQUIRED (March 14); 1 = old Booking.com canceled ordering buffer test |
| **iCal-originated?** | **No.** The table is OTA API push ingestion only. iCal failures do not land here. |
| **Tenant-scoped?** | **No.** Global table. Data belongs to this tenant's test runs but infrastructure-level — not separate by tenant. |
| **Are they current incidents?** | **No.** Oldest: March 8. Newest: March 15. All 18+ days old. None from live iCal operations. |
| **Are they actionable by OM?** | **No.** These were integration testing artifacts. The Booking.com and Airbnb entries come from push API testing (the tenant does not have live Booking.com / Airbnb API integrations). |
| **Verdict** | ❌ **NOT CREDIBLE ON OM HUB.** Global metric, contaminated with test entries, 18+ days stale, not iCal-sourcing tenant's live operations, no operator action path. |

### 1.8 Top action generation
| Item | Truth |
|------|-------|
| **Logic** | Priority: critical_sla → dlq_alert → sync_degraded → high_arrival → default |
| **Current output** | "Review and replay Dead Letter Queue entries" — triggered by dlq_alert = True (count ≥ 5) |
| **Verdict** | ❌ **WRONG.** The top action is generated by incorrect signal priority. DLQ alert fires even over real operational priorities because the heuristic threshold is global and stale. |

---

## 2. Open Task Meaning Audit

**Confirmed DB truth for this tenant (2026-04-02):**

| Category | Count | Due dates |
|----------|-------|-----------|
| Due today | **0** | — |
| Overdue (past due_date) | **0** | — |
| Future scheduled | **30** | Apr 5 → Mar 2027 |
| High priority | 13 | All future CHECKIN_PREP |
| Critical priority | **0** | — |
| Critical past 5-min ACK SLA | **0** | — |

**Current briefing wording: `"30 open task(s) — 13 high/critical priority"`**
**Reality: 0 tasks require any action today.**

### Product-correct wording

The briefing should distinguish between:
1. **Needs attention now** = overdue + today's due + critical unacked
2. **Scheduled queue** = future-dated tasks (system is working normally)

**Proposed corrected line:**
- If 0 tasks need attention today: `"No tasks require attention today. 30 tasks scheduled across upcoming weeks."`
- If N tasks need attention: `"N task(s) need attention today (due or overdue). X more scheduled ahead."`

---

## 3. DLQ Audit

### Full chain

| Question | Answer |
|----------|--------|
| **Which table?** | `ota_dead_letter` |
| **What populates it?** | OTA API push ingestion failures — events that reach the backend OTA webhook endpoint but fail the `apply_envelope` gate |
| **Can iCal failures appear here?** | **No.** iCal is polled/pulled, not pushed. iCal failures fail in a different path and are not recorded in `ota_dead_letter`. |
| **Can only OTA/API events appear?** | **Yes** — by design. The write path (`src/adapters/ota/dead_letter.py`) is only called by the OTA adapter layer. |
| **Are these 7 tenant-scoped?** | **No.** The table has no `tenant_id` column. It is global infrastructure. |
| **Do these 7 belong to this property?** | Unknown — no property filter is possible. Some envelope payloads contain property_id inside JSON but the outer table has no property column. |
| **Are these 7 current/relevant?** | **No.** Oldest: Mar 8 (a month ago). Newest: Mar 15 (18 days ago, same day as integration testing). 2 of 7 are explicit test entries (`provider='test'`). |
| **Are they actionable by OM?** | **No.** Even if a replay were needed, the admin endpoint `POST /admin/dlq/{envelope_id}/replay` is correctly placed under `/admin/*` — it should not be surfaced on the OM Hub. |

### The specific 7 entries

| id | Provider | Event | Rejection | Age | Nature |
|----|----------|-------|-----------|-----|--------|
| 9 | bookingcom | BOOKING_AMENDED | BOOKING_NOT_FOUND | 18 days | Integration test artifact |
| 8 | bookingcom | BOOKING_CREATED | OVERLAP_NOT_ALLOWED | 18 days | Integration test artifact |
| 7 | airbnb | BOOKING_CREATED | TENANT_ID_REQUIRED | 19 days | Integration test artifact |
| 5 | bookingcom | BOOKING_CANCELED | BOOKING_NOT_FOUND | 25 days | Ordering buffer test |
| 3 | test-phase39 | BOOKING_CANCELED | TEST | 25 days | **Explicit dev test** |
| 2 | bookingcom | BOOKING_CANCELED | BOOKING_NOT_FOUND | 25 days | Integration test artifact |
| 1 | test | BOOKING_CANCELED | BOOKING_NOT_FOUND | 25 days | **Explicit dev test** |

**Conclusion: 2/7 are explicit dev test entries. 5/7 are integration testing artifacts from OTA API testing (not live operations). 0/7 represent a current live operational incident.**

---

## 4. Real Operator Action Path

### Current state
There is **no user-facing action path** for a DLQ entry from the OM Hub. The briefing says "Review and replay Dead Letter Queue entries" but:
- There is no link in the briefing UI
- The DLQ Inspector exists at `GET /admin/dlq` (admin-only endpoint) with no corresponding admin UI page exposed on the Hub
- The replay mechanism (`POST /admin/dlq/{envelope_id}/replay`) is an admin API endpoint

### Recommendation

**Remove DLQ signal from OM Hub entirely.**

Rationale:
1. The DLQ is global — not tenant or property scoped
2. The DLQ contains test/integration artifacts not relevant to live operations
3. The DLQ is an infrastructure/admin signal — not an Operational Manager operational signal
4. "Replay" is a technical operation not belonging in the OM surface
5. No current live incidents exist in this tenant's DLQ

If the DLQ signal is ever reinstated for OM: it must require (a) a tenant-scoped `tenant_id` column in `ota_dead_letter`, (b) a property-scoped filter, (c) a recency filter (e.g., last 24h only), (d) a UI path to inspect and act.

---

## 5. Product Language Correction

| Term | Assessment | Recommendation |
|------|-----------|----------------|
| **"Dead Letter Queue"** | Developer/infrastructure terminology. OM does not know what this means. | **Remove from OM.** If kept for admin: "Sync Failure Queue" |
| **"OTA events"** | Platform abbreviation. OM thinks in bookings, not events. | **Remove from OM.** If kept for admin: "booking sync entries" |
| **"replay"** | Technical operation. OM cannot perform replay and doesn't know what it means. | **Remove from OM.** For admin only: "retry sync" |
| **"unprocessed OTA events"** | Doubly opaque — combines both problematic terms. | **Remove entirely from OM Hub.** |

---

## Final Decisions

### Is the current briefing trustworthy as-is?

**No.**

### Line-by-line verdict

| Briefing line | Trustworthy? | Action |
|---------------|-------------|--------|
| `"0 check-in(s), 0 check-out(s), 0 cleaning(s) today"` | ✅ Yes | Keep. Correct. |
| `"13 active booking(s)"` | ✅ Yes | Keep. Correct. |
| `"30 open task(s) — 13 high/critical priority"` | ❌ **Misleading** | **Rewrite.** All 30 are future. None require action today. 13 "high" are normal CHECKIN_PREP scheduled weeks ahead. |
| `"⚠ DLQ alert: 7 unprocessed OTA events"` | ❌ **Incorrect/Misleading** | **Remove from OM Hub.** Not tenant-scoped, contains test artifacts, stale (18+ days), no live incidents, no action path for OM. |
| `"Top action: Review and replay Dead Letter Queue entries"` | ❌ **Wrong** | **Remove.** Generated by incorrect signal priority. Developer terminology. No action path exists. |
| Action item: `"Inspect and replay unprocessed Dead Letter Queue entries"` | ❌ **Wrong** | **Remove.** Same reasons. |

---

## Required Fixes (Phase 1043)

### Fix A — Task wording correction
Change `_fetch_tenant_tasks_summary` to separate "needs attention now" (due today + overdue + critical) from "scheduled future work".
Correct heuristic briefing line to distinguish these two categories.

### Fix B — DLQ removed from Morning Briefing context
Remove DLQ summary from `_get_operations_context()` call in `manager_copilot_router.py` — for the purposes of the Morning Briefing, the DLQ signal is not OM-relevant.

The DLQ Inspector remains available at `GET /admin/dlq` for admin users. No change to the admin surface.

### Fix C — System prompt update
Remove DLQ from the LLM system prompt priority list: `"Lead with the most urgent items (SLA breaches, high arrivals days, DLQ alerts)."` — DLQ alerts are not an OM priority.

### Fix D — Heuristic briefing suppression
Remove the DLQ conditional branches from `_build_heuristic_briefing()` for the OM briefing path. The top action should never be "Review DLQ" for an Operational Manager.

---

## Closure

- [x] All Morning Briefing data sources audited with code read + DB verification
- [x] "30 open tasks" proven to be 100% future-scheduled work — 0 actionable today
- [x] DLQ table confirmed as global, non-tenant-scoped, containing stale test artifacts
- [x] DLQ entries proven to be integration-testing artifacts, not live incidents
- [x] iCal-originated failures confirmed to NOT enter `ota_dead_letter`
- [x] Operator action path evaluated — no path exists, DLQ is admin-only
- [x] Product language evaluated — "DLQ", "OTA events", "replay" are all inappropriate for OM surface
- [x] Final decisions documented with specific line-by-line verdict
- [x] Required fixes scoped for Phase 1043

**Phase 1042 CLOSED — audit complete, no code changes (this was a pure audit phase).**
**Phase 1043 = implement the required briefing corrections.**
