import time
from typing import Any, Dict, List

from config import GENESIS_TIMESTAMP
from core.block import Block
from crypto.merkle import MerkleTree


class BlockFactory:
    """Encapsulates the complex instantiation logic for Blocks."""

    @staticmethod
    def create_block(
        index: int,
        transactions: List[Dict[str, Any]],
        previous_hash: str,
        nonce: int = 0,
    ) -> Block:
        """Create a new block with a cryptographically committed Merkle root."""
        merkle_root = MerkleTree(transactions).root
        return Block(
            index=index,
            timestamp=time.time(),
            previous_hash=previous_hash,
            merkle_root=merkle_root,
            transactions=transactions,
            nonce=nonce,
        )

    @staticmethod
    def create_genesis_block() -> Block:
        """Create the immutable genesis block."""
        return Block(
            index=0,
            timestamp=GENESIS_TIMESTAMP,
            previous_hash="0" * 64,
            merkle_root=MerkleTree([]).root,
            transactions=[],
            nonce=0,
        )