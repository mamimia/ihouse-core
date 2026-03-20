# Phase 855D — Auth Identity Model Design

**Status:** Closed
**Prerequisite:** Phase 855C (Google OAuth E2E Proof)
**Date Closed:** 2026-03-20

## Goal

Design a comprehensive identity architecture that separates Supabase Auth users (login identities) from canonical internal users, supports linked identities, and defines explicit rules for identity binding, post-login routing, and UI requirements.

## Design / Files

| File | Change |
|------|--------|
| `auth_identity_architecture.md` (artifact) | NEW — Decision map, routing matrix, data model (internal_users, linked_identities, leads tables), UI page list, 5-phase implementation plan |

## Result

Architecture document produced covering:
- Decision map for login identity resolution
- Post-login routing matrix (platform user, pending access, suspended, new lead)
- Data model for linked identities (multiple login methods per internal user)
- UI requirements (intake form, waiting/suspended pages, connected accounts, admin lead review)
- 5-phase implementation order

**Note:** This design was subsequently superseded by the Phase 855E audit findings, which concluded that the full linked-identity architecture is over-engineered for the current use case. The simpler admin-email-change approach was recommended instead. The architecture document remains as a reference for future expansion.
