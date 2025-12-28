"""Fetcher module for Gmail data retrieval and caching."""

from .cache import MessageCache
from .labels import fetch_labels
from .messages import fetch_messages

__all__ = ["MessageCache", "fetch_labels", "fetch_messages"]
