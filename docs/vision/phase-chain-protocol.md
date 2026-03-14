# Phase Chain Protocol — Domaniqo Vision Implementation

## Rule
The Master Roadmap (`docs/vision/master_roadmap.md`) contains **172 phases (586–757)**.
No single chat session can complete all 172. Therefore:

> **Each session executes ~40 phases, then writes a handoff for the next session.**

## Chain Schedule

| Session | Phases | Waves | Handoff Written |
|---------|--------|-------|-----------------|
| 1 | 586–625 | Wave 1 (Foundation) + Wave 2 (Guest Check-in) | `handoff_to_new_chat Phase-625.md` |
| 2 | 626–665 | Wave 3 (Task Enhancement) + Wave 4 (Problem Reporting) | `handoff_to_new_chat Phase-665.md` |
| 3 | 666–705 | Wave 5 (Guest Portal & Extras) + Wave 6 (Checkout & Deposit) | `handoff_to_new_chat Phase-705.md` |
| 4 | 706–757 | Wave 7 + Wave 8 + Wave 9 + Wave 10 (remaining) | `handoff_to_new_chat Phase-757.md` (final) |

## Handoff Requirements

Every handoff file MUST:

1. **Location:** `releases/handoffs/handoff_to_new_chat Phase-{N}.md`
2. **First line:** `> ⚠️ FIRST: Read docs/core/BOOT.md before doing anything else.`
3. **Include:**
   - Last closed phase number and name
   - Next phase to execute
   - Exact phases this handoff covers (e.g., "626–665")
   - Phase-by-phase summary of what to build
   - Key files to read and modify
   - Test count baseline
   - **This protocol reference:** "Read `docs/vision/phase-chain-protocol.md`"
   - **Chain instruction:** "After completing these phases, write the NEXT handoff"

4. **Include the Domaniqo context:**
   - Reference `docs/vision/master_roadmap.md` for full phase details
   - Reference `docs/vision/product_vision.md` for requirements
   - Reference `docs/vision/system_vs_vision_audit.md` for gap analysis

## Session End Checklist

Before ending a session, the assistant MUST:
- [ ] Close all completed phases per BOOT.md phase closure protocol
- [ ] Update `docs/core/current-snapshot.md`
- [ ] Update `docs/core/work-context.md`
- [ ] Update `docs/core/phase-timeline.md` (append)
- [ ] Update `docs/core/construction-log.md` (append)
- [ ] Create spec files for all closed phases
- [ ] Create ZIP for last closed phase
- [ ] Write handoff for next session covering the NEXT ~40 phases
- [ ] Git commit + push

## Important Notes

- The `master_roadmap.md` is the SINGLE SOURCE OF TRUTH for what each phase does
- Each phase in the roadmap has detailed DB schemas, API specs, and test requirements
- Existing iHouse Core infrastructure should be leveraged wherever noted in the roadmap
- Reserved phases exist in each wave for iteration — use them if needed
- If a phase takes longer than expected, it's OK to reduce the batch — just adjust the handoff
