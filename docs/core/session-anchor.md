# iHouse Core – Session Anchor

## SPINE Trigger

If context is unclear or drift is suspected, type:

SPINE

When SPINE is triggered:

ChatGPT must NOT rely on memory.

ChatGPT must request the following terminal commands.

---

## Terminal Commands to Execute

Run these commands one by one in terminal:

sed -n '1,400p' docs/core/current-snapshot.md

sed -n '1,400p' docs/core/system-identity.md

sed -n '1,400p' docs/core/canonical-event-architecture.md

sed -n '1,400p' docs/core/construction-log.md

---

## Procedure

1. Execute each command.
2. Paste the full output into chat.
3. ChatGPT must identify the last locked Phase from construction-log.
4. Resume execution strictly from the last stable boundary.

---

## Authority Rule

Repository state is the single source of truth.

Chat memory is not authoritative.

If repository state contradicts conversation context,
repository state wins.

SPINE is mandatory before architectural decisions.

