from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, List


@dataclass(frozen=True)
class QueryResult:
    rows: List[Mapping[str, Any]]


_ALLOWED_QUERIES = {
    "list_properties",
    "list_bookings",
    "list_users",
}


class QueryAPI:
    def __init__(self, *, db: Any) -> None:
        self._db = db

    def fetch(
        self,
        query_name: str,
        params: Optional[Mapping[str, Any]] = None,
    ) -> QueryResult:

        if query_name not in _ALLOWED_QUERIES:
            raise ValueError(f"Query '{query_name}' is not allowed.")

        rows = self._db.fetch_projection(
            query_name=query_name,
            params=params or {},
        )

        return QueryResult(rows=rows)
