import asyncio
import json
import time
import httpx
import os
from typing import Dict, List, Optional, Set

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from blockchain import Blockchain, MINING_SENDER
from wallet import Wallet, verify_transaction_signature

# ─── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="NovaChain", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

blockchain = Blockchain(difficulty=3)

# Wallets stored in memory (in production, use encrypted storage)
wallets: Dict[str, Dict] = {}

# WebSocket connections
active_connections: Set[WebSocket] = set()

# ─── WebSocket Manager ────────────────────────────────────────────────────────


async def broadcast(message: Dict):
    dead = set()
    for ws in active_connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)
    active_connections.difference_update(dead)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        # Send current state on connect
        await websocket.send_json({
            "type": "init",
            "chain": [b.to_dict() for b in blockchain.chain],
            "pending": blockchain.pending_transactions,
            "valid": blockchain.is_chain_valid(),
            "difficulty": blockchain.difficulty,
            "nodes": list(blockchain.nodes),
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.discard(websocket)
    except Exception:
        active_connections.discard(websocket)


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class TransactionRequest(BaseModel):
    sender: str
    receiver: str
    amount: float
    private_key: Optional[str] = None
    signature: Optional[str] = None
    public_key: Optional[str] = None


class MineRequest(BaseModel):
    miner_address: str


class NodeRequest(BaseModel):
    nodes: List[str]


class TamperRequest(BaseModel):
    block_index: int
    field: str
    value: str


class DifficultyRequest(BaseModel):
    difficulty: int

# ─── Routes ───────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/chain")
async def get_chain():
    return blockchain.to_dict()


@app.get("/chain/valid")
async def validate_chain():
    valid = blockchain.is_chain_valid()
    return {"valid": valid, "length": len(blockchain.chain)}


@app.post("/transactions/new")
async def new_transaction(req: TransactionRequest):
    tx = {
        "sender": req.sender,
        "receiver": req.receiver,
        "amount": req.amount,
        "timestamp": time.time(),
        "signature": req.signature or "UNSIGNED",
    }

    added = blockchain.add_transaction(tx)
    if not added:
        raise HTTPException(
            status_code=400, detail="Invalid transaction (bad data or insufficient funds)")

    await broadcast({"type": "new_transaction", "transaction": tx, "pending": blockchain.pending_transactions})

    # ── GOSSIP PROTOCOL ──
    # Forward the new transaction to all registered peer nodes asynchronously
    async def gossip_tx():
        async with httpx.AsyncClient(timeout=2.0) as client:
            for node in blockchain.nodes:
                try:
                    await client.post(f"{node}/transactions/receive", json=tx)
                except Exception:
                    pass  # Ignore nodes that are offline
    asyncio.create_task(gossip_tx())

    return {"message": "Transaction added to pending pool", "transaction": tx}


@app.post("/transactions/receive")
async def receive_transaction(tx: dict):
    # This endpoint allows nodes to receive gossiped transactions from peers
    # without re-gossiping them to avoid infinite loops.
    added = blockchain.add_transaction(tx)
    if added:
        await broadcast({"type": "new_transaction", "transaction": tx, "pending": blockchain.pending_transactions})
    return {"message": "Transaction received"}


@app.post("/mine")
async def mine_block(req: MineRequest):
    if not req.miner_address:
        raise HTTPException(status_code=400, detail="Miner address required")

    if blockchain._mining:
        return {"message": "Mining already in progress"}

    # Start mining in background thread
    blockchain.start_mining_async(req.miner_address)

    # Poll until done (up to 60s)
    for _ in range(600):
        await asyncio.sleep(0.1)
        if not blockchain._mining_progress.get("active", False):
            break

    if blockchain._mining_progress.get("active", False):
        return {"message": "Mining still in progress, check /mining/status"}

    block = blockchain.chain[-1]

    await broadcast({
        "type": "new_block",
        "block": block.to_dict(),
        "chain": [b.to_dict() for b in blockchain.chain],
        "valid": blockchain.is_chain_valid(),
    })

    # ── AUTOMATIC CONSENSUS ──
    # Tell peer nodes to sync up because we just mined a new valid block
    async def trigger_peer_sync():
        async with httpx.AsyncClient(timeout=3.0) as client:
            for node in blockchain.nodes:
                try:
                    await client.get(f"{node}/nodes/resolve")
                except Exception:
                    pass
    asyncio.create_task(trigger_peer_sync())

    return {"message": "Block mined successfully", "block": block.to_dict()}


@app.get("/mining/status")
async def mining_status():
    return {
        "active": blockchain._mining_progress.get("active", False),
        "nonce": blockchain._mining_progress.get("nonce", 0),
        "hash": blockchain._mining_progress.get("hash", ""),
        "difficulty": blockchain.difficulty,
    }


@app.post("/mining/stop")
async def stop_mining():
    blockchain.stop_mining()
    return {"message": "Mining stopped"}


@app.post("/wallet/create")
async def create_wallet():
    w = Wallet()
    wallet_data = w.to_dict()
    wallets[wallet_data["address"]] = wallet_data
    return wallet_data


@app.get("/wallet/balance/{address}")
async def get_balance(address: str):
    balance = blockchain.get_balance(address)
    history = blockchain.get_transaction_history(address)
    return {"address": address, "balance": balance, "transactions": history}


@app.get("/wallet/history/{address}")
async def get_history(address: str):
    return {"address": address, "transactions": blockchain.get_transaction_history(address)}


@app.post("/nodes/register")
async def register_nodes(req: NodeRequest):
    for node in req.nodes:
        blockchain.register_node(node)
    return {"message": f"Registered {len(req.nodes)} node(s)", "nodes": list(blockchain.nodes)}


@app.get("/nodes/resolve")
async def resolve_conflicts():
    replaced = False
    current_length = len(blockchain.chain)

    for node in blockchain.nodes:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{node}/chain")
                data = resp.json()

                if data["length"] > current_length:
                    from blockchain import Block
                    new_chain = [Block.from_dict(b) for b in data["chain"]]
                    if blockchain.replace_chain(new_chain):
                        replaced = True
                        current_length = data["length"]
        except Exception:
            pass

    if replaced:
        await broadcast({"type": "chain_replaced", "chain": [b.to_dict() for b in blockchain.chain]})
        return {"message": "Chain replaced with longer valid chain", "chain_length": len(blockchain.chain)}
    return {"message": "Local chain is authoritative", "chain_length": len(blockchain.chain)}


@app.get("/nodes")
async def get_nodes():
    return {"nodes": list(blockchain.nodes)}


@app.post("/debug/tamper")
async def tamper_block(req: TamperRequest):
    if req.block_index <= 0 or req.block_index >= len(blockchain.chain):
        raise HTTPException(
            status_code=400, detail="Invalid block index (cannot tamper genesis)")

    block = blockchain.chain[req.block_index]
    if req.field == "transactions" and block.transactions:
        block.transactions[0]["amount"] = float(req.value)
    elif req.field == "nonce":
        block.nonce = int(req.value)

    await broadcast({
        "type": "tampered",
        "chain": [b.to_dict() for b in blockchain.chain],
        "valid": blockchain.is_chain_valid(),
    })
    return {
        "message": f"Block {req.block_index} tampered (chain now invalid)",
        "valid": blockchain.is_chain_valid(),
    }


@app.post("/debug/reset")
async def reset_chain():
    from blockchain import Block
    blockchain.chain = [blockchain._create_genesis_block()]
    blockchain.pending_transactions = []
    blockchain._save()
    await broadcast({
        "type": "reset",
        "chain": [b.to_dict() for b in blockchain.chain],
        "valid": True,
    })
    return {"message": "Blockchain reset to genesis"}


@app.post("/difficulty")
async def set_difficulty(req: DifficultyRequest):
    if not 1 <= req.difficulty <= 6:
        raise HTTPException(status_code=400, detail="Difficulty must be 1–6")
    blockchain.difficulty = req.difficulty
    blockchain._save()
    await broadcast({"type": "difficulty_changed", "difficulty": req.difficulty})
    return {"message": f"Difficulty set to {req.difficulty}"}


@app.get("/stats")
async def get_stats():
    total_tx = sum(len(b.transactions) for b in blockchain.chain)
    total_mined = sum(1 for b in blockchain.chain[1:])
    return {
        "blocks": len(blockchain.chain),
        "total_transactions": total_tx,
        "pending_transactions": len(blockchain.pending_transactions),
        "difficulty": blockchain.difficulty,
        "nodes": len(blockchain.nodes),
        "valid": blockchain.is_chain_valid(),
        "mined_blocks": total_mined,
    }


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
