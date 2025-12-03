from typing import List, Dict, Any
from core.db.models.records import TransactionRecord


class BlockChainAdapter:
    """Stub adapter for blockchain-style backends.

    This is a lightweight skeleton: implement actual web3 calls as needed.
    """

    def __init__(self, web3_client: Any | None = None) -> None:
        self._w3 = web3_client

    def write(self, payload: Dict[str, Any], metadata: Dict[str, Any] | None = None) -> TransactionRecord:
        # TODO: construct, sign and send transaction via web3 client
        tx_hash = "0xTODO"
        return TransactionRecord(success=True, tx_hash=tx_hash, backend="blockchain", metadata=metadata)

    def confirm(self, tx_hash: str, confirmations: int = 1) -> TransactionRecord:
        # TODO: check chain for confirmations and return updated TransactionRecord
        return TransactionRecord(success=True, tx_hash=tx_hash, confirmations=confirmations, backend="blockchain")

    def read(self, query: Dict[str, Any] | None = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        # Optional: read indexed data from a chain indexer / explorer
        return []
