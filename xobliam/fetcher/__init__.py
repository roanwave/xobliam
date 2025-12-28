"""Fetcher module for Gmail data retrieval and caching."""

from .cache import MessageCache
from .label_ops import (
    apply_label_to_messages,
    create_label,
    get_label_id_by_name,
    merge_labels,
)
from .labels import fetch_labels
from .messages import fetch_messages

__all__ = [
    "MessageCache",
    "apply_label_to_messages",
    "create_label",
    "fetch_labels",
    "fetch_messages",
    "get_label_id_by_name",
    "merge_labels",
]
