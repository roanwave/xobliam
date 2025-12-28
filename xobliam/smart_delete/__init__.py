"""Smart delete module for safe email cleanup."""

from .candidate_finder import find_deletion_candidates, get_safety_tier
from .executor import delete_messages
from .safety_scorer import calculate_safety_score

__all__ = [
    "calculate_safety_score",
    "find_deletion_candidates",
    "get_safety_tier",
    "delete_messages",
]
