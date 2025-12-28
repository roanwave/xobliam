"""Fetcher module for Gmail data retrieval and caching."""

from .cache import MessageCache
from .label_ops import get_label_id_by_name, merge_labels
from .labels import fetch_labels
from .messages import fetch_messages

__all__ = [
    "MessageCache",
    "fetch_labels",
    "fetch_messages",
    "get_label_id_by_name",
    "merge_labels",
]
