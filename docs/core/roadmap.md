# iHouse Core – Roadmap


Completed

Phase 21  
External OTA ingestion boundary defined.

Phase 22  
OTA adapter layer introduced with normalization and validation.

Phase 23  
Semantic classification layer introduced for OTA events.

Phase 24  
OTA modification semantic recognition (MODIFY) introduced with
deterministic rejection of unresolved modification events.

Phase 25  
OTA modification resolution rules closed with deterministic
reject-by-default preserved.

Phase 26  
OTA payload contract verification completed across multiple providers.

Phase 27  
Multi-OTA adapter architecture introduced with a shared pipeline,
multi-provider registry, and provider extensibility proof through
Booking.com plus an Expedia scaffold adapter.


Upcoming


Phase 28  
OTA external surface decision.

Goal:
Decide whether the current single external OTA envelope kind
(`BOOKING_SYNC_INGEST`) remains sufficient for multi-provider scale,
or whether the canonical external surface must be split into more
explicit deterministic kinds.

Key question:
Should the OTA boundary continue to emit one canonical external
envelope kind with semantic differentiation inside payload fields,
or should CREATE and CANCEL outcomes be represented by more explicit
external canonical kinds?

Constraint:
No reconciliation layer may be introduced in this phase.
No booking_state lookup may be introduced in this phase.


Phase 29  
OTA ingestion replay harness.

Goal:
Create deterministic replay tools to simulate external OTA event
streams against the canonical ingestion pipeline.


Phase 30  
External integration test harness.

Goal:
End-to-end verification of OTA ingestion behavior across adapters,
including rejection scenarios and replay safety.


Phase 31  
Operational observability for OTA ingestion.

Goal:
Introduce structured logging, metrics, and ingestion visibility
for OTA adapters without modifying the deterministic event model.
