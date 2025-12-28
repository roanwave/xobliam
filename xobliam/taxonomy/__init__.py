"""Taxonomy module for email classification."""

from .classifier import (
    classify_batch,
    classify_message,
    get_category_senders,
    get_category_stats,
    get_unlabeled_taxonomy,
)
from .rules import SENDER_TYPES

__all__ = [
    "SENDER_TYPES",
    "classify_message",
    "classify_batch",
    "get_category_senders",
    "get_category_stats",
    "get_unlabeled_taxonomy",
]
