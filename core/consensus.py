from typing import List

from config import (
    DEFAULT_DIFFICULTY,
    EXPECTED_MINE_TIME,
    MAX_DIFFICULTY,
    MIN_DIFFICULTY,
    RETARGET_INTERVAL,
)
from core.block import Block


class ConsensusEngine:
    """Encapsulates protocol validation and retargeting logic."""

    @staticmethod
    def validate_block(block: Block, previous_block: Block, difficulty: int) -> bool:
        """Validate a single block against its predecessor and difficulty target."""
        if block.previous_hash != previous_block.hash:
            return False
        if not block.hash.startswith("0" * difficulty):
            return False
        if block.hash != block.calculate_hash():
            return False
        return True

    @staticmethod
    def validate_chain(chain: List[Block], difficulty: int) -> bool:
        """Validate every link in the chain."""
        for i in range(1, len(chain)):
            if not ConsensusEngine.validate_block(chain[i], chain[i - 1], difficulty):
                return False
        return True

    @staticmethod
    def calculate_difficulty(
        current_difficulty: int,
        chain: List[Block],
        retarget_interval: int = RETARGET_INTERVAL,
        expected_time: int = EXPECTED_MINE_TIME,
    ) -> int:
        """Retargeting algorithm.

        Returns:
            The new difficulty clamped between MIN_DIFFICULTY and MAX_DIFFICULTY.
        """
        chain_length = len(chain)
        if chain_length == 0 or chain_length % retarget_interval != 0:
            return current_difficulty

        current_block = chain[-1]
        lookback_index = max(0, chain_length - retarget_interval - 1)
        lookback_block = chain[lookback_index]

        actual_time = current_block.timestamp - lookback_block.timestamp
        expected_time_total = retarget_interval * expected_time

        if actual_time <= 0:
            actual_time = 1.0

        ratio = expected_time_total / actual_time

        if ratio > 1.5:
            new_difficulty = current_difficulty + 1
        elif ratio < 0.5:
            new_difficulty = current_difficulty - 1
        else:
            new_difficulty = current_difficulty

        return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, new_difficulty))
    
    @staticmethod
    def validate_chain(chain: List[Block]) -> bool:
        """Validate every link in the chain, recalculating historical difficulty."""
        from config import DEFAULT_DIFFICULTY
        current_expected_diff = DEFAULT_DIFFICULTY

        for i in range(1, len(chain)):
            # 1. What should the difficulty have been for this specific block?
            expected_diff = ConsensusEngine.calculate_difficulty(
                current_expected_diff, chain[:i]
            )
            
            # 2. Validate the block using the historical expected difficulty
            if not ConsensusEngine.validate_block(chain[i], chain[i - 1], expected_diff):
                return False
                
            # 3. Move the difficulty forward for the next iteration
            current_expected_diff = expected_diff

        return True