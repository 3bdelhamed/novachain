import hashlib
import json
from typing import Any, Dict, List, Optional


class Block:
    """A single unit of the blockchain.

    The block hash is computed over the HEADER ONLY (index, timestamp,
    previous_hash, merkle_root, nonce). The full transaction list is committed
    to via the merkle_root, keeping headers small and validation fast.
    """

    def __init__(
        self,
        index: int,
        timestamp: float,
        previous_hash: str,
        merkle_root: str,
        transactions: Optional[List[Dict[str, Any]]] = None,
        nonce: int = 0,
        hash: Optional[str] = None,
    ) -> None:
        self.index: int = index
        self.timestamp: float = timestamp
        self.previous_hash: str = previous_hash
        self.merkle_root: str = merkle_root
        self.transactions: List[Dict[str, Any]] = transactions or []
        self.nonce: int = nonce
        self.hash: str = hash or self.calculate_hash()

    def calculate_hash(self) -> str:
        """Compute SHA-256 over the block header only."""
        header = {
            "index": self.index,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
        }
        header_string = json.dumps(header, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(header_string.encode()).hexdigest()

    def mine_block(self, difficulty: int) -> None:
        """Proof-of-Work: increment nonce until hash meets difficulty target."""
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses and database storage."""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Block":
        """Deserialize from storage without recalculating the hash."""
        return cls(
            index=data["index"],
            timestamp=data["timestamp"],
            previous_hash=data["previous_hash"],
            merkle_root=data.get("merkle_root", ""),
            transactions=data.get("transactions", []),
            nonce=data["nonce"],
            hash=data["hash"],
        )