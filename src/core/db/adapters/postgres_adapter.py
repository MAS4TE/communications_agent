from typing import List, Dict, Any
from core.db.models.records import Record


class PostgresAdapter:
    """Skeleton Postgres adapter. Replace TODOs with actual DB code (psycopg2/asyncpg/SQLAlchemy)."""

    def __init__(self, engine_or_conn: Any | None = None) -> None:
        self._engine = engine_or_conn

    def write(self, payload: Dict[str, Any], metadata: Dict[str, Any] | None = None) -> Record:
        # TODO: execute INSERT ... RETURNING id against Postgres and return Record
        return Record(success=True, id="TODO", backend="postgres", metadata=metadata)

    def read(self, query: Dict[str, Any] | None = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        # TODO: run SELECT with filters/pagination
        return []
