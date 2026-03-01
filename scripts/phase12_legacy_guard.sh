#!/usr/bin/env bash
set -euo pipefail

# Phase 12 Legacy Guard
# Fails deterministically if anything under .agent/skills changed (except .gitkeep).
# This is a safety rail to prevent accidental edits in legacy skill scripts after Core ports.

if ! command -v git >/dev/null 2>&1; then
  echo "LEGACY_GUARD_FAIL git_not_found"
  exit 2
fi

# Must be inside a git work tree
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "LEGACY_GUARD_FAIL not_a_git_repo"
  exit 2
fi

# Show only changes under .agent/skills
# Allow .gitkeep changes (ignored)
CHANGED="$(git status --porcelain -- .agent/skills | awk '{print $2}' | grep -vE '\.gitkeep$' || true)"

if [[ -n "${CHANGED}" ]]; then
  echo "LEGACY_GUARD_FAIL legacy_skills_modified"
  echo "${CHANGED}"
  exit 2
fi

echo "LEGACY_GUARD_OK"
