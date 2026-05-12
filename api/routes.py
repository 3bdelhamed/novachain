from pydantic import BaseModel
import asyncio
import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import HTMLResponse
import httpx
import asyncio
from api.models import (
    DifficultyRequest,
    MineRequest,
    NodeRequest,
    TamperRequest,
    TransactionRequest,
)
from core.block import Block
from core.instance import get_blockchain
from crypto.wallet import Wallet
from network.p2p import gossip_transaction, trigger_peer_sync
from network.websocket import ws_manager

router = APIRouter()
# --- Pydantic Models ---


class ImportWalletRequest(BaseModel):
    private_key: str


class TransactionRequest(BaseModel):
    sender: str
    receiver: str
    amount: float
    signature: str = "UNSIGNED"
    public_key: str = ""


# @router.get("/", response_class=HTMLResponse)
# async def index():
#     with open("templates/index.html", "r", encoding="utf-8") as f:
#         return HTMLResponse(f.read())


@router.get("/chain")
async def get_chain():
    return get_blockchain().to_dict()


@router.get("/chain/valid")
async def validate_chain():
    bc = get_blockchain()
    return {"valid": bc.is_chain_valid(), "length": len(bc.chain)}


@router.post("/transactions/new")
async def new_transaction(req: TransactionRequest):
    from core.instance import get_blockchain
    from network.websocket import ws_manager
    bc = get_blockchain()

    tx = req.dict()
    import time
    tx["timestamp"] = time.time()

    if bc.add_transaction(tx):
        # Broadcast to UI
        await ws_manager.broadcast({
            "type": "new_transaction",
            "transaction": tx,
            "pending": bc.pending_transactions
        })
        return {"message": "Transaction added successfully"}

    raise HTTPException(
        status_code=400, detail="Invalid transaction or insufficient funds")


@router.post("/transactions/receive")
async def receive_transaction(tx: Dict[str, Any]):
    bc = get_blockchain()
    added = bc.add_transaction(tx)
    if added:
        await ws_manager.broadcast({"type": "new_transaction", "transaction": tx, "pending": bc.pending_transactions})
    return {"message": "Transaction received"}


async def notify_network_to_sync(nodes: set):
    """Background task to tell all peers a new block was mined."""
    async with httpx.AsyncClient(timeout=3.0) as client:
        for node in nodes:
            try:
                await client.get(f"{node}/nodes/resolve")
            except Exception:
                pass
# --------------------------------------------------------


@router.post("/mine")
async def mine_block(req: dict, background_tasks: BackgroundTasks):
    from core.instance import get_blockchain
    bc = get_blockchain()

    miner_address = req.get("miner_address")
    if not miner_address:
        return {"error": "Miner address required"}

    # Run the mining logic
    block = bc.mine_pending_transactions(miner_address)

    if block:
        # -- 1. UPDATE LOCAL UI (The Fix) --
        # Fetch only the last 100 blocks to prevent OOM crashes on huge chains
        current_length = bc.storage.get_chain_length()
        recent_blocks = bc.storage.get_blocks_batch(
            max(0, current_length - 100), 100)

        await ws_manager.broadcast({
            "type": "new_block",
            "block": block.to_dict(),
            "chain": [b.to_dict() for b in recent_blocks],
            "valid": True
        })

        background_tasks.add_task(notify_network_to_sync, bc.nodes)

        return {"message": "Block mined successfully", "block": block.to_dict()}

    return {"error": "Mining failed"}


@router.get("/mining/status")
async def mining_status():
    bc = get_blockchain()
    return {
        "active": bc._mining_progress.get("active", False),
        "nonce": bc._mining_progress.get("nonce", 0),
        "hash": bc._mining_progress.get("hash", ""),
        "difficulty": bc.difficulty,
    }


@router.post("/mining/stop")
async def stop_mining():
    get_blockchain().stop_mining()
    return {"message": "Mining stopped"}


@router.post("/wallet/create")
async def create_wallet():
    """Generates a brand new ECDSA Wallet."""
    from crypto.wallet import Wallet  # Adjust import path based on your folder structure
    w = Wallet()
    return w.to_dict()


@router.post("/wallet/import")
async def import_wallet(req: ImportWalletRequest):
    """Derives the Public Key and Address from an existing Private Key."""
    from crypto.wallet import create_wallet_from_private_key
    
    # Use the standalone function you already wrote instead of the Wallet class
    wallet_dict = create_wallet_from_private_key(req.private_key)
    
    if not wallet_dict:
        raise HTTPException(
            status_code=400, detail="Invalid Private Key format")
            
    return wallet_dict


@router.get("/wallet/balance/{address}")
async def get_balance(address: str):
    """Queries the blockchain for the user's balance."""
    from core.instance import get_blockchain
    bc = get_blockchain()
    balance = bc.get_balance(address)
    return {"address": address, "balance": balance}


@router.get("/wallet/history/{address}")
async def get_history(address: str):
    return {"address": address, "transactions": get_blockchain().get_transaction_history(address)}


@router.post("/nodes/register")
async def register_nodes(req: NodeRequest):
    bc = get_blockchain()
    for node in req.nodes:
        bc.register_node(node)

    # -- NEW: Tell the UI to update the network tab instantly! --
    await ws_manager.broadcast({
        "type": "nodes_updated",
        "nodes": list(bc.nodes)
    })
    # -----------------------------------------------------------

    return {"message": f"Registered {len(req.nodes)} node(s)", "nodes": list(bc.nodes)}


@router.get("/blocks")
async def get_blocks_batch(offset: int = 0, limit: int = 50):
    """Serve blocks in small batches to prevent OOM crashes on peers."""
    bc = get_blockchain()
    blocks = bc.storage.get_blocks_batch(offset, limit)
    return {"blocks": [b.to_dict() for b in blocks]}


@router.get("/nodes/resolve")
async def resolve_conflicts():
    import httpx
    from core.block import Block
    from core.instance import get_blockchain
    from network.websocket import ws_manager
    
    bc = get_blockchain()
    current_length = bc.storage.get_chain_length()
    
    # 1. NEW: Check if our own local chain is corrupted
    is_local_valid = bc.is_chain_valid()

    best_peer = None
    
    # 2. FIX: If our chain is invalid, we will accept ANY valid remote chain 
    # that is longer than the genesis block, ignoring our own corrupted length.
    max_length = current_length if is_local_valid else 1

    # Ask peers for their chain length
    for node in bc.nodes:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{node}/chain/valid")
                data = resp.json()
                if data.get("valid") and data.get("length") > max_length:
                    max_length = data["length"]
                    best_peer = node
        except Exception:
            pass
    # 2. Safely fetch and validate before wiping local data
    if best_peer:
        new_chain_dicts = []
        offset = 0
        batch_size = 50

        # Fetch the longer chain from the peer
        async with httpx.AsyncClient(timeout=10.0) as client:
            while offset < max_length:
                resp = await client.get(f"{best_peer}/blocks?offset={offset}&limit={batch_size}")
                batch_data = resp.json().get("blocks", [])
                if not batch_data:
                    break
                new_chain_dicts.extend(batch_data)
                offset += batch_size

        # Convert dictionaries back to Block objects
        new_chain = [Block.from_dict(b) for b in new_chain_dicts]

        # Use replace_chain to validate against local difficulty BEFORE touching SQLite
        if bc.replace_chain(new_chain):
            recent_blocks = bc.storage.get_blocks_batch(max(0, max_length - 100), 100)
            await ws_manager.broadcast({
                "type": "chain_replaced",
                "chain": [b.to_dict() for b in recent_blocks]
            })
            return {"message": f"Chain synchronized safely. Total length: {max_length}"}
        else:
            return {"message": "Sync failed: Remote chain violates local consensus rules (check difficulty)."}

    return {"message": "Local chain is authoritative", "chain_length": current_length}

@router.post("/debug/reset")
async def reset_chain():
    bc = get_blockchain()
    bc.reset_to_genesis()
    await ws_manager.broadcast({
        "type": "reset",
        "chain": [b.to_dict() for b in bc.chain],
        "valid": True,
    })
    return {"message": "Blockchain reset to genesis"}


@router.post("/difficulty")
async def set_difficulty(req: DifficultyRequest):
    if not 1 <= req.difficulty <= 6:
        raise HTTPException(status_code=400, detail="Difficulty must be 1–6")
    bc = get_blockchain()
    bc.storage.save_difficulty(req.difficulty)
    await ws_manager.broadcast({"type": "difficulty_changed", "difficulty": req.difficulty})
    return {"message": f"Difficulty set to {req.difficulty}"}


@router.get("/stats")
async def get_stats():
    bc = get_blockchain()
    total_tx = sum(len(b.transactions) for b in bc.chain)
    total_mined = sum(1 for b in bc.chain[1:])
    return {
        "blocks": len(bc.chain),
        "total_transactions": total_tx,
        "pending_transactions": len(bc.pending_transactions),
        "difficulty": bc.difficulty,
        "nodes": len(bc.nodes),
        "valid": bc.is_chain_valid(),
        "mined_blocks": total_mined,
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    bc = get_blockchain()
    try:
        await websocket.send_json({
            "type": "init",
            "chain": [b.to_dict() for b in bc.chain],
            "pending": bc.pending_transactions,
            "valid": bc.is_chain_valid(),
            "difficulty": bc.difficulty,
            "nodes": list(bc.nodes),
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@router.get("/nodes")
async def get_nodes():
    """Returns the list of all known peer nodes."""
    from core.instance import get_blockchain
    bc = get_blockchain()
    return {"nodes": list(bc.nodes)}
