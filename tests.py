"""
NovaChain Test Suite
Run: python tests.py
"""
import sys
import time
import json

# Add parent directory
sys.path.insert(0, '.')

from blockchain import Blockchain, Block, MINING_SENDER
from wallet import Wallet, verify_transaction_signature

# Clean up any persisted state to ensure test isolation
import os
for f in ["blockchain_data.json"]:
    if os.path.exists(f): os.remove(f)


def test(name, fn):
    try:
        result = fn()
        status = "PASS" if result else "FAIL"
        print(f"  {'✓' if result else '✗'} {name}")
        return result
    except Exception as e:
        print(f"  ✗ {name} — ERROR: {e}")
        return False


print("\n" + "="*50)
print("  NOVACHAIN TEST SUITE")
print("="*50)

results = []

# ── Block Tests ───────────────────────────────────────────────────────────────
print("\n[1] Block System")

def t_block_hash():
    ts = 1_700_000_000.0
    b = Block(0, [], "0"*64, timestamp=ts)
    h1 = b.calculate_hash()
    b2 = Block(0, [], "0"*64, timestamp=ts)
    return h1 == b2.calculate_hash()

def t_block_hash_changes():
    b = Block(0, [], "0"*64)
    h1 = b.calculate_hash()
    b.nonce = 99
    h2 = b.calculate_hash()
    return h1 != h2

def t_block_serialization():
    b = Block(1, [{"sender": "A", "receiver": "B", "amount": 10}], "abc123")
    d = b.to_dict()
    b2 = Block.from_dict(d)
    return b2.index == 1 and b2.hash == b.hash

results.append(test("Block hash is deterministic", t_block_hash))
results.append(test("Changing nonce changes hash", t_block_hash_changes))
results.append(test("Block serialization/deserialization", t_block_serialization))


# ── Blockchain Tests ──────────────────────────────────────────────────────────
print("\n[2] Blockchain System")

def t_genesis():
    bc = Blockchain(difficulty=1)
    return len(bc.chain) >= 1 and bc.chain[0].index == 0 and bc.chain[0].previous_hash == "0"*64

def t_valid_chain():
    bc = Blockchain(difficulty=1)
    return bc.is_chain_valid()

def t_add_transaction():
    bc = Blockchain(difficulty=1)
    # Add mining reward first to give genesis miner some coins
    bc.add_transaction({"sender": MINING_SENDER, "receiver": "ALICE", "amount": 100, "timestamp": time.time(), "signature": "REWARD"})
    bc.mine_pending_transactions("GENESIS")
    tx = {"sender": "ALICE", "receiver": "BOB", "amount": 5, "timestamp": time.time(), "signature": "SIG"}
    return bc.add_transaction(tx)

def t_balance():
    bc = Blockchain(difficulty=1)
    bc.add_transaction({"sender": MINING_SENDER, "receiver": "ALICE", "amount": 50, "timestamp": time.time(), "signature": "REWARD"})
    bc.mine_pending_transactions("ALICE")
    bal = bc.get_balance("ALICE")
    return bal > 0

results.append(test("Genesis block created correctly", t_genesis))
results.append(test("Fresh blockchain is valid", t_valid_chain))
results.append(test("Transaction added to pending pool", t_add_transaction))
results.append(test("Balance calculation works", t_balance))


# ── Mining Tests ──────────────────────────────────────────────────────────────
print("\n[3] Mining / Proof of Work")

def t_mining():
    import os; os.makedirs('/tmp/novatest', exist_ok=True)
    import blockchain as bc_mod
    old_file = bc_mod.DATA_FILE
    bc_mod.DATA_FILE = '/tmp/novatest/test_mining.json'
    try:
        bc = Blockchain(difficulty=2)
        block = bc.mine_pending_transactions("MINER")
        if block is None:
            block = bc.chain[-1]
        return block.hash.startswith("00") and bc.is_chain_valid()
    finally:
        bc_mod.DATA_FILE = old_file

def t_mining_reward():
    bc = Blockchain(difficulty=1)
    bc.mine_pending_transactions("MINER_ADDR")
    bal = bc.get_balance("MINER_ADDR")
    return bal == 10  # MINING_REWARD

def t_chain_still_valid_after_mining():
    bc = Blockchain(difficulty=1)
    bc.mine_pending_transactions("MINER")
    bc.mine_pending_transactions("MINER")
    return bc.is_chain_valid()

results.append(test("Block mines with correct difficulty", t_mining))
results.append(test("Miner receives reward", t_mining_reward))
results.append(test("Chain valid after multiple mines", t_chain_still_valid_after_mining))


# ── Validation Tests ──────────────────────────────────────────────────────────
print("\n[4] Tamper Detection")

def t_tamper_detected():
    bc = Blockchain(difficulty=1)
    bc.mine_pending_transactions("MINER")
    bc.mine_pending_transactions("MINER")
    # Tamper with a block without recalculating hash
    bc.chain[1].nonce = 999999
    return not bc.is_chain_valid()

def t_hash_mismatch_detected():
    bc = Blockchain(difficulty=1)
    bc.mine_pending_transactions("MINER")
    original_hash = bc.chain[1].hash
    bc.chain[1].hash = "0" * 64  # fake hash
    return not bc.is_chain_valid()

def t_broken_link_detected():
    bc = Blockchain(difficulty=1)
    bc.mine_pending_transactions("MINER")
    bc.mine_pending_transactions("MINER")
    bc.chain[2].previous_hash = "FAKEHASH"
    return not bc.is_chain_valid()

results.append(test("Tampered nonce detected", t_tamper_detected))
results.append(test("Fake hash detected", t_hash_mismatch_detected))
results.append(test("Broken chain link detected", t_broken_link_detected))


# ── Wallet Tests ──────────────────────────────────────────────────────────────
print("\n[5] Wallet System")

def t_wallet_creation():
    w = Wallet()
    return w.address.startswith("NC") and len(w.address) == 40

def t_unique_addresses():
    w1, w2 = Wallet(), Wallet()
    return w1.address != w2.address

def t_has_keys():
    w = Wallet()
    return len(w.public_key_hex) > 0 and len(w.private_key_hex) > 0

results.append(test("Wallet address starts with NC", t_wallet_creation))
results.append(test("Each wallet has unique address", t_unique_addresses))
results.append(test("Wallet has public and private keys", t_has_keys))


# ── Insufficient Funds ────────────────────────────────────────────────────────
print("\n[6] Transaction Rules")

def t_insufficient_funds():
    bc = Blockchain(difficulty=1)
    tx = {"sender": "BROKE_ADDR", "receiver": "RICH_ADDR", "amount": 1000, "timestamp": time.time(), "signature": "SIG"}
    return not bc.add_transaction(tx)

def t_negative_amount():
    bc = Blockchain(difficulty=1)
    tx = {"sender": MINING_SENDER, "receiver": "ADDR", "amount": -5, "timestamp": time.time(), "signature": "SIG"}
    return not bc.add_transaction(tx)

def t_mining_sender_bypass():
    bc = Blockchain(difficulty=1)
    tx = {"sender": MINING_SENDER, "receiver": "ADDR", "amount": 100, "timestamp": time.time(), "signature": "REWARD"}
    return bc.add_transaction(tx)

results.append(test("Insufficient funds rejected", t_insufficient_funds))
results.append(test("Negative amount rejected", t_negative_amount))
results.append(test("Mining reward bypasses balance check", t_mining_sender_bypass))


# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(results)
total = len(results)
print(f"\n{'='*50}")
print(f"  Results: {passed}/{total} tests passed")
if passed == total:
    print("  ✓ ALL TESTS PASSED")
else:
    print(f"  ✗ {total - passed} TESTS FAILED")
print("="*50 + "\n")
