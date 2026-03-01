#!/usr/bin/env python3
import sys
import json

RUNNER_DISABLED = "SKILL_RUNNER_DISABLED_USE_CORE"


def _error(skill=None):
    return {
        "ok": False,
        "runner": "skill_runner",
        "skill": skill,
        "result": {
            "error_code": RUNNER_DISABLED,
            "warnings": [
                "SKILL_RUNNER_DISABLED",
                "USE_CANONICAL_PATH_FASTAPI_COREAPI_ONLY"
            ],
        },
    }


def main() -> int:
    skill = sys.argv[1] if len(sys.argv) >= 2 else None

    # Consume stdin to keep callers stable, but do not execute anything.
    try:
        _ = json.load(sys.stdin)
    except Exception:
        pass

    sys.stdout.write(json.dumps(_error(skill=skill)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
