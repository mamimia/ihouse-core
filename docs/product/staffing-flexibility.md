# Check-in / Check-out Staffing Flexibility — Product Direction

> Status: **Future** · Phase: TBD · Priority: Medium

## Concept

Check-in and check-out are **always two separate screens and two separate workflows**,
but they are **not always two separate people**.

- The **same worker** can do both check-in and check-out (they see both screens, switch between them)
- **Two different workers** can each handle one of the two (each sees only their assigned screen)
- The **admin decides** the staffing — per property, per task kind

The key principle: the system never merges the two operations into one screen,
but the staffing model is fully flexible.

## Rules

1. **Screens are always separate** — check-in screen and check-out screen are two distinct UI surfaces, always
2. **People are flexible** — one person can do both, or two different people can each do one
3. **Admin controls staffing assignment** — per property, per task kind
4. **Same person scenario** → they see both screens, can switch between them
5. **Different people scenario** → each gets their assigned screen only
6. **No hard coupling** between check-in and check-out at the data model level

## Data Model Implications

- `worker_role` field on tasks: `checkin` or `checkout` (already exists)
- Role assignment is per-property, per-task-kind (not global)
- `tenant_permissions` supports multiple roles per user (future) or role aggregation

## Staffing Configurations

| Config | Check-in Staff | Check-out Staff | UX |
|--------|----------------|-----------------|-----|
| **One person** | Alice | Alice | Alice sees both surfaces, tab/toggle switch |
| **Two people** | Alice | Bob | Each sees only their assigned surface |
| **Rotating** | Schedule-based | Schedule-based | Daily/weekly assignment via worker availability |

## Implementation Notes

- The current role model (`checkin`, `checkout`) already supports separate roles
- When same person: UI shows both tabs; backend doesn't need to change
- Worker availability system (Phase 234) already handles scheduling
- Task automator (Phase 111) already assigns by `worker_role`

## Non-Goals

- Merging check-in and check-out into a single workflow
- Removing the distinction between the two operations
- Making role assignment implicit or automatic
