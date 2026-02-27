#!/usr/bin/env bash
set -euo pipefail

META_FILE="${1:-PR_METADATA.txt}"

if [[ ! -f "$META_FILE" ]]; then
  echo "Missing $META_FILE"
  echo "Create it with one line:"
  echo "behavior_change_intent=none"
  echo "or"
  echo "behavior_change_intent=explicit_event_change"
  exit 1
fi

VAL="$(grep -E '^behavior_change_intent=' "$META_FILE" | tail -n 1 | cut -d= -f2 || true)"

if [[ "$VAL" != "none" && "$VAL" != "explicit_event_change" ]]; then
  echo "Invalid behavior_change_intent in $META_FILE"
  echo "Allowed values: none, explicit_event_change"
  exit 1
fi

echo "OK behavior_change_intent=$VAL"
