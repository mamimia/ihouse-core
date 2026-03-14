> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 585 → Phase 586–625

## Current State
- **Last Closed Phase:** 585 — Booking Test Suite Repair
- **Next Phase to Execute:** 586
- **This Handoff Covers:** Phases 586–625 (Wave 1 + Wave 2)

## ⚠️ CHAIN PROTOCOL — READ THIS
> After completing ~40 phases (up to Phase 625), you MUST:
> 1. Write a NEW handoff: `releases/handoffs/handoff_to_new_chat Phase-625.md`
> 2. That handoff covers Phases 626–665 (Wave 3 + Wave 4)
> 3. Read `docs/vision/phase-chain-protocol.md` for full rules
> **Each session = ~40 phases. Each session ends with a new handoff for the next.**

## Objective
Execute **Wave 1 (Foundation, 586–605)** and **Wave 2 (Guest Check-in, 606–625)** from the Domaniqo Product Vision Master Roadmap.

## Key Documents — Read These
| File | Purpose |
|------|---------|
| `docs/vision/master_roadmap.md` | **172 phases (586–757)** — the full implementation plan |
| `docs/vision/product_vision.md` | Product bible — what Domaniqo must be |
| `docs/vision/system_vs_vision_audit.md` | Gap analysis — what exists vs what's missing |
| `docs/vision/phase-chain-protocol.md` | Chain protocol — how to hand off every ~40 phases |

## Wave 1 — Foundation (Phases 586–605)
All DB schema extensions. Start here:
```
586: Property GPS (latitude, longitude)
587: Check-in/out times (default 3PM/11AM)
588: Deposit configuration
589: House rules (JSONB)
590: Property details (door code, wifi, AC, etc.)
591: Reference photos schema + Supabase Storage
592: Marketing photos schema
593: Amenities schema + seed data
594: Worker ID system (WRK-001, MGR-001...)
595: Worker action tracking
596: Extras catalog schema + seed (15+ items)
597: Property-extras mapping
598: Problem report schema
599: Guest check-in form schema (Tourist/Resident)
600: Cleaning checklist schema
601: Extra orders schema
602: Guest chat schema
603: Maintenance specialists schema
604: Owner visibility settings schema
605: QR token + manual booking schema
```

## Wave 2 — Guest Check-in (Phases 606–625)
All guest check-in form APIs:
```
606: Guest check-in form core API
607: Add guests to form
608: Passport photo upload
609: Tourist vs Resident logic
610: Deposit collection
611: Digital signature
612: Form submit + complete
613: QR code generation
614: Pre-arrival email with form link
615: Pre-arrival guest self-service
616: Form language selection (EN/TH/HE)
617: Wire guest form to booking_checkin_router
618: Wire QR to checkin response
619-625: Tests + edge cases
```

## Key Files to Modify
```
src/api/onboarding_router.py  — extend Step 1 with new fields
src/api/booking_checkin_router.py — wire guest form + QR
src/services/guest_portal.py — extend with new fields
src/tasks/task_model.py — already has needed TaskKinds
src/i18n/language_pack.py — extend for form labels
supabase/ — new migration files for all new tables
```

## Test Count Baseline
- **7,380 passed, 0 failed, 22 skipped** (as of Phase 585)
