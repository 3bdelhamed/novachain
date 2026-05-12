import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

from config import DEFAULT_DIFFICULTY
from core.block import Block
from storage.base import BlockchainStorage


class SQLiteStorage(BlockchainStorage):
    """Drop-in SQLite replacement for LevelDBStorage."""

    def __init__(self, db_path: str) -> None:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                block_hash TEXT PRIMARY KEY,
                index_num INTEGER UNIQUE NOT NULL,
                data TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        self.conn.commit()
        cur.execute("INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)",
                    ("difficulty", str(DEFAULT_DIFFICULTY)))
        self.conn.commit()

    def save_block(self, block: Block) -> None:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO blocks (block_hash, index_num, data) VALUES (?, ?, ?)",
            (block.hash, block.index, json.dumps(block.to_dict())),
        )
        self.conn.commit()
        self.set_latest_hash(block.hash)
        cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                    ("chain_length", str(block.index + 1)))
        self.conn.commit()

    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        cur = self.conn.cursor()
        cur.execute("SELECT data FROM blocks WHERE block_hash = ?", (block_hash,))
        row = cur.fetchone()
        return Block.from_dict(json.loads(row["data"])) if row else None

    def get_block_by_index(self, index: int) -> Optional[Block]:
        cur = self.conn.cursor()
        cur.execute("SELECT data FROM blocks WHERE index_num = ?", (index,))
        row = cur.fetchone()
        return Block.from_dict(json.loads(row["data"])) if row else None

    def get_latest_block(self) -> Optional[Block]:
        h = self.get_latest_hash()
        return self.get_block_by_hash(h) if h else None

    def set_latest_hash(self, block_hash: str) -> None:
        cur = self.conn.cursor()
        cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                    ("latest_hash", block_hash))
        self.conn.commit()

    def get_latest_hash(self) -> Optional[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM meta WHERE key = ?", ("latest_hash",))
        row = cur.fetchone()
        return row["value"] if row else None

    def get_chain_length(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM meta WHERE key = ?", ("chain_length",))
        row = cur.fetchone()
        return int(row["value"]) if row else 0

    def get_all_blocks(self) -> List[Block]:
        cur = self.conn.cursor()
        cur.execute("SELECT data FROM blocks ORDER BY index_num ASC")
        return [Block.from_dict(json.loads(row["data"])) for row in cur.fetchall()]

    def clear_blocks(self) -> None:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM blocks")
        cur.execute("UPDATE meta SET value = ? WHERE key = ?", ("0", "chain_length"))
        cur.execute("UPDATE meta SET value = ? WHERE key = ?", ("", "latest_hash"))
        self.conn.commit()

    def save_pending_transactions(self, transactions: List[Dict[str, Any]]) -> None:
        cur = self.conn.cursor()
        cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                    ("pending", json.dumps(transactions)))
        self.conn.commit()

    def get_pending_transactions(self) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM meta WHERE key = ?", ("pending",))
        row = cur.fetchone()
        return json.loads(row["value"]) if row else []

    def save_nodes(self, nodes: List[str]) -> None:
        cur = self.conn.cursor()
        cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                    ("nodes", json.dumps(nodes)))
        self.conn.commit()

    def get_nodes(self) -> List[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM meta WHERE key = ?", ("nodes",))
        row = cur.fetchone()
        return json.loads(row["value"]) if row else []

    def save_difficulty(self, difficulty: int) -> None:
        cur = self.conn.cursor()
        cur.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                    ("difficulty", str(difficulty)))
        self.conn.commit()

    def get_difficulty(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM meta WHERE key = ?", ("difficulty",))
        row = cur.fetchone()
        return int(row["value"]) if row else DEFAULT_DIFFICULTY

    def close(self) -> None:
        self.conn.close()
        
    def get_blocks_batch(self, offset: int, limit: int) -> List[Block]:
        cur = self.conn.cursor()
        cur.execute("SELECT data FROM blocks ORDER BY index_num ASC LIMIT ? OFFSET ?", (limit, offset))
        return [Block.from_dict(json.loads(row["data"])) for row in cur.fetchall()]