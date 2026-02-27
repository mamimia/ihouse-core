import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import sqlite3
from core.db.config import db_path
from core.db.sqlite import Sqlite
def main() -> None:
    conn = Sqlite(path=db_path()).connect()
    try:
        bookings = conn.execute("SELECT booking_id, status FROM bookings").fetchall()
        booking_status = {r["booking_id"]: r["status"] for r in bookings}

        open_tasks = conn.execute(
            "SELECT booking_id FROM conflict_tasks WHERE status = 'Open'"
        ).fetchall()
        open_booking_ids = {r["booking_id"] for r in open_tasks}

        violations = []

        for bid in sorted(open_booking_ids):
            st = booking_status.get(bid)
            if st is None:
                violations.append({"type": "OPEN_TASK_MISSING_BOOKING", "booking_id": bid})
            elif st != "PendingResolution":
                violations.append({"type": "OPEN_TASK_REQUIRES_PENDING", "booking_id": bid, "booking_status": st})

        for bid, st in booking_status.items():
            if st == "PendingResolution" and bid not in open_booking_ids:
                violations.append({"type": "PENDING_REQUIRES_OPEN_TASK", "booking_id": bid})

        if violations:
            raise AssertionError(f"Booking/conflict consistency invariant violated: {violations}")

        print("OK booking/conflict consistency")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
