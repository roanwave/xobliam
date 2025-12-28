"""Gmail label fetching functionality."""

from typing import Any

from googleapiclient.discovery import Resource

from xobliam.auth import get_gmail_service

from .cache import MessageCache


def fetch_labels(
    service: Resource | None = None,
    cache: MessageCache | None = None,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """
    Fetch all Gmail labels.

    Args:
        service: Gmail API service. Created if not provided.
        cache: Message cache instance. Created if not provided.
        use_cache: Whether to use cached labels if available.

    Returns:
        List of label dictionaries with id, name, type, and message counts.
    """
    if cache is None:
        cache = MessageCache()

    # Check cache first
    if use_cache:
        cached_labels = cache.get_cached_labels()
        if cached_labels:
            return cached_labels

    # Clear old labels before fetching fresh ones
    # This ensures deleted labels don't persist in the cache
    cache.clear_labels()

    # Fetch from API
    if service is None:
        service = get_gmail_service()

    results = service.users().labels().list(userId="me").execute()
    labels_raw = results.get("labels", [])

    labels = []
    for label in labels_raw:
        # Get detailed info for each label
        try:
            label_detail = (
                service.users().labels().get(userId="me", id=label["id"]).execute()
            )
            labels.append(
                {
                    "id": label_detail.get("id"),
                    "name": label_detail.get("name"),
                    "type": label_detail.get("type"),
                    "messagesTotal": label_detail.get("messagesTotal", 0),
                    "messagesUnread": label_detail.get("messagesUnread", 0),
                }
            )
        except Exception:
            # If detail fetch fails, use basic info
            labels.append(
                {
                    "id": label.get("id"),
                    "name": label.get("name"),
                    "type": label.get("type"),
                    "messagesTotal": 0,
                    "messagesUnread": 0,
                }
            )

    # Cache the results
    cache.cache_labels(labels)

    return labels


def get_user_labels(
    service: Resource | None = None,
    cache: MessageCache | None = None,
) -> list[dict[str, Any]]:
    """
    Get only user-created labels (excluding system labels).

    Args:
        service: Gmail API service. Created if not provided.
        cache: Message cache instance. Created if not provided.

    Returns:
        List of user label dictionaries.
    """
    all_labels = fetch_labels(service=service, cache=cache)
    return [label for label in all_labels if label.get("type") == "user"]


def get_system_labels(
    service: Resource | None = None,
    cache: MessageCache | None = None,
) -> list[dict[str, Any]]:
    """
    Get only system labels.

    Args:
        service: Gmail API service. Created if not provided.
        cache: Message cache instance. Created if not provided.

    Returns:
        List of system label dictionaries.
    """
    all_labels = fetch_labels(service=service, cache=cache)
    return [label for label in all_labels if label.get("type") == "system"]


def get_label_by_name(
    name: str,
    service: Resource | None = None,
    cache: MessageCache | None = None,
) -> dict[str, Any] | None:
    """
    Get a label by its name.

    Args:
        name: The label name to find.
        service: Gmail API service. Created if not provided.
        cache: Message cache instance. Created if not provided.

    Returns:
        Label dictionary or None if not found.
    """
    all_labels = fetch_labels(service=service, cache=cache)
    for label in all_labels:
        if label.get("name") == name:
            return label
    return None
