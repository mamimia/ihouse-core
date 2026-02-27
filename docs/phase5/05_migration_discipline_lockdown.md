# iHouse Core Phase 5
## 05 Migration Discipline Lockdown

Status: Draft
Scope: Repo process, CI gates, release discipline

### Goal
Prevent any future change that can break replay
by locking policy into code review and CI.

### Hard Rules
1. No migration merges without passing replay gates.
2. No event contract change without version bump rules.
3. No projection semantic changes without explicit domain event.
4. No conditional logic based on schema version.
5. No rewriting historical events.

### Required Artifacts Per Change Type

Event change that requires new event_version:
1. Update LATEST registry
2. Add upcaster chain
3. Add fixtures for old version and canonical
4. Add replay test that includes old version fixtures

Non additive migration:
1. Migration classification recorded
2. Cross version fingerprint test added
3. Staging replay run recorded

Structural rewrite:
1. Written invariants and rollback plan
2. Diff capability proof or equivalent debugging path
3. Explicit approval from core owners

### CI Gates

Gate A Event Contract Gate
1. Validate every event_type has LATEST defined
2. Validate upcaster chain completeness for all supported versions
3. Reject unknown future event_version

Gate B Replay Determinism Gate
1. rebuild runs twice
2. fingerprints must match

Gate C Cross Version Replay Gate
For any migration marked non additive:
1. rebuild on baseline schema snapshot
2. apply migration
3. rebuild again
4. fingerprints must match

Gate D Fixture Coverage Gate
If LATEST or UPCASTERS changed:
1. at least one fixture per old version must exist
2. at least one replay test must reference them

### Review Discipline

Code Owners
Core owners must approve changes in:
1. events envelope
2. event registry and upcasters
3. rebuild engine
4. migrations folder
5. projection handlers

PR Checklist Must Be Completed
1. I did not change meaning of old events
2. I did not add non deterministic behavior
3. If I changed payload contract, I bumped event_version
4. If I bumped event_version, I added upcasters and fixtures
5. validate_rebuild passes
6. cross version fingerprint test passes when required
7. rollback plan exists for high risk changes

### Release Discipline

Release must include:
1. migration plan
2. runtime compatibility notes
3. staging evidence of replay gates passing

No hotfix bypass.
If production breaks, fix forward with new events or new projections.
Never rewrite old events.

### Enforcement Notes
This policy is enforced by CI and ownership gates.
If someone can merge without these steps, the system is not production grade.

