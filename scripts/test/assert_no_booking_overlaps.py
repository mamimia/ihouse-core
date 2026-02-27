import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import sqlite3
from core.db.config import db_path
from core.db.sqlite import Sqlite
def overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)

def main() -> None:
    conn = Sqlite(path=db_path()).connect()
    try:
        rows = conn.execute(
            """
            SELECT booking_id, property_id, start_date, end_date, status
            FROM bookings
            WHERE status NOT IN ('CANCELLED')
            ORDER BY property_id ASC, start_date ASC, end_date ASC, booking_id ASC
            """
        ).fetchall()

        by_property = {}
        for r in rows:
            by_property.setdefault(r["property_id"], []).append(r)

        violations = []
        for property_id, items in by_property.items():
            for i in range(len(items)):
                a = items[i]
                for j in range(i + 1, len(items)):
                    b = items[j]
                    if b["start_date"] >= a["end_date"]:
                        break
                    if overlaps(a["start_date"], a["end_date"], b["start_date"], b["end_date"]):
                        violations.append({
                            "property_id": property_id,
                            "a_booking_id": a["booking_id"],
                            "a_range": [a["start_date"], a["end_date"]],
                            "b_booking_id": b["booking_id"],
                            "b_range": [b["start_date"], b["end_date"]],
                        })

        if violations:
            raise AssertionError(f"Booking overlap invariant violated: {violations}")

        print("OK no booking overlaps at property level")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
