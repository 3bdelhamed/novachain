import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from core.block import Block


class BlockchainStorage(ABC):
    """Abstract interface for all blockchain persistence backends."""

    @abstractmethod
    def save_block(self, block: Block) -> None:
        ...

    @abstractmethod
    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        ...

    @abstractmethod
    def get_block_by_index(self, index: int) -> Optional[Block]:
        ...

    @abstractmethod
    def get_latest_block(self) -> Optional[Block]:
        ...

    @abstractmethod
    def set_latest_hash(self, block_hash: str) -> None:
        ...

    @abstractmethod
    def get_latest_hash(self) -> Optional[str]:
        ...

    @abstractmethod
    def get_chain_length(self) -> int:
        ...

    @abstractmethod
    def get_all_blocks(self) -> List[Block]:
        ...

    @abstractmethod
    def clear_blocks(self) -> None:
        ...

    @abstractmethod
    def save_pending_transactions(self, transactions: List[Dict[str, Any]]) -> None:
        ...

    @abstractmethod
    def get_pending_transactions(self) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def save_nodes(self, nodes: List[str]) -> None:
        ...

    @abstractmethod
    def get_nodes(self) -> List[str]:
        ...

    @abstractmethod
    def save_difficulty(self, difficulty: int) -> None:
        ...

    @abstractmethod
    def get_difficulty(self) -> int:
        ...

    @abstractmethod
    def close(self) -> None:
        ...

    @abstractmethod
    def get_blocks_batch(self, offset: int, limit: int) -> List[Block]:
        ...
