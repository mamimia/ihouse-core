# Handoff to New Chat — Phase 149

**Context at ~80% — handoff initiated per BOOT.md protocol.**  
**Date:** 2026-03-10  
**Time:** 12:18 ICT (UTC+7)  
**Git branch:** `checkpoint/supabase-single-write-20260305-1747`  
**Last commit:** `8248c48` — docs: record UI product layer direction in future-improvements.md

---

## Current Status

| | |
|--|--|
| **Last Closed Phase** | Phase 149 — RFC 5545 VCALENDAR Compliance Audit |
| **Total Tests** | **3836 passed**, 2 pre-existing SQLite skips (unrelated) |
| **Git** | ✅ All committed and clean |
| **Next Phase** | Phase 150 — iCal VTIMEZONE Support |

---

## What This Session Did (Phases 148–149 + Roadmap)

| Phase | Description | Tests |
|-------|-------------|-------|
| 148 | Sync Result Webhook Callback — `_fire_callback()` in `outbound_executor.py`; `IHOUSE_SYNC_CALLBACK_URL`; fires on `ok` only; errors swallowed; 5s timeout; `urllib.request` only | +30 → 3799 |
| 149 | RFC 5545 VCALENDAR Compliance — `CALSCALE:GREGORIAN`, `METHOD:PUBLISH`, `DTSTAMP:UTC`, `SEQUENCE:0` in `_ICAL_TEMPLATE`; PRODID Phase 149; `datetime.now(tz=UTC)` at push time | +37 → 3836 |
| docs | Roadmap revision Phase 150–175 — backend/UI rhythm introduced; `docs/core/planning/phases-150-175.md` written and committed | — |

---

## Phase 150 — What to Do Next

**Phase 150 — iCal VTIMEZONE Support**

Goal: RFC 5545 compliance continuation. Infer timezone from `property_channel_map.timezone`
(new nullable column). When timezone known: emit `VTIMEZONE` component + `TZID`-qualified
`DTSTART`/`DTEND`. When absent: UTC behaviour unchanged.

### Steps:

1. **Migration:**
   ```sql
   ALTER TABLE property_channel_map ADD COLUMN timezone TEXT;
   ```
   Apply via Supabase MCP: `apply_migration(project_id, "phase_150_property_channel_map_timezone", sql)`

2. **Modify `src/adapters/outbound/ical_push_adapter.py`:**
   - Accept `timezone` optional param in `push()`
   - When timezone provided: add `VTIMEZONE` block + `DTSTART;TZID=...:YYYYMMDDTHHMMSS` format
   - When absent: existing UTC format unchanged

3. **New test file:** `tests/test_ical_timezone_contract.py` (~20 tests)
   - UTC fallback when no timezone
   - VTIMEZONE component present when timezone known
   - TZID format correct on DTSTART/DTEND
   - CRLF throughout

4. **Phase closure protocol** (BOOT.md — all steps):
   - Append to `phase-timeline.md`
   - Append to `construction-log.md`
   - Update `current-snapshot.md`
   - Update `work-context.md`
   - Create `docs/archive/phases/phase-150-spec.md`
   - Create `releases/phase-zips/iHouse-Core-Docs-Phase-150.zip`

---

## Roadmap Direction (IMPORTANT — Read This)

**The original `phases-141-190.md` is superseded for Phases 150–175.**

New document: `docs/core/planning/phases-150-175.md`

**Rhythm:** Backend/UI/Backend/UI — not all-API any more.

| Phases | Theme | Type |
|--------|-------|------|
| 150–151 | iCal lifecycle close | Backend |
| 152–153 | Next.js scaffold + Operations Dashboard | **UI** |
| 154–156 | Cancel/Amend push + Property metadata | Backend |
| 157–158 | Worker Mobile + Manager Booking view | **UI** |
| 159–162 | Guest profile + financial hardening | Backend |
| 163–164 | Financial Dashboard + Owner Statement | **UI** |
| 165–168 | Permissions + notifications | Backend |
| 169–170 | Admin Settings + Owner Portal | **UI** |
| 171–174 | Hardening + IPI | Backend |
| 175 | Platform Checkpoint | Milestone |

**UI stack:** Next.js 14 App Router / Tailwind CSS / Fetch with existing Phase 61 JWT.  
**Rule:** UI never reads Supabase directly — all data through FastAPI.

---

## Key Files for New Chat

| File | Purpose |
|------|---------|
| `docs/core/BOOT.md` | Read first — authority rules + all protocols |
| `docs/core/current-snapshot.md` | Phase 149 closed, 3836 tests, Phase 150 next |
| `docs/core/work-context.md` | Active objective + Rhythm note |
| `docs/core/planning/phases-150-175.md` | **Revised roadmap — read before planning Phase 150+** |
| `src/adapters/outbound/ical_push_adapter.py` | Phase 149 iCal template — next phase modifies this |
| `docs/archive/phases/phase-149-spec.md` | Phase 149 spec (reference) |

---

## Key Invariants (Do Not Break)

1. `apply_envelope` is the **only** write authority for canonical booking state
2. `event_log` is **append-only** — no row ever updated
3. `booking_id = {source}_{reservation_ref}` — deterministic, canonical (Phase 36)
4. `booking_state` must **NEVER** contain financial data (Phase 62)
5. `tenant_id` comes from verified JWT `sub` — never from payload body (Phase 61)
6. Outbound sync is always **best-effort and non-blocking** (Phase 135)
7. CRITICAL ACK SLA = **5 minutes** — locked, cannot be shortened (Phase 111)
8. Callback failures are **always swallowed** — never block sync path (Phase 148)
9. iCal is **degraded mode only** — never the primary sync strategy (Phase 135)
10. UI never reads Supabase directly — all through FastAPI (Phase 152+)

---

## Supabase Project

- Project ID: in `.env` — `SUPABASE_PROJECT_ID`
- Current schema: `outbound_sync_log` (Phase 144), `property_channel_map` (Phase 135), `provider_capability_registry` (Phase 136), `tasks` (Phase 114), `booking_financial_facts` (Phase 66), `ota_dead_letter` (Phase 38), `ota_ordering_buffer` (Phase 44)
- Phase 150 needs: `ALTER TABLE property_channel_map ADD COLUMN timezone TEXT`

---

## System Architecture (Unchanged)

```
POST /webhooks/{provider}
  └─ signature_verifier.py   (HMAC-SHA256)
  └─ rate_limiter.py         (per-tenant)
  └─ payload_validator.py
  └─ pipeline.py
       └─ registry.py        (11 OTA adapters)
       └─ adapter.normalize()
       └─ classifier.py
       └─ apply_envelope()   ← ONLY canonical write authority

After BOOKING_CREATED APPLIED (best-effort hooks):
  financial_writer.py → booking_financial_facts
  task_writer.py      → tasks
  outbound_sync_trigger.py → outbound_executor → 5 channel adapters
```

---

**Start the new chat by reading:**
1. `docs/core/BOOT.md`
2. `docs/core/current-snapshot.md`
3. `docs/core/work-context.md`
4. `docs/core/planning/phases-150-175.md` ← new, supersedes old roadmap for Phase 150+

Then proceed directly to **Phase 150 — iCal VTIMEZONE Support**.
