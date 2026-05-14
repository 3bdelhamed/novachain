"""
api/demo_routes.py
═══════════════════════════════════════════════════════════════════════════════
DEMO ONLY — Session-isolated endpoints. NEVER touches SQLite.
═══════════════════════════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from core.demo_chain import (
    create_demo_session,
    get_demo_session,
    get_demo_blockchain,
    DEMO_SESSIONS,
    cleanup_old_sessions,
)
from core.instance import get_blockchain

router = APIRouter(prefix="/demo", tags=["demo"])


# ── Models ───────────────────────────────────────────────────────────────────

class TamperRequest(BaseModel):
    amount: Optional[float] = None
    receiver: Optional[str] = None


class MineRequest(BaseModel):
    miner_address: str = "DEMO_MINER"


class TxRequest(BaseModel):
    sender: str = "Alice"
    receiver: str = "Bob"
    amount: float = 10.0


class ForkResolveRequest(BaseModel):
    fork_id: str


# ── Session Lifecycle ────────────────────────────────────────────────────────

@router.post("/session/create")
async def demo_session_create():
    """Spawn a fresh sandbox cloned from the real blockchain."""
    real = get_blockchain()
    cleanup_old_sessions()
    sid = create_demo_session(real.chain, real.difficulty)
    session = get_demo_session(sid)
    return {
        "session_id": sid,
        "chain_length": session.length,   # ← now works: DemoSession.length property
        "difficulty": session.difficulty,
        "message": "Demo session created. Isolated from real network.",
    }


@router.get("/session/{session_id}")
async def demo_session_get(session_id: str):
    """Inspect a demo session's current state."""
    try:
        demo = get_demo_blockchain(session_id)
        return demo.to_dict()
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")


# ── Transactions ─────────────────────────────────────────────────────────────

@router.post("/session/{session_id}/transaction")
async def demo_add_transaction(session_id: str, req: TxRequest):
    demo = get_demo_blockchain(session_id)
    tx = demo.add_demo_transaction(req.sender, req.receiver, req.amount)
    return {"transaction": tx, "pending_count": len(demo.pending)}


# ── Mining ───────────────────────────────────────────────────────────────────

@router.post("/session/{session_id}/mine")
async def demo_mine(session_id: str, req: MineRequest, background_tasks: BackgroundTasks):
    demo = get_demo_blockchain(session_id)
    demo.start_mining()

    if not demo.pending:
        demo.auto_fill_mempool(2)

    block = demo.mine_next_block(req.miner_address)

    if block:
        return {
            "message": "Block mined",
            "block": block.to_dict(),
            "chain_length": demo.length,
            "mining_state": demo.get_mining_state(),
        }
    return {"message": "Mining aborted", "mining_state": demo.get_mining_state()}


@router.get("/session/{session_id}/mining/status")
async def demo_mining_status(session_id: str):
    demo = get_demo_blockchain(session_id)
    return demo.get_mining_state()


@router.post("/session/{session_id}/mining/stop")
async def demo_mining_stop(session_id: str):
    demo = get_demo_blockchain(session_id)
    demo.stop_mining()
    return {"message": "Mining stopped"}


# ── Tampering ────────────────────────────────────────────────────────────────

@router.post("/session/{session_id}/tamper")
async def demo_tamper(session_id: str, index: int, req: TamperRequest):
    demo = get_demo_blockchain(session_id)
    try:
        result = demo.tamper_block(index, req.amount, req.receiver)
        return {
            "message": f"Block #{index} tampered",
            **result,
            "chain_valid": False,
            "visual_effect": "corruption_propagated",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Validation ───────────────────────────────────────────────────────────────

@router.get("/session/{session_id}/validate")
async def demo_validate(session_id: str):
    demo = get_demo_blockchain(session_id)
    return demo.validate_step_by_step()


# ── Re-mine / Auto Fix ───────────────────────────────────────────────────────

@router.post("/session/{session_id}/remine")
async def demo_remine(session_id: str):
    demo = get_demo_blockchain(session_id)

    start_index = None
    validation = demo.validate_step_by_step()
    for step in validation["steps"]:
        if step["status"] == "invalid":
            start_index = step["index"]
            break

    if start_index is None:
        return {"message": "Chain is already valid", "remined_from": None}

    results = demo.remine_from(start_index)

    return {
        "message": f"Re-mined {len(results)} block(s)",
        "remined_from": start_index,
        "results": results,
        "chain_valid": demo.validate_step_by_step()["valid"],
    }


# ── Fork / Consensus Demo ────────────────────────────────────────────────────

@router.post("/session/{session_id}/fork")
async def demo_create_fork(session_id: str, fork_point: int, extra_blocks: int = 2):
    demo = get_demo_blockchain(session_id)
    fork_id = demo.simulate_fork(fork_point, extra_blocks)
    return {
        "fork_id": fork_id,
        "fork_point": fork_point,
        "main_length": demo.length,
        "fork_preview": [b.to_dict() for b in demo.fork_chains[fork_id][fork_point + 1:]],
    }


@router.post("/session/{session_id}/fork/resolve")
async def demo_resolve_fork(session_id: str, req: ForkResolveRequest):
    demo = get_demo_blockchain(session_id)
    try:
        result = demo.resolve_fork(req.fork_id)
        return {
            **result,
            "final_chain": [b.to_dict() for b in demo.chain],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Reset ────────────────────────────────────────────────────────────────────

@router.post("/session/{session_id}/reset")
async def demo_reset(session_id: str):
    """Clone fresh from real chain again."""
    real = get_blockchain()
    demo = get_demo_blockchain(session_id)
    demo.clone_from_real(real.chain, real.difficulty)
    return {"message": "Demo reset to real chain state", "chain_length": demo.length}