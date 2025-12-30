"""Fetcher module for Gmail data retrieval and caching."""

from .cache import MessageCache
from .label_ops import (
    apply_label_to_messages,
    create_filter_for_senders,
    create_label,
    delete_filter,
    get_label_id_by_name,
    get_label_name_by_id,
    list_filters,
    merge_labels,
)
from .labels import fetch_labels
from .messages import fetch_messages

__all__ = [
    "MessageCache",
    "apply_label_to_messages",
    "create_filter_for_senders",
    "create_label",
    "delete_filter",
    "fetch_labels",
    "fetch_messages",
    "get_label_id_by_name",
    "get_label_name_by_id",
    "list_filters",
    "merge_labels",
]
