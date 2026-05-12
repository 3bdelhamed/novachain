"""Pydantic request/response schemas."""

from typing import List, Optional

from pydantic import BaseModel


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