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


Upcoming


Phase 25  
Deterministic OTA modification resolution rules.

Goal:
Determine whether a safe subset of OTA modification events can be
resolved using payload semantics alone.

Only payload-deterministic modification events may be accepted.
All ambiguous modification events must continue to be rejected.


Phase 26  
OTA payload contract verification.

Goal:
Document and verify provider payload guarantees for Booking.com
modification events.

Determine which payload fields can safely signal deterministic
booking updates.


Phase 27  
Multi-OTA adapter architecture.

Goal:
Introduce additional OTA adapters (e.g. Airbnb) while preserving
the canonical ingestion pipeline and adapter contract.


Phase 28  
OTA ingestion replay harness.

Goal:
Create deterministic replay tools to simulate external OTA event
streams against the canonical ingestion pipeline.


Phase 29  
External integration test harness.

Goal:
End-to-end verification of OTA ingestion behavior across adapters,
including rejection scenarios and replay safety.


Phase 30  
Operational observability for OTA ingestion.

Goal:
Introduce structured logging, metrics, and ingestion visibility
for OTA adapters without modifying the deterministic event model.
