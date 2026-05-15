# NovaChain 

**NovaChain** is a robust, Python-based blockchain implementation designed for both educational and production environments. Built with asynchronous networking, it features a complete Proof-of-Work consensus engine, a decentralized Peer-to-Peer network, cryptographic wallets, and an isolated learning sandbox.

## Key Features

* **Proof-of-Work (PoW) Consensus:** Implements Nakamoto Consensus rules with dynamic difficulty retargeting to maintain consistent block generation times.


* **Cryptographic Wallets:** Provides built-in wallet generation utilizing ECDSA (SECP256K1) and SHA-256 for secure transaction signing and verification.


* **Decentralized P2P Network:** Features an automated background discovery loop to find peers, heal network splits, and gossip transactions across active nodes.


* **Real-Time Subscriptions:** Integrates WebSockets to broadcast live network updates, newly mined blocks, and mempool changes directly to connected clients.


* **Persistent Storage:** Utilizes a robust SQLite storage backend to persist the blockchain ledger, meta-states, and registered nodes.


* **Educational Demo Sandbox:** Includes an isolated, session-based interactive playground (`/demo`) that operates independently from the real SQLite database and P2P network. This allows users to safely simulate forks, tamper with blocks, and visualize broken consensus chains.



## Technology Stack

* **Framework:** FastAPI and Uvicorn 


* **Language:** Python 


*  **Networking:** HTTPX (asynchronous REST) and WebSockets 


* **Cryptography:** `cryptography` package (ECDSA, SECP256K1) and `hashlib` (SHA-256) 


* **Database:** SQLite 



## Getting Started

### Prerequisites

Ensure you have Python installed on your system.

### 1. Installation

Install the required dependencies via the provided `requirements.txt` file:

```bash
pip install -r requirements.txt

```

### 2. Running a Single Node

You can start a standalone NovaChain node on the default port (8000) using:

```bash
python main.py

```

Note: If you have a compiled React UI in the `static/assets` folder, the server will mount and serve it automatically. Otherwise, it will return a JSON status payload prompting you to build the UI.

### 3. Running a Multi-Node Network

To test the P2P capabilities locally, NovaChain includes a launcher that automatically initializes a seed node and multiple peers. The nodes will automatically discover each other within a few seconds.

```bash
python runner.py

```

This script launches nodes on ports `8000`, `8001`, `8002`, and `8003`.

## API Overview

NovaChain provides a comprehensive suite of REST endpoints. Once the server is running, you can interact with the API directly.

### Core Endpoints

* `GET /chain`: Returns the full blockchain ledger and validation status.


* `GET /network/status`: Provides diagnostics on network health, peer synchronization status, and authoritative chain validation.


* `POST /mine`: Commences mining operations for pending transactions.


* `POST /transactions/new`: Submits a newly signed transaction to the mempool.


* `POST /nodes/register`: Manually registers new peer nodes.



### Demo Endpoints (Session Isolated)

* `POST /demo/session/create`: Spawns a fresh sandbox cloned from the real blockchain.


* `POST /demo/session/{session_id}/tamper`: Intentionally corrupts a block's data to demonstrate broken chain links.


* `POST /demo/session/{session_id}/fork`: Simulates a blockchain fork at a specified block index.



## Project Structure

* `api/`: Contains FastAPI routes (`routes.py`), Pydantic request models (`models.py`), and the educational sandbox endpoints (`demo_routes.py`).


* `core/`: Houses the fundamental blockchain logic, including `Blockchain`, `Block`, `ConsensusEngine`, and the isolated `DemoBlockchain`.


* `crypto/`: Provides cryptographic utilities, including `MerkleTree` construction and `Wallet` ECDSA logic.


* `network/`: Manages the peer-to-peer gossip protocol (`p2p.py`), automated peer discovery (`discovery.py`), and real-time event broadcasting (`websocket.py`).


* `storage/`: Defines the persistence layer via the base abstraction (`base.py`) and the concrete `SQLiteStorage` implementation (`sqlite.py`).