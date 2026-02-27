import json
import subprocess
import sys

PY = sys.executable

def run_py(args: list[str]) -> str:
    p = subprocess.run(
        [PY] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if p.returncode != 0:
        raise AssertionError(
            f"Command failed: {PY} {' '.join(args)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p.stdout

def test_deterministic_rebuild_validation() -> None:
    run_py(["-m", "core.db.validate_rebuild"])

def test_booking_overlaps_are_tracked() -> None:
    run_py(["scripts/test/run_rebuild.py"])
    run_py(["scripts/test/assert_booking_overlaps_are_tracked.py"])

def test_booking_conflict_consistency() -> None:
    run_py(["scripts/test/run_rebuild.py"])
    run_py(["scripts/test/assert_booking_conflict_consistency.py"])

def test_fingerprint_snapshot_is_json() -> None:
    out = run_py(["scripts/test/snapshot_fingerprints.py"]).strip()
    data = json.loads(out)
    assert isinstance(data, list)
    assert all("table" in x and "sha256" in x for x in data)
