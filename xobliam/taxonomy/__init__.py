"""Taxonomy module for email classification."""

from .classifier import classify_batch, classify_message, get_category_stats
from .rules import SENDER_TYPES

__all__ = ["SENDER_TYPES", "classify_message", "classify_batch", "get_category_stats"]
