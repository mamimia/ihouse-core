# Phase 34 — OTA Canonical Event Emission Alignment (COMPLETE)

## Routing Verification
- [x] Verify which active skill handles `BOOKING_CREATED`
- [x] Verify which active skill handles `BOOKING_CANCELED`
- [x] Verify whether those skills emit canonical business events or noop
- [x] Verify whether any alternate routing path exists

## Emitted Event Mapping Verification
- [x] Inspect canonical payload shape required by `apply_envelope`
- [x] Inspect emitted event shape produced by active OTA runtime path
- [x] Identify exact field and routing mismatch

## Minimal Alignment Definition
- [x] Define smallest safe future change for canonical alignment
- [x] Write implementation plan artifact with evidence
- [x] Notify user for review

## Documentation Updates
- [x] Update active docs minimally based on evidence

## Phase Closure
- [x] Verify all 5 required questions answered with evidence
- [x] Verify all completion conditions met
- [x] Get user approval for closure
- [x] Append to [phase-timeline.md](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/docs/core/phase-timeline.md)
- [x] Append to [construction-log.md](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/docs/core/construction-log.md)
- [x] Update [current-snapshot.md](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/docs/core/current-snapshot.md)
- [x] Prepare [phase-35-spec.md](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/docs/core/phase-35-spec.md)
- [x] Archive [phase-34-spec.md](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/docs/core/phase-34-spec.md)
- [x] Git push

---

# Phase 35 — OTA Canonical Emitted Event Alignment Implementation

## Implementation
- [ ] Implement [booking_created](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/tests/test_ota_replay_harness.py#120-138) skill (payload transformation)
- [ ] Implement [booking_canceled](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/tests/test_ota_replay_harness.py#140-158) skill
- [ ] Update [kind_registry.core.json](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/src/core/kind_registry.core.json)
- [ ] Update [skill_exec_registry.core.json](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/src/core/skill_exec_registry.core.json)

## Verification
- [ ] Add contract tests for new skills
- [ ] Verify E2E flow from OTA webhook to Supabase `p_emit`
