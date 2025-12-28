"""Gmail label operations - merge, rename, delete."""

from typing import Any, Callable

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from xobliam.auth import get_gmail_service

from .cache import MessageCache


def merge_labels(
    source_label_id: str,
    target_label_id: str,
    delete_source: bool = False,
    service: Resource | None = None,
    cache: MessageCache | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """
    Merge one label into another.

    1. Get all messages with source label
    2. Add target label to those messages
    3. Remove source label from those messages
    4. Optionally delete source label entirely

    Args:
        source_label_id: ID of the label to merge FROM (will be removed).
        target_label_id: ID of the label to merge INTO (will be added).
        delete_source: If True, delete the source label after merging.
        service: Gmail API service. Created if not provided.
        cache: Message cache instance.
        progress_callback: Optional callback for progress updates (current, total).

    Returns:
        Dictionary with merge results.
    """
    if service is None:
        service = get_gmail_service()

    if cache is None:
        cache = MessageCache()

    # Get all messages with source label
    message_ids = []
    page_token = None

    while True:
        try:
            results = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    labelIds=[source_label_id],
                    maxResults=500,
                    pageToken=page_token,
                )
                .execute()
            )
        except HttpError as e:
            return {
                "success": False,
                "error": str(e),
                "messages_modified": 0,
            }

        messages = results.get("messages", [])
        message_ids.extend([m["id"] for m in messages])

        page_token = results.get("nextPageToken")
        if not page_token:
            break

    if not message_ids:
        return {
            "success": True,
            "messages_modified": 0,
            "source_deleted": False,
            "message": "No messages found with source label",
        }

    # Modify messages in batches
    modified_count = 0
    errors = []
    batch_size = 100

    for i in range(0, len(message_ids), batch_size):
        batch = message_ids[i : i + batch_size]

        try:
            # Batch modify - add target, remove source
            service.users().messages().batchModify(
                userId="me",
                body={
                    "ids": batch,
                    "addLabelIds": [target_label_id],
                    "removeLabelIds": [source_label_id],
                },
            ).execute()

            modified_count += len(batch)

            if progress_callback:
                progress_callback(modified_count, len(message_ids))

        except HttpError as e:
            errors.append({"batch_start": i, "error": str(e)})

    # Optionally delete the source label
    source_deleted = False
    if delete_source and not errors:
        try:
            service.users().labels().delete(userId="me", id=source_label_id).execute()
            source_deleted = True
        except HttpError as e:
            errors.append({"action": "delete_label", "error": str(e)})

    return {
        "success": len(errors) == 0,
        "messages_modified": modified_count,
        "total_messages": len(message_ids),
        "source_deleted": source_deleted,
        "errors": errors if errors else None,
    }


def get_label_id_by_name(
    label_name: str,
    service: Resource | None = None,
    cache: MessageCache | None = None,
) -> str | None:
    """
    Get a label ID by its name.

    Args:
        label_name: The label name to look up.
        service: Gmail API service.
        cache: Message cache instance.

    Returns:
        Label ID or None if not found.
    """
    if cache is None:
        cache = MessageCache()

    # Try cache first
    cached_labels = cache.get_cached_labels()
    for label in cached_labels:
        if label.get("name") == label_name:
            return label.get("label_id")

    # Fall back to API
    if service is None:
        service = get_gmail_service()

    try:
        results = service.users().labels().list(userId="me").execute()
        for label in results.get("labels", []):
            if label.get("name") == label_name:
                return label.get("id")
    except HttpError:
        pass

    return None


def delete_label(
    label_id: str,
    service: Resource | None = None,
) -> dict[str, Any]:
    """
    Delete a label.

    Args:
        label_id: ID of the label to delete.
        service: Gmail API service.

    Returns:
        Dictionary with delete results.
    """
    if service is None:
        service = get_gmail_service()

    try:
        service.users().labels().delete(userId="me", id=label_id).execute()
        return {"success": True}
    except HttpError as e:
        return {"success": False, "error": str(e)}
