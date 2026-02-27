# Status Model

## Core Principle
Property state is authoritative.
No UI may override state without log entry.

## Property States

### Available
Property has no active booking and no blocking issue.

### Occupied
Property has an active booking and guest is currently staying.

### Cleaning
Checkout completed.
Cleaning task is active.

### Ready
Cleaning completed.
No blocking issues exist.
Next booking (if any) is confirmed.

### At Risk
A condition threatens readiness.
Examples:
- Cleaning not started within SLA
- Major issue before check-in
- Buffer below threshold
- External booking date change causing overlap

### Blocked
Check-in cannot proceed.
Examples:
- Critical infrastructure failure
- Major damage requiring relocation
- Safety issue

## State Transitions

Available → Occupied  
Occupied → Cleaning  
Cleaning → Ready  
Ready → Occupied  
Any → At Risk  
At Risk → Ready  
Any → Blocked  

## Invariant
Every state transition must:
- Generate log entry
- Record timestamp
- Record triggering entity (system / role)