from typing import Any, Dict, Set

import httpx

from core.instance import get_blockchain


async def gossip_transaction(tx: Dict[str, Any], exclude: Set[str] = None) -> None:
    """Forward a transaction to all registered peer nodes."""
    blockchain = get_blockchain()
    exclude = exclude or set()
    async with httpx.AsyncClient(timeout=2.0) as client:
        for node in blockchain.nodes:
            if node in exclude:
                continue
            try:
                await client.post(f"{node}/transactions/receive", json=tx)
            except Exception:
                pass


async def trigger_peer_sync() -> None:
    """Ask all peers to resolve conflicts (Nakamoto consensus)."""
    blockchain = get_blockchain()
    async with httpx.AsyncClient(timeout=3.0) as client:
        for node in blockchain.nodes:
            try:
                await client.get(f"{node}/nodes/resolve")
            except Exception:
                pass