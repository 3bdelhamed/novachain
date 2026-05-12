import hashlib
import json
from typing import Any, Dict, List


class MerkleTree:
    def __init__(self, transactions: List[Dict[str, Any]]) -> None:
        self.leaves: List[str] = [self._hash_transaction(tx) for tx in transactions]
        self.root: str = self._build_tree(self.leaves) if self.leaves else self._empty_hash()

    @staticmethod
    def _hash_transaction(tx: Dict[str, Any]) -> str:
        payload = json.dumps(tx, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _hash_pair(left: str, right: str) -> str:
        combined = (left + right).encode()
        return hashlib.sha256(combined).hexdigest()

    @staticmethod
    def _empty_hash() -> str:
        return hashlib.sha256(b"").hexdigest()

    def _build_tree(self, leaves: List[str]) -> str:
        if len(leaves) == 1:
            return leaves[0]
        if len(leaves) % 2 == 1:
            leaves.append(leaves[-1])
        next_level: List[str] = []
        for i in range(0, len(leaves), 2):
            next_level.append(self._hash_pair(leaves[i], leaves[i + 1]))
        return self._build_tree(next_level)