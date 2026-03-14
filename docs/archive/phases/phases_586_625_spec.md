# Phases 586–625 — Wave 1 Foundation + Wave 2 Guest Check-in

## Closed: 2026-03-14

### Wave 1 — Foundation (Phases 586–605)

| Phase | What | File(s) |
|-------|------|---------|
| 586 | Property GPS & Location | `property_location_router.py`, migration |
| 587 | Check-in/out Times | `properties_router.py` PATCH extended |
| 588 | Deposit Configuration | `properties_router.py` PATCH extended |
| 589 | House Rules JSONB | `property_house_rules_router.py` |
| 590 | Property Details | `properties_router.py` PATCH extended (16 fields) |
| 591 | Reference Photos | `property_photos_router.py` |
| 592 | Marketing Photos | `property_photos_router.py` |
| 593 | Amenities + Seed | `property_amenities_router.py` |
| 594 | Worker ID System | Migration (ALTER TABLE users) |
| 595 | Worker Action Tracking | Migration (task_actions table) |
| 596 | Extras Catalog | `extras_catalog_router.py` |
| 597 | Property-Extras Mapping | `property_extras_router.py` |
| 598 | Problem Reports | `problem_report_router.py` |
| 599 | Guest Check-in Form Schema | Migration (3 tables) |
| 600 | Cleaning Checklist Schema | Migration (3 tables) |
| 601 | Extra Orders Schema | Migration |
| 602 | Guest Chat Schema (extend) | Migration (via guest_messages) |
| 603 | Maintenance Specialists | Migration (2 tables) |
| 604 | Owner Visibility Settings | `owner_visibility_router.py` |
| 605 | QR Token + Manual Booking | Migration + booking_state columns |

### Wave 2 — Guest Check-in (Phases 606–625)

| Phase | What | File(s) |
|-------|------|---------|
| 606 | Form Create/Get API | `guest_checkin_form_router.py` |
| 607 | Add Guests API | `guest_checkin_form_router.py` |
| 608 | Passport Photo Upload | `guest_checkin_form_router.py` |
| 609 | Tourist vs Resident Logic | `checkin_form_labels.py` |
| 610 | Deposit Collection API | `guest_checkin_form_router.py` |
| 611 | Digital Signature API | `guest_checkin_form_router.py` |
| 612 | Form Submit + Complete | `guest_checkin_form_router.py` |
| 613 | QR Code Generation | `guest_checkin_form_router.py` |
| 614 | Pre-Arrival Email Enhancement | Deferred (requires live SMTP) |
| 615 | Guest Self-Service Portal | `guest_checkin_form_router.py` |
| 616 | Language Selection EN/TH/HE | `checkin_form_labels.py` |
| 617 | Wire Form to Checkin Router | Deferred (requires live booking) |
| 618 | Wire QR to Checkin Response | Deferred (requires live booking) |
| 619-625 | Tests + Edge Cases | `test_wave2_guest_checkin_contract.py` |

### Test Count
- Before: 7,380 passed, 0 failed, 22 skipped
- After: 7,456 passed, 0 failed, 22 skipped
- New tests: 76 (45 Wave 1 + 31 Wave 2)

### Migration
- `supabase/migrations/20260314201500_phase586_605_foundation.sql` — 18 new tables, ~30 new columns

### Files Created/Modified
- 9 new API routers in `src/api/`
- 1 i18n module: `src/i18n/checkin_form_labels.py`
- 1 migration: `supabase/migrations/`
- 2 test files: `tests/test_wave1_foundation_contract.py`, `tests/test_wave2_guest_checkin_contract.py`
- Modified: `src/api/properties_router.py`, `src/main.py`
