# releases/

This directory holds generated artifacts from iHouse Core phase closures.

## Structure

| Folder | Contents |
|--------|---------|
| `phase-zips/` | Phase ZIP archives — `iHouse-Core-Docs-Phase-<N>.zip` — one per closed phase |
| `handoffs/` | Handoff files for new chat sessions — `handoff_to_new_chat Phase-<N>.md` |

## Protocol (enforced in `docs/core/BOOT.md`)

- **Phase ZIPs:** created at end of every phase closure, placed directly in `releases/phase-zips/`
- **Handoff files:** created when context reaches ~80%, placed directly in `releases/handoffs/`
- **Never** place these files in the repo root

## Naming conventions

```
releases/phase-zips/iHouse-Core-Docs-Phase-65.zip
releases/handoffs/handoff_to_new_chat Phase-65.md
```
