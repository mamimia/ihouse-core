import sys
import json

ROUTER_DISABLED = "ROUTER_DISABLED_USE_CORE"


def _error(kind=None, request_id=None):
    return {
        "ok": False,
        "route": "event_router",
        "skill": None,
        "kind": kind,
        "request_id": request_id,
        "result": {
            "error_code": ROUTER_DISABLED,
            "warnings": [
                "EVENT_ROUTER_DISABLED",
                "USE_CANONICAL_PATH_FASTAPI_COREAPI_ONLY"
            ],
        },
    }


def main():
    raw = sys.stdin.read() or ""
    kind = None
    request_id = None

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            kind = data.get("kind")
            idem = data.get("idempotency", {})
            if isinstance(idem, dict):
                request_id = idem.get("request_id")
    except Exception:
        pass

    sys.stdout.write(json.dumps(_error(kind=kind, request_id=request_id)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
