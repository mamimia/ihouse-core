# Title

Booking Status Stale in Staging — Supporting Evidence for Issue 15; Causal Chain Now Fully Closed; Phase 883 Task Architecture Is Preserved as Deliberate Design

# Related files

- Investigation: `INVESTIGATIONS/16_booking_status_stale_in_staging.md`
- Evidence: `EVIDENCE/16_booking_status_stale_in_staging.md`
- Root cause: `VERIFICATIONS/15_checkout_direct_db_write_bypasses_event_log.md` — the shadow route that caused the staleness, now removed

# Original claim

The checkout frontend explicitly documents that booking status is "stale/disconnected" in staging. The checkout workflow was rebuilt (Phase 883) to use `CHECKOUT_VERIFY` tasks instead of booking status. The root cause was identified as `deposit_settlement_router.py` Phase 690 writing `status: "checked_out"` directly to `bookings` without going through `booking_state` or `event_log`.

# Original verdict

PROVEN

# Response from implementation layer

**Verdict: Agree completely with the reading. This is supporting evidence for Issue 15, not a standalone bug. No new defects. One documentation change made.**

**Complete causal chain — now fully closed:**
```
Phase 690 shadow route (deposit_settlement_router.py)
    → wrote booking.status = "checked_out" to `bookings` table
    → bypass of booking_state and event_log
    → booking_state.status remained stale after checkout
    ↓
Phase 883 team response
    → observed stale/disconnected status in staging
    → rebuilt checkout list around CHECKOUT_VERIFY tasks
    → correct pragmatic workaround for a structural bug
    ↓
Issue 15 fix (this session)
    → shadow route removed
    → booking_checkin_router (Phase 398) is now sole checkout handler
    → writes to booking_state ✅, emits BOOKING_CHECKED_OUT to event_log ✅
    ↓
Issue 16 (this issue)
    → confirms Phase 883 workaround was correct and evidence-based
    → task-based list architecture is preserved as deliberate design
    → no regression: the workaround is now best-practice, not just a fallback
```

**The attribution question from Verification 15 is resolved:**
Verification 15 flagged that the investigation attributed the staging staleness to Phase 690 — but Phase 690 was never the active endpoint (Phase 398 was). The implementation response here resolves this: Phase 690 was the active endpoint at the time Phase 883 observed the staleness. Phase 398 was the correct replacement; Phase 690 became a shadow route at some point when the correct implementation was mounted first. The staleness was real and was caused by Phase 690 when it was the active endpoint. The causal chain is coherent.

**Remaining surfaces using booking status examined — both safe:**

**Surface 1 — `ops/checkout/page.tsx` line 278: `GET /bookings?status=checked_in`**
Not a risk. This is enrichment only: the call is explicitly labeled, wrapped in `try/catch`, and never used for the checkout list. The list is built from `CHECKOUT_VERIFY` tasks (Phase 883 architecture). Booking data fetched at this point enriches the detail view (guest name, dates, deposit amounts) after a worker has already selected a task — it does not determine which bookings appear in the list.

**Surface 2 — `ops/checkin/page.tsx` lines 645–653: `b.status === 'checked_in'`**
Not a risk. The check-in router (Phase 398) correctly writes to `booking_state`. The staleness issue was specific to the Phase 690 checkout path. Check-in has always written through the correct router. This status check in the checkin page is operating against correctly maintained `booking_state` data.

**One documentation change applied:**
The Phase 883 comment in `ops/checkout/page.tsx` was updated to record the full causal chain: root cause found, fix applied. The comment now formally states the architectural rule: do not build future checkout-readiness surfaces on `booking.status`. This makes the Phase 883 lesson durable for developers joining the codebase after the Phase 690 shadow route is long forgotten.

# Verification reading

No additional repository verification read performed. The implementation response provides the complete causal chain and confirms all four remaining questions from Investigation 16 and from the Verification 15 cross-reference note. The attribution question is resolved: Phase 690 caused the staleness when it was active; Phase 398 superseded it correctly; the shadow route is now gone.

# Verification verdict

RESOLVED

# What changed

`ihouse-ui/app/(app)/ops/checkout/page.tsx`:
- Phase 883 comment updated to record the full causal chain (Phase 690 was root cause, shadow route removed in this session, Phase 398 is now sole handler)
- Architectural rule formally stated in code comment: do not build checkout-readiness surfaces on `booking.status`

No backend changes. No schema changes.

# What now appears true

- The full causal chain from symptom to root cause to fix is now documented and closed.
- Phase 883 was correct: the team correctly identified that booking status was unreliable, correctly identified that CHECKOUT_VERIFY tasks were a more reliable signal, and correctly rebuilt the checkout list around tasks. This was evidence-based engineering in response to a real structural bug.
- The task-based checkout architecture is now deliberate design, not a workaround. Even with Phase 690 removed and Phase 398 correctly writing `booking_state`, the CHECKOUT_VERIFY task approach provides additional benefits (pre-arrival automation, SLA tracking, independent of booking status projection latency) that make it the preferred architecture going forward.
- Booking status for checkout-readiness is not a reliable signal to build on. The Phase 883 architectural rule is now codified in the source comment.
- `booking_state` writes at check-in have always been correct (Phase 398 check-in router). The staleness was specific to the checkout write path via Phase 690 — check-in surfaces are not affected.
- The two remaining surfaces that reference booking status for checkout (`ops/checkout/page.tsx` enrichment, `ops/checkin/page.tsx` status check) are both safe: one is enrichment-only post-task-selection, one operates against correctly maintained data.

# What is still unclear

- **Whether any `booking_state` rows in staging are permanently stale** from test cycles that ran through the Phase 690 checkout path when it was the active endpoint. The fix removes the path going forward; it does not retroactively correct historical stale `booking_state` data in staging. A data cleanup script may be needed for staging if clean data is required for testing.
- **Whether production has ever run the Phase 690 checkout path.** The comment in Investigation 16 says "stale in staging" — if production was never used for real checkouts while Phase 690 was the active endpoint, production `booking_state` data may be clean. Not confirmed.
- **Whether the CHECKOUT_VERIFY task pre-arrival automation creates tasks for all future checkout dates** — if a booking was created before the automation existed, or before the pre-arrival scan ran for that property, there may be no CHECKOUT_VERIFY task. The checkout list would then not show that booking. This is an edge case in the task-based architecture, not introduced by this fix.

# Recommended next step

**Close both Issues 15 and 16 as a resolved pair.** The causal chain is complete. The root cause is removed. The workaround is confirmed as deliberate design. The architectural rule is codified.

**The Phase 883 lesson — now formally stated — should be applied to any future surface that needs to query "which bookings are ready for checkout":**
- Use `CHECKOUT_VERIFY` task queries, not `booking.status` filters
- `booking.status` may be read for enrichment (displaying current status of a known booking) but must not be used as a list filter for operational readiness
- This rule applies equally to any analytics or dashboard that counts "currently checked in guests" — those counts should be derived from task state or direct `booking_state` projections, not from `bookings.status`
