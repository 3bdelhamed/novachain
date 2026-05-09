# NovaChain — Distributed Blockchain Simulation Platform

A full-stack blockchain simulation built from scratch in Python + Vanilla JS.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the server
uvicorn main:app --reload --port 8000

# 3. Open in browser
# http://localhost:8000
```

## Run Tests

```bash
python tests.py
```

## Project Structure

```
novachain/
├── main.py          # FastAPI app — all REST endpoints + WebSocket
├── blockchain.py    # Block, Blockchain classes (PoW, validation, persistence)
├── wallet.py        # ECDSA wallet, key generation, digital signatures
├── tests.py         # Test suite (18 tests)
├── requirements.txt
└── templates/
    └── index.html   # Full web GUI
```

## API Endpoints

| Endpoint                    | Method | Description            |
|-----------------------------|--------|------------------------|
| `/chain`                    | GET    | Full blockchain state  |
| `/chain/valid`              | GET    | Validate chain         |
| `/transactions/new`         | POST   | Add transaction        |
| `/mine`                     | POST   | Mine pending txs       |
| `/mining/status`            | GET    | Live mining status     |
| `/mining/stop`              | POST   | Stop mining            |
| `/wallet/create`            | POST   | Generate wallet        |
| `/wallet/balance/{address}` | GET    | Balance + history      |
| `/nodes/register`           | POST   | Register peer node     |
| `/nodes/resolve`            | GET    | Run consensus          |
| `/difficulty`               | POST   | Set mining difficulty  |
| `/stats`                    | GET    | Chain statistics       |
| `/debug/tamper`             | POST   | Demo: tamper a block   |
| `/debug/reset`              | POST   | Reset to genesis       |
| `/ws`                       | WS     | Real-time updates      |

## Features Implemented

- ✅ SHA-256 hashing
- ✅ Proof of Work mining (configurable difficulty 1–6)
- ✅ Mining rewards (10 NVC per block)
- ✅ ECDSA digital signatures (secp256k1)
- ✅ Transaction validation (balance checks, signature verification)
- ✅ Blockchain validation (hash integrity, chain links, PoW)
- ✅ Tamper detection — modifying any block invalidates the chain
- ✅ Distributed nodes + Nakamoto consensus
- ✅ JSON persistence (survives server restart)
- ✅ WebSocket real-time updates
- ✅ Full web GUI with 7 sections
- ✅ 18 automated tests

## Multi-Node Simulation

Run two nodes on different ports:

```bash
# Terminal 1
uvicorn main:app --port 8000

# Terminal 2
cp blockchain_data.json /tmp/node2/
cd /tmp/node2
uvicorn main:app --port 8001
```

Then register nodes from the GUI: Network → Register Node → `http://localhost:8001`
