from typing import Any, Dict, List
from core.db.sqlite import Sqlite


class SqliteAdapter:
    """
    Adapter layer between CoreAPI QueryAPI and Sqlite DB implementation.
    """

    def __init__(self, sqlite: Sqlite) -> None:
        self._sqlite = sqlite

    # pass-through for ingest
    def append_event(self, *, envelope, idempotency_key=None):
        return self._sqlite.append_event(
            envelope=envelope,
            idempotency_key=idempotency_key,
        )

    # projection reader aligned with existing tables
    def fetch_projection(self, *, query_name: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        conn = self._sqlite.connect()
        try:
            cursor = conn.cursor()

            if query_name == "list_properties":
                cursor.execute("SELECT * FROM properties")

            elif query_name == "list_bookings":
                cursor.execute("SELECT * FROM bookings")

            elif query_name == "list_users":
                cursor.execute("SELECT * FROM users")

            else:
                raise ValueError("Unknown projection")

            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

            return [dict(zip(columns, row)) for row in rows]

        finally:
            conn.close()
