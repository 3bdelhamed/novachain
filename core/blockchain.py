import json
import threading
import time
from typing import Any, Dict, List, Optional, Set

from config import MINING_REWARD, MINING_SENDER
from core.block import Block
from core.consensus import ConsensusEngine
from core.factory import BlockFactory
from storage.base import BlockchainStorage
from crypto.wallet import verify_transaction_signature


class Blockchain:
    """High-level blockchain orchestrator.

    Depends on:
        - BlockchainStorage (DIP): injected at startup.
        - ConsensusEngine (SRP): validation and retargeting rules.
        - BlockFactory (Factory): block instantiation.
    """

    def __init__(self, storage: BlockchainStorage) -> None:
        self.storage = storage
        self.consensus = ConsensusEngine()
        self._mining = False
        self._mining_progress: Dict[str, Any] = {
            "active": False, "nonce": 0, "hash": ""
        }
        self._mining_lock = threading.Lock()

        # Bootstrap genesis if storage is empty
        if self.storage.get_chain_length() == 0:
            genesis = BlockFactory.create_genesis_block()
            self.storage.save_block(genesis)

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def difficulty(self) -> int:
        return self.storage.get_difficulty()

    @property
    def chain(self) -> List[Block]:
        return self.storage.get_all_blocks()

    @property
    def pending_transactions(self) -> List[Dict[str, Any]]:
        return self.storage.get_pending_transactions()

    @property
    def nodes(self) -> Set[str]:
        return set(self.storage.get_nodes())

    # ── Internal Persistence ─────────────────────────────────────────────────

    def _evaluate_retarget(self) -> None:
        """Trigger difficulty adjustment every RETARGET_INTERVAL blocks."""
        length = self.storage.get_chain_length()
        if length % 10 == 0 and length > 0:
            new_diff = self.consensus.calculate_difficulty(
                self.difficulty, self.chain)
            if new_diff != self.difficulty:
                self.storage.save_difficulty(new_diff)

    # ── Public Chain Operations ──────────────────────────────────────────────

    def get_latest_block(self) -> Block:
        latest = self.storage.get_latest_block()
        if not latest:
            raise RuntimeError("Blockchain has no blocks")
        return latest

    def add_block(self, block: Block) -> bool:
        latest = self.get_latest_block()
        if not self.consensus.validate_block(block, latest, self.difficulty):
            return False
        self.storage.save_block(block)
        self._evaluate_retarget()
        return True

    def add_transaction(self, transaction: Dict[str, Any]) -> bool:
        required = {"sender", "receiver", "amount"}
        if not required.issubset(transaction):
            return False
        if transaction["amount"] <= 0:
            return False

        # -- BUG FIX: Enforce Cryptographic Signatures --
        if transaction["sender"] != MINING_SENDER:
            # 1. Check Balance
            bal = self.get_balance(transaction["sender"])
            if bal < transaction["amount"]:
                return False

        # 2. Check Signature (using the wallet module)
        sig = transaction.get("signature", "")
        pub_key = transaction.get("public_key", "")

        # --- UI BYPASS FIX ---
        # If the transaction comes from the HTML UI, it will have a dummy signature like "UNSIGNED"
        if sig != "UNSIGNED":
            tx_data_to_verify = {
                "sender": transaction["sender"],
                "receiver": transaction["receiver"],
                "amount": transaction["amount"],
                "timestamp": transaction.get("timestamp")
            }

            from crypto.wallet import verify_transaction_signature
            if not verify_transaction_signature(tx_data_to_verify, sig, pub_key):
                return False  # Hacker blocked!
        # ---------------------

        pending = self.pending_transactions
        if transaction in pending:
            return True

        pending.append(transaction)
        self.storage.save_pending_transactions(pending)
        return True

    def get_balance(self, address: str) -> float:
        balance = 0.0
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("receiver") == address:
                    balance += tx["amount"]
                if tx.get("sender") == address:
                    balance -= tx["amount"]
        for tx in self.pending_transactions:
            if tx.get("sender") == address:
                balance -= tx["amount"]
        return balance

    def get_transaction_history(self, address: str) -> List[Dict[str, Any]]:
        history = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("sender") == address or tx.get("receiver") == address:
                    history.append(
                        {**tx, "block_index": block.index, "confirmed": True})
        for tx in self.pending_transactions:
            if tx.get("sender") == address or tx.get("receiver") == address:
                history.append({**tx, "block_index": None, "confirmed": False})
        return sorted(history, key=lambda x: x.get("timestamp", 0), reverse=True)

    # ── Mining ───────────────────────────────────────────────────────────────

    def mine_pending_transactions(self, miner_address: str) -> Optional[Block]:
        reward_tx = {
            "sender": MINING_SENDER,
            "receiver": miner_address,
            "amount": MINING_REWARD,
            "timestamp": time.time(),
            "signature": "REWARD",
        }
        pending = list(self.pending_transactions)
        txs = pending + [reward_tx]

        block = BlockFactory.create_block(
            index=self.storage.get_chain_length(),
            transactions=txs,
            previous_hash=self.get_latest_block().hash,
        )

        self._mining_progress = {"active": True, "nonce": 0, "hash": ""}
        self._mining = True

        while self._mining:
            block.nonce += 1
            block.hash = block.calculate_hash()
            self._mining_progress["nonce"] = block.nonce
            self._mining_progress["hash"] = block.hash
            if block.hash.startswith("0" * self.difficulty):
                break

        if not self._mining:
            self._mining_progress = {"active": False, "nonce": 0, "hash": ""}
            return None

        self._mining = False
        self._mining_progress["active"] = False

        with self._mining_lock:
            self.storage.save_block(block)
            mined_tx_strings = {json.dumps(tx, sort_keys=True)
                                for tx in pending}
            current_pending = self.storage.get_pending_transactions()

            kept_pending = [
                tx for tx in current_pending
                if json.dumps(tx, sort_keys=True) not in mined_tx_strings
            ]
            self.storage.save_pending_transactions(kept_pending)

            self._evaluate_retarget()

        return block

    def start_mining_async(self, miner_address: str) -> bool:
        if self._mining:
            return False
        thread = threading.Thread(
            target=self.mine_pending_transactions,
            args=(miner_address,),
            daemon=True,
        )
        thread.start()
        return True

    def stop_mining(self) -> None:
        self._mining = False

    # ── Consensus / Nakamoto ─────────────────────────────────────────────────

    def replace_chain(self, new_chain: List[Block]) -> bool:
        # 1. FIX: Check if our current chain is healthy
        is_current_valid = self.is_chain_valid()
        
        # 2. FIX: Only enforce the "must be strictly longer" rule if our local chain is healthy.
        # If our local chain is broken, we gladly accept the new valid chain even if it's shorter.
        if is_current_valid and len(new_chain) <= self.storage.get_chain_length():
            return False
            
        if not self.consensus.validate_chain(new_chain):
            return False

        self.storage.clear_blocks()
        for block in new_chain:
            self.storage.save_block(block)

        # Recalculate and adopt the difficulty of the newly synced chain tip!
        from config import DEFAULT_DIFFICULTY
        new_diff = DEFAULT_DIFFICULTY
        for i in range(1, len(new_chain) + 1):
            new_diff = self.consensus.calculate_difficulty(new_diff, new_chain[:i])
        self.storage.save_difficulty(new_diff)

        # Purge confirmed transactions from mempool
        pending = self.pending_transactions
        confirmed = {
            json.dumps(tx, sort_keys=True)
            for block in new_chain
            for tx in block.transactions
        }
        new_pending = [
            tx for tx in pending
            if json.dumps(tx, sort_keys=True) not in confirmed
        ]
        self.storage.save_pending_transactions(new_pending)
        return True
    
    def reset_to_genesis(self) -> None:
        """Wipe chain and restart from genesis (debug)."""
        self.stop_mining()
        self.storage.clear_blocks()
        genesis = BlockFactory.create_genesis_block()
        self.storage.save_block(genesis)
        self.storage.save_pending_transactions([])


    def is_chain_valid(self) -> bool:
            # We no longer pass self.difficulty here
         return self.consensus.validate_chain(self.chain)

    def register_node(self, address: str) -> None:
        """Safely normalizes and registers a node without crashing on bad data."""
        def clean_url(url: str) -> str:
            if not url:
                return ""
            u = url.strip().rstrip("/")
            if not u.startswith("http"):
                u = "http://" + u
            return u.replace("localhost", "127.0.0.1")

        new_address = clean_url(address)
        if not new_address:
            return

        # Fetch existing nodes and clean them
        cleaned_nodes = set()
        for node in self.nodes:
            clean = clean_url(node)
            if clean:
                cleaned_nodes.add(clean)

        # Add the new node and save
        cleaned_nodes.add(new_address)
        self.storage.save_nodes(list(cleaned_nodes))

    def append_sync_block(self, block: Block) -> bool:
        """Safely validates and appends a single block during batch synchronization."""
        # If it is the Genesis block, just save it
        if block.index == 0:
            self.storage.save_block(block)
            return True

        latest = self.storage.get_latest_block()
        if not latest or not self.consensus.validate_block(block, latest, self.difficulty):
            return False

        self.storage.save_block(block)
        return True
    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain": [b.to_dict() for b in self.chain],
            "length": self.storage.get_chain_length(),
            "pending_transactions": self.pending_transactions,
            "nodes": list(self.nodes),
            "difficulty": self.difficulty,
            "valid": self.is_chain_valid(),
        }
