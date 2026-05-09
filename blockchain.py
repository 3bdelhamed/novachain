import hashlib
import json
import time
import threading
import os
from typing import List, Optional, Dict, Any

# ─── Block ────────────────────────────────────────────────────────────────────


class Block:
    def __init__(
        self,
        index: int,
        transactions: List[Dict],
        previous_hash: str,
        nonce: int = 0,
        timestamp: Optional[float] = None,
    ):
        self.index = index
        self.timestamp = timestamp or time.time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:
        block_string = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                "transactions": self.transactions,
                "previous_hash": self.previous_hash,
                "nonce": self.nonce,
            },
            sort_keys=True,
        )
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine_block(self, difficulty: int) -> None:
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Block":
        block = cls(
            index=data["index"],
            transactions=data["transactions"],
            previous_hash=data["previous_hash"],
            nonce=data["nonce"],
            timestamp=data["timestamp"],
        )
        block.hash = data["hash"]
        return block


# ─── Blockchain ───────────────────────────────────────────────────────────────

MINING_REWARD = 10
MINING_SENDER = "BLOCKCHAIN_REWARD"

# DYNAMIC DATA FILE FIX: Assign file based on the port being used
PORT = os.environ.get("PORT", "8000")
DATA_FILE = f"blockchain_data_{PORT}.json"


class Blockchain:
    def __init__(self, difficulty: int = 3):
        self.difficulty = difficulty
        self.pending_transactions: List[Dict] = []
        self.nodes: set = set()
        self._mining = False
        self._mining_thread: Optional[threading.Thread] = None
        self._mining_progress: Dict[str, Any] = {
            "active": False, "nonce": 0, "hash": ""}
        self._lock = threading.Lock()

        loaded = self._load()
        if not loaded:
            self.chain: List[Block] = [self._create_genesis_block()]
            self._save()

    # ── Genesis ──────────────────────────────────────────────────────────────

    def _create_genesis_block(self) -> Block:
        genesis = Block(
            index=0,
            transactions=[],
            previous_hash="0" * 64,
            nonce=0,
            timestamp=1_700_000_000.0,
        )
        genesis.hash = genesis.calculate_hash()
        return genesis

    # ── Chain Operations ─────────────────────────────────────────────────────

    def add_block(self, block: Block) -> bool:
        if block.previous_hash != self.chain[-1].hash:
            return False
        if not block.hash.startswith("0" * self.difficulty):
            return False
        if block.hash != block.calculate_hash():
            return False
        self.chain.append(block)
        self._save()
        return True

    def add_transaction(self, transaction: Dict) -> bool:
        required = {"sender", "receiver", "amount"}
        if not required.issubset(transaction):
            return False
        if transaction["amount"] <= 0:
            return False

        # Prevent adding duplicates to pending
        if transaction in self.pending_transactions:
            return True

        if transaction["sender"] != MINING_SENDER:
            bal = self.get_balance(transaction["sender"])
            if bal < transaction["amount"]:
                return False
        self.pending_transactions.append(transaction)
        self._save()  # Save state when pending changes
        return True

    def is_chain_valid(self, chain: Optional[List[Block]] = None) -> bool:
        chain = chain or self.chain
        for i in range(1, len(chain)):
            current = chain[i]
            previous = chain[i - 1]
            if current.hash != current.calculate_hash():
                return False
            if current.previous_hash != previous.hash:
                return False
            if not current.hash.startswith("0" * self.difficulty):
                return False
        return True

    # ── Mining ───────────────────────────────────────────────────────────────

    def mine_pending_transactions(self, miner_address: str) -> Optional[Block]:
        reward_tx = {
            "sender": MINING_SENDER,
            "receiver": miner_address,
            "amount": MINING_REWARD,
            "timestamp": time.time(),
            "signature": "REWARD",
        }
        txs = list(self.pending_transactions) + [reward_tx]

        block = Block(
            index=len(self.chain),
            transactions=txs,
            previous_hash=self.chain[-1].hash,
        )

        self._mining_progress = {"active": True, "nonce": 0, "hash": ""}
        self._mining = True

        while self._mining:
            block.nonce += 1
            block.hash = block.calculate_hash()
            self._mining_progress["nonce"] = block.nonce
            self._mining_progress["hash"] = block.hash
            if block.hash.startswith("0" * self.difficulty):
                break

        if not self._mining:
            self._mining_progress = {"active": False, "nonce": 0, "hash": ""}
            return None

        self._mining = False
        self._mining_progress["active"] = False

        with self._lock:
            self.chain.append(block)
            self.pending_transactions = []
            self._save()

        return block

    def start_mining_async(self, miner_address: str):
        if self._mining:
            return False
        self._mining_thread = threading.Thread(
            target=self.mine_pending_transactions, args=(
                miner_address,), daemon=True
        )
        self._mining_thread.start()
        return True

    def stop_mining(self):
        self._mining = False

    # ── Balance ──────────────────────────────────────────────────────────────

    def get_balance(self, address: str) -> float:
        balance = 0.0
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("receiver") == address:
                    balance += tx["amount"]
                if tx.get("sender") == address:
                    balance -= tx["amount"]
        # pending outgoing
        for tx in self.pending_transactions:
            if tx.get("sender") == address:
                balance -= tx["amount"]
        return balance

    def get_transaction_history(self, address: str) -> List[Dict]:
        history = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("sender") == address or tx.get("receiver") == address:
                    history.append(
                        {**tx, "block_index": block.index, "confirmed": True})
        for tx in self.pending_transactions:
            if tx.get("sender") == address or tx.get("receiver") == address:
                history.append({**tx, "block_index": None, "confirmed": False})
        return sorted(history, key=lambda x: x.get("timestamp", 0), reverse=True)

    # ── Nodes / Consensus ────────────────────────────────────────────────────

    def register_node(self, address: str):
        self.nodes.add(address.rstrip("/"))
        self._save()

    def replace_chain(self, new_chain: List[Block]) -> bool:
        if len(new_chain) > len(self.chain) and self.is_chain_valid(new_chain):
            self.chain = new_chain
            # Optional: purge pending transactions that are now in the new chain
            self._save()
            return True
        return False

    # ── Persistence ──────────────────────────────────────────────────────────

    def _save(self):
        data = {
            "chain": [b.to_dict() for b in self.chain],
            "pending_transactions": self.pending_transactions,
            "nodes": list(self.nodes),
            "difficulty": self.difficulty,
        }
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _load(self) -> bool:
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            self.chain = [Block.from_dict(b) for b in data["chain"]]
            self.pending_transactions = data.get("pending_transactions", [])
            self.nodes = set(data.get("nodes", []))
            self.difficulty = data.get("difficulty", self.difficulty)
            return True
        except Exception:
            return False

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain": [b.to_dict() for b in self.chain],
            "length": len(self.chain),
            "pending_transactions": self.pending_transactions,
            "nodes": list(self.nodes),
            "difficulty": self.difficulty,
            "valid": self.is_chain_valid(),
        }
