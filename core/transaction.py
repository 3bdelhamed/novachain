from typing import Any, Dict, Set

REQUIRED_FIELDS: Set[str] = {"sender", "receiver", "amount"}


def validate_transaction(tx: Dict[str, Any]) -> bool:
    """Check that a transaction dict contains valid required fields."""
    if not REQUIRED_FIELDS.issubset(tx):
        return False
    if not isinstance(tx["amount"], (int, float)):
        return False
    if tx["amount"] <= 0:
        return False
    return True