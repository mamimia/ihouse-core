import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVENT_ROUTER = REPO_ROOT / ".agent" / "system" / "event_router.py"
SMOKE_DIR = REPO_ROOT / "smoke_events"

def run_router(smoke_file: Path) -> dict:
    if not EVENT_ROUTER.exists():
        raise AssertionError(f"Missing event_router.py at {EVENT_ROUTER}")
    if not smoke_file.exists():
        raise AssertionError(f"Missing smoke event file at {smoke_file}")

    payload = smoke_file.read_text(encoding="utf-8")

    p = subprocess.run(
        [sys.executable, str(EVENT_ROUTER)],
        input=payload,
        text=True,
        capture_output=True,
        cwd=str(REPO_ROOT),
    )

    if p.returncode != 0:
        raise AssertionError(f"event_router failed\nstdout:\n{p.stdout}\nstderr:\n{p.stderr}")

    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON from event_router: {e}\nstdout:\n{p.stdout}\nstderr:\n{p.stderr}")

def assert_common_envelope(out: dict, kind: str, request_id: str):
    assert out.get("ok") is True
    assert out.get("route") == "event_router"
    assert out.get("kind") == kind
    assert out.get("request_id") == request_id
    assert isinstance(out.get("result"), dict)

def test_state_transition_smoke():
    out = run_router(SMOKE_DIR / "01_state_transition.json")
    assert_common_envelope(out, "STATE_TRANSITION", "smoke_state_transition_001")
    decision = out["result"].get("decision") or {}
    assert decision.get("allowed") is True
    assert decision.get("allowed_next_state") == "CONFIRMED"

def test_booking_conflict_smoke():
    out = run_router(SMOKE_DIR / "02_booking_conflict.json")
    assert out.get("ok") is True
    assert out.get("kind") == "BOOKING_CONFLICT"
    assert out.get("request_id") == "smoke_booking_conflict_001"
