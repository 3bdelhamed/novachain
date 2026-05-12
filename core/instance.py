import threading
from typing import Optional

from core.blockchain import Blockchain
from storage.base import BlockchainStorage

_blockchain_instance: Optional[Blockchain] = None
_instance_lock = threading.Lock()


def get_blockchain(storage: Optional[BlockchainStorage] = None) -> Blockchain:
    """Return the singleton Blockchain instance.

    Args:
        storage: Required on FIRST call only.

    Raises:
        ValueError: If called for the first time without a storage argument.
    """
    global _blockchain_instance
    if _blockchain_instance is None:
        with _instance_lock:
            if _blockchain_instance is None:
                if storage is None:
                    raise ValueError("Blockchain storage must be provided on first initialization.")
                _blockchain_instance = Blockchain(storage)
    return _blockchain_instance