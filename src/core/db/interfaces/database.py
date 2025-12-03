"""Protocol interfaces for storage behaviors."""
from typing import Protocol, List, Dict, Any, runtime_checkable
from core.db.models.records import Record, TransactionRecord


@runtime_checkable
class Reader(Protocol):
    def read(self, query: Dict[str, Any] | None = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        ...


@runtime_checkable
class Writer(Protocol):
    def write(self, payload: Dict[str, Any], metadata: Dict[str, Any] | None = None) -> Record:
        ...


@runtime_checkable
class Confirmable(Protocol):
    def confirm(self, tx_hash: str, confirmations: int = 1) -> TransactionRecord:
        ...


@runtime_checkable
class DatabaseIO(Reader, Writer, Protocol):
    """Composite protocol for adapters that support both read and write."""
    ...
