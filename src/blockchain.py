"""On-chain settlement: one ContractTool per agent, signing with its own key."""
import logging

import yaml
from eth_account import Account
from web3 import Web3

from adapters.web3 import ContractTool, load_contract
from config import (BLOCKCHAIN_CONTRACT_ADDRESS, BLOCKCHAIN_KEYS_FILE,
                    BLOCKCHAIN_RPC_URL)

log = logging.getLogger("blockchain")


def build_contract_tool(agent_id: str, expected_address: str | None = None) -> ContractTool:
    with open(BLOCKCHAIN_KEYS_FILE) as f:
        account = Account.from_key(yaml.safe_load(f)[agent_id])

    w3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_RPC_URL))
    if not w3.is_connected():
        raise ConnectionError(f"no chain reachable at {BLOCKCHAIN_RPC_URL}")
    contract = load_contract(w3, BLOCKCHAIN_CONTRACT_ADDRESS)
    return ContractTool(w3, contract, account)