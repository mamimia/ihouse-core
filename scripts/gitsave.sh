#!/usr/bin/env bash
set -euo pipefail

msg="${1:-wip autosave}"
if git diff --quiet && git diff --cached --quiet; then
  echo "No changes to save"
  exit 0
fi

git add -A
git commit -m "$msg"
echo "Saved: $msg"
