from typing import List, Dict, Any
from core.db.models.records import Record


class InMemoryAdapter:
    """A tiny in-memory adapter useful for tests and development."""

    def __init__(self) -> None:
        self._store: List[Dict[str, Any]] = []
        self._next_id = 1

    def write(self, payload: Dict[str, Any], metadata: Dict[str, Any] | None = None) -> Record:
        rec = dict(payload)
        rec_id = str(self._next_id)
        rec["_id"] = rec_id
        self._next_id += 1
        self._store.append(rec)
        return Record(success=True, id=rec_id, backend="inmemory", metadata=metadata)

    def read(self, query: Dict[str, Any] | None = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        # naive implementation: ignore query and return slice
        return list(self._store)[offset: offset + limit]
