# iHouse Core — Master Reload (Mastery Load Documents)

## Purpose
This document is the mandatory reload entrypoint for any new session.
It forces deterministic context loading from repo state (not chat memory).

## Authority Rules
1. Repository files are authoritative. Chat memory is not.
2. Do not modify any docs until the Load Order below is completed.
3. Phase Timeline is append-only. Never overwrite it. Only append new phase closure blocks.
4. If any conflict exists between docs, stop and resolve authority drift before changing code or docs.

## Load Order (Must Read In This Order)
1) docs/core/operating-constitution.md
2) docs/core/session-anchor.md
3) docs/core/construction-log.md
4) docs/core/current-snapshot.md
5) docs/core/canonical-event-architecture.md
6) docs/core/system-identity.md
7) docs/core/live-system.md
8) docs/core/vision.md
9) docs/core/phase-timeline/phase-timeline.md

## Terminal Commands (Copy/Paste)
sed -n '1,260p' docs/core/operating-constitution.md
sed -n '1,260p' docs/core/session-anchor.md
sed -n '1,260p' docs/core/construction-log.md
sed -n '1,260p' docs/core/current-snapshot.md
sed -n '1,260p' docs/core/canonical-event-architecture.md
sed -n '1,260p' docs/core/system-identity.md
sed -n '1,260p' docs/core/live-system.md
sed -n '1,260p' docs/core/vision.md
sed -n '1,260p' docs/core/phase-timeline/phase-timeline.md

## Session Start Checklist
- Identify the latest Closed phase in construction-log.md
- Confirm current phase in current-snapshot.md
- Confirm availability invariants:
  - Overlap scope: (tenant_id, property_id)
  - Range semantics: [check_in, check_out)
  - Active predicate: status IS DISTINCT FROM 'canceled' (NULL is active)
- Only then proceed with implementation or doc updates
