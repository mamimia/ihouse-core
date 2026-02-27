import sys
import json
import subprocess

# --- Deterministic Error Codes ---
INPUT_NOT_JSON = "INPUT_NOT_JSON"
INPUT_INVALID = "INPUT_INVALID"
MISSING_KIND = "MISSING_KIND"
NO_ROUTE = "NO_ROUTE"
SKILL_RUN_FAILED = "SKILL_RUN_FAILED"
RUNNER_OUTPUT_NOT_JSON = "RUNNER_OUTPUT_NOT_JSON"


# --- Hard Mapping: kind → skill ---
KIND_TO_SKILL = {
    "STATE_TRANSITION": "state-transition-guard",
    "BOOKING_CONFLICT": "booking-conflict-resolver",
    "TASK_COMPLETION": "task-completion-validator",
    "SLA_ESCALATION": "sla-escalation-engine",
}


def error_response(code, kind=None, request_id=None):
    return {
        "ok": False,
        "route": "event_router",
        "skill": None,
        "kind": kind,
        "request_id": request_id,
        "result": {
            "error_code": code
        }
    }


def validate_envelope(data):
    if not isinstance(data, dict):
        return False

    if "kind" not in data:
        return MISSING_KIND

    if "idempotency" not in data or not isinstance(data["idempotency"], dict):
        return INPUT_INVALID

    if "request_id" not in data["idempotency"]:
        return INPUT_INVALID

    if "actor" not in data or not isinstance(data["actor"], dict):
        return INPUT_INVALID

    if "actor_id" not in data["actor"]:
        return INPUT_INVALID

    if "role" not in data["actor"]:
        return INPUT_INVALID

    if "payload" not in data:
        return INPUT_INVALID

    return None


def main():
    raw_input = sys.stdin.read()

    try:
        envelope = json.loads(raw_input)
    except Exception:
        print(json.dumps(error_response(INPUT_NOT_JSON)))
        sys.exit(0)

    validation_error = validate_envelope(envelope)
    if validation_error:
        kind = envelope.get("kind")
        request_id = envelope.get("idempotency", {}).get("request_id")
        print(json.dumps(error_response(validation_error, kind, request_id)))
        sys.exit(0)

    kind = envelope["kind"]
    request_id = envelope["idempotency"]["request_id"]

    if kind not in KIND_TO_SKILL:
        print(json.dumps(error_response(NO_ROUTE, kind, request_id)))
        sys.exit(0)

    skill_name = KIND_TO_SKILL[kind]

    try:
        process = subprocess.run(
            ["python3", ".agent/system/skill_runner.py", skill_name],
            input=json.dumps(envelope),
            text=True,
            capture_output=True,
        )
    except Exception:
        print(json.dumps(error_response(SKILL_RUN_FAILED, kind, request_id)))
        sys.exit(0)

    if process.returncode != 0:
        print(json.dumps(error_response(SKILL_RUN_FAILED, kind, request_id)))
        sys.exit(0)

    try:
        skill_output = json.loads(process.stdout)
    except Exception:
        print(json.dumps(error_response(RUNNER_OUTPUT_NOT_JSON, kind, request_id)))
        sys.exit(0)

    response = {
        "ok": True,
        "route": "event_router",
        "skill": skill_name,
        "kind": kind,
        "request_id": request_id,
        "result": skill_output
    }

    print(json.dumps(response))


if __name__ == "__main__":
    main()
    