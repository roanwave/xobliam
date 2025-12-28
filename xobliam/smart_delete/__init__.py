"""Smart delete module for safe email cleanup."""

from .candidate_finder import (
    filter_unlabeled_messages,
    find_deletion_candidates,
    get_bulk_delete_recommendations,
    get_deletion_summary,
    get_safety_tier,
)
from .executor import delete_messages
from .safety_scorer import calculate_safety_score, get_score_breakdown

__all__ = [
    "calculate_safety_score",
    "delete_messages",
    "filter_unlabeled_messages",
    "find_deletion_candidates",
    "get_bulk_delete_recommendations",
    "get_deletion_summary",
    "get_safety_tier",
    "get_score_breakdown",
]
