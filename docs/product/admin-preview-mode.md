# Admin Preview Mode — Product Direction

> Status: **Future** · Phase: TBD · Priority: Low

## Concept

An internal tool for admins to view the system from the perspective of different roles
(worker, manager, owner, check-in, check-out, maintenance) without full impersonation.

## Rules

1. **Read-only** — Preview Mode shows the UI exactly as that role sees it, but no actions
   are taken on behalf of other users
2. **Clearly marked** — A persistent visual indicator (banner + border tint) shows
   "Preview: Worker View" or "Preview: Owner View" at all times
3. **No mutations** — API calls in preview mode use a `X-Preview-Role` header; the backend
   responds with the same data that role would see but blocks all POST/PUT/PATCH/DELETE
4. **Audit logged** — Every preview session is logged with the admin's real identity and the
   previewed role
5. **No credential exposure** — The admin never receives the target user's token or session

## Implementation Approach

1. Frontend: Toggle in admin navbar → sets `previewRole` in app state
2. Frontend: All API calls include `X-Preview-Role: worker` header
3. Backend: Middleware reads `X-Preview-Role`, verifies caller is admin, returns data
   scoped for that role but blocks all write operations
4. Backend: Audit event `PREVIEW_SESSION_STARTED` / `PREVIEW_SESSION_ENDED`

## Use Cases

- Admin wants to verify what a worker sees after task assignment
- Admin wants to check owner portal data accuracy before sharing with property owner
- Admin wants to test role-based surface layout during development

## Non-Goals

- Full impersonation (acting as another user)
- Token sharing or credential delegation
- Multi-tenant preview (viewing another tenant's data)
