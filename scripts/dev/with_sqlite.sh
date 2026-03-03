#!/usr/bin/env bash
set -euo pipefail
export IHOUSE_ALLOW_SQLITE=1
exec env "$@"
