"""
core/demo_chain.py
═══════════════════════════════════════════════════════════════════════════════
ISOLATED DEMO SANDBOX — NEVER touches SQLite. NEVER broadcasts to real peers.
═══════════════════════════════════════════════════════════════════════════════
"""

from typing import Dict
import json
import time
import copy
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from config import MINING_REWARD, MINING_SENDER, DEFAULT_DIFFICULTY
from core.block import Block
from core.factory import BlockFactory
from crypto.merkle import MerkleTree


@dataclass
class DemoSession:
    """Container for one browser tab's isolated playground state."""
    session_id: str
    chain: List[Block] = field(default_factory=list)
    pending: List[Dict[str, Any]] = field(default_factory=list)
    difficulty: int = DEFAULT_DIFFICULTY
    mining_active: bool = False
    mining_nonce: int = 0
    mining_hash: str = ""
    mining_attempts: int = 0
    created_at: float = field(default_factory=time.time)
    fork_chains: Dict[str, List[Block]] = field(default_factory=dict)

    @property
    def length(self) -> int:
        return len(self.chain)


class DemoBlockchain:
    """
    Standalone educational blockchain. No persistence. No P2P.
    Initialized by cloning the REAL chain, then mutated freely.
    """

    def __init__(self, real_chain: List[Block], real_difficulty: int = DEFAULT_DIFFICULTY):
        self.chain: List[Block] = [
            Block.from_dict(b.to_dict()) for b in real_chain]
        self.pending: List[Dict[str, Any]] = []
        self.difficulty: int = real_difficulty
        self._mining_active: bool = False
        self._mining_nonce: int = 0
        self._mining_hash: str = ""
        self._mining_attempts: int = 0

    @property
    def length(self) -> int:
        return len(self.chain)

    def latest_block(self) -> Optional[Block]:
        return self.chain[-1] if self.chain else None

    def clone_from_real(self, real_chain: List[Block], real_difficulty: int):
        """Reset to a fresh copy of the real blockchain."""
        self.chain = [Block.from_dict(b.to_dict()) for b in real_chain]
        self.difficulty = real_difficulty
        self.pending = []
        self._reset_mining()

    def add_demo_transaction(self, sender: str, receiver: str, amount: float) -> Dict[str, Any]:
        tx = {
            "sender": sender,
            "receiver": receiver,
            "amount": amount,
            "timestamp": time.time(),
            "signature": "DEMO_UNSIGNED",
        }
        self.pending.append(tx)
        return tx

    def auto_fill_mempool(self, count: int = 3) -> List[Dict[str, Any]]:
        txs = []
        for i in range(count):
            tx = self.add_demo_transaction(
                sender=f"DEMO_SENDER_{i}",
                receiver=f"DEMO_RECEIVER_{i}",
                amount=round(10.0 + i * 5.5, 2),
            )
            txs.append(tx)
        return txs

    def mine_next_block(self, miner_address: str) -> Optional[Block]:
        if not self.chain:
            return None

        reward_tx = {
            "sender": MINING_SENDER,
            "receiver": miner_address,
            "amount": MINING_REWARD,
            "timestamp": time.time(),
            "signature": "REWARD",
        }
        txs = list(self.pending) + [reward_tx]

        block = BlockFactory.create_block(
            index=self.length,
            transactions=txs,
            previous_hash=self.latest_block().hash,
        )

        target = "0" * self.difficulty
        while self._mining_active and not block.hash.startswith(target):
            block.nonce += 1
            block.hash = block.calculate_hash()
            self._mining_nonce = block.nonce
            self._mining_hash = block.hash
            self._mining_attempts += 1

        if not self._mining_active:
            return None

        self.chain.append(block)
        self.pending = []
        self._reset_mining()
        return block

    def start_mining(self):
        self._mining_active = True
        self._mining_nonce = 0
        self._mining_hash = ""
        self._mining_attempts = 0

    def stop_mining(self):
        self._mining_active = False

    def get_mining_state(self) -> Dict[str, Any]:
        return {
            "active": self._mining_active,
            "nonce": self._mining_nonce,
            "hash": self._mining_hash,
            "attempts": self._mining_attempts,
            "difficulty": self.difficulty,
            "target_prefix": "0" * self.difficulty,
        }

    def _reset_mining(self):
        self._mining_active = False
        self._mining_nonce = 0
        self._mining_hash = ""
        self._mining_attempts = 0

    def tamper_block(self, index: int, amount: Optional[float] = None,
                     receiver: Optional[str] = None) -> Dict[str, Any]:
        if index <= 0 or index >= len(self.chain):
            raise ValueError("Cannot tamper genesis or non-existent block")

        block = self.chain[index]
        old_hash = block.hash
        old_txs = copy.deepcopy(block.transactions)

        if not block.transactions:
            raise ValueError("Block has no transactions to tamper")

        if amount is not None:
            block.transactions[0]["amount"] = amount
        if receiver is not None:
            block.transactions[0]["receiver"] = receiver

        block.merkle_root = MerkleTree(block.transactions).root
        block.hash = block.calculate_hash()

        return {
            "index": index,
            "old_hash": old_hash,
            "new_hash": block.hash,
            "old_transactions": old_txs,
            "new_transactions": block.transactions,
        }

    def validate_step_by_step(self) -> Dict[str, Any]:
        from core.consensus import ConsensusEngine

        steps = []
        for i, block in enumerate(self.chain):
            if i == 0:
                steps.append({
                    "index": block.index,
                    "status": "valid",
                    "reason": "Genesis block accepted",
                    "hash_match": True,
                    "link_match": True,
                    "pow_valid": True,
                    "merkle_match": True,
                })
                continue

            prev_block = self.chain[i - 1]
            diff = self._historical_difficulty(i)

            link_match = block.previous_hash == prev_block.hash
            pow_valid = block.hash.startswith("0" * diff)
            hash_match = block.hash == block.calculate_hash()
            expected_merkle = MerkleTree(block.transactions).root
            merkle_match = block.merkle_root == expected_merkle

            is_valid = link_match and pow_valid and hash_match and merkle_match
            reasons = []
            if not link_match:
                reasons.append(
                    f"Previous hash mismatch: expected {prev_block.hash[:16]}..., got {block.previous_hash[:16]}...")
            if not pow_valid:
                reasons.append(f"PoW invalid (needs {diff} leading zeros)")
            if not hash_match:
                reasons.append("Hash integrity compromised")
            if not merkle_match:
                reasons.append("Merkle root mismatch")

            steps.append({
                "index": block.index,
                "status": "valid" if is_valid else "invalid",
                "reason": "; ".join(reasons) if reasons else "All checks passed",
                "hash_match": hash_match,
                "link_match": link_match,
                "pow_valid": pow_valid,
                "merkle_match": merkle_match,
                "expected_difficulty": diff,
                "expected_hash": block.calculate_hash(),
                "actual_hash": block.hash,
                "previous_hash": block.previous_hash,
                "actual_previous_hash": prev_block.hash,
            })

        overall = all(s["status"] == "valid" for s in steps)
        return {
            "valid": overall,
            "total_blocks": len(self.chain),
            "invalid_count": sum(1 for s in steps if s["status"] == "invalid"),
            "steps": steps,
        }

    def _historical_difficulty(self, block_index: int) -> int:
        from core.consensus import ConsensusEngine
        from config import DEFAULT_DIFFICULTY
        diff = DEFAULT_DIFFICULTY
        for i in range(1, block_index):
            diff = ConsensusEngine.calculate_difficulty(diff, self.chain[:i])
        return diff

    def remine_from(self, start_index: int) -> List[Dict[str, Any]]:
        from core.consensus import ConsensusEngine

        results = []
        for i in range(start_index, len(self.chain)):
            block = self.chain[i]
            prev_block = self.chain[i - 1]

            block.previous_hash = prev_block.hash
            block.merkle_root = MerkleTree(block.transactions).root

            diff = self._historical_difficulty(i)

            block.nonce = 0
            block.mine_block(diff)

            results.append({
                "index": block.index,
                "new_hash": block.hash,
                "nonce": block.nonce,
                "difficulty": diff,
            })

        return results

    def simulate_fork(self, fork_point: int, extra_blocks: int = 2) -> str:
        if fork_point < 0 or fork_point >= len(self.chain):
            raise ValueError("Invalid fork point")

        fork_id = f"fork_{int(time.time() * 1000)}"
        base = [Block.from_dict(b.to_dict())
                for b in self.chain[:fork_point + 1]]

        for i in range(extra_blocks):
            prev = base[-1]
            tx = {
                "sender": "FORK_NODE",
                "receiver": f"FORK_MINER_{i}",
                "amount": MINING_REWARD,
                "timestamp": time.time() + i,
                "signature": "FORK_REWARD",
            }
            block = BlockFactory.create_block(
                index=prev.index + 1,
                transactions=[tx],
                previous_hash=prev.hash,
            )
            block.mine_block(self.difficulty)
            base.append(block)

        self.fork_chains[fork_id] = base
        return fork_id

    def resolve_fork(self, fork_id: str) -> Dict[str, Any]:
        from core.consensus import ConsensusEngine

        if fork_id not in self.fork_chains:
            raise ValueError("Fork not found")

        fork = self.fork_chains[fork_id]
        main_valid = ConsensusEngine.validate_chain(self.chain)
        fork_valid = ConsensusEngine.validate_chain(fork)

        main_len = len(self.chain)
        fork_len = len(fork)

        if fork_valid and fork_len > main_len:
            self.chain = [Block.from_dict(b.to_dict()) for b in fork]
            winner = "fork"
        elif main_valid:
            winner = "main"
        elif fork_valid:
            self.chain = [Block.from_dict(b.to_dict()) for b in fork]
            winner = "fork"
        else:
            winner = "none"

        del self.fork_chains[fork_id]

        return {
            "winner": winner,
            "main_length": main_len,
            "fork_length": fork_len,
            "main_valid": main_valid,
            "fork_valid": fork_valid,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain": [b.to_dict() for b in self.chain],
            "length": len(self.chain),
            "pending": self.pending,
            "difficulty": self.difficulty,
            "mining": self.get_mining_state(),
        }


# ── Session Manager ───────────────────────────────────────────────────────────


DEMO_SESSIONS: Dict[str, DemoSession] = {}


def create_demo_session(real_chain: List[Block], real_difficulty: int) -> str:
    """Spawn a new isolated playground session."""
    cleanup_old_sessions()
    sid = str(uuid.uuid4())[:8]
    demo = DemoBlockchain(real_chain, real_difficulty)
    session = DemoSession(
        session_id=sid,
        chain=demo.chain,
        difficulty=demo.difficulty,
    )
    session._demo = demo  # type: ignore
    DEMO_SESSIONS[sid] = session
    return sid


def get_demo_session(session_id: str) -> DemoSession:
    if session_id not in DEMO_SESSIONS:
        raise ValueError("Demo session not found")
    return DEMO_SESSIONS[session_id]


def get_demo_blockchain(session_id: str) -> DemoBlockchain:
    session = get_demo_session(session_id)
    if not hasattr(session, '_demo'):
        session._demo = DemoBlockchain(session.chain, session.difficulty)
    return session._demo  # type: ignore


def cleanup_old_sessions(max_age_seconds: float = 3600):
    now = time.time()
    stale = [sid for sid, s in DEMO_SESSIONS.items() if now -
             s.created_at > max_age_seconds]
    for sid in stale:
        del DEMO_SESSIONS[sid]
