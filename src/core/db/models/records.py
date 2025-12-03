from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class Record:
    """Generic persisted record returned by writers."""
    success: bool
    id: Optional[str] = None
    backend: Optional[str] = None
    message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TransactionRecord(Record):
    tx_hash: Optional[str] = None
    confirmations: Optional[int] = None
    block_number: Optional[int] = None


@dataclass
class BidRecord(Record):
    bid_id: Optional[str] = None
    amount: Optional[float] = None
    bidder: Optional[str] = None
