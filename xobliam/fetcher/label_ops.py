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


def create_label(
    label_name: str,
    service: Resource | None = None,
) -> dict[str, Any]:
    """
    Create a new Gmail label.

    Args:
        label_name: Name for the new label.
        service: Gmail API service.

    Returns:
        Dictionary with created label info or error.
    """
    if service is None:
        service = get_gmail_service()

    try:
        label_body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        result = service.users().labels().create(userId="me", body=label_body).execute()
        return {
            "success": True,
            "label_id": result.get("id"),
            "label_name": result.get("name"),
        }
    except HttpError as e:
        error_msg = str(e)
        if "Label name exists" in error_msg or "already exists" in error_msg.lower():
            return {"success": False, "error": f"Label '{label_name}' already exists"}
        return {"success": False, "error": error_msg}


def apply_label_to_messages(
    message_ids: list[str],
    label_id: str,
    service: Resource | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """
    Apply a label to multiple messages using batch operations.

    Args:
        message_ids: List of message IDs to label.
        label_id: ID of the label to apply.
        service: Gmail API service.
        progress_callback: Optional callback for progress updates (current, total).

    Returns:
        Dictionary with results.
    """
    if service is None:
        service = get_gmail_service()

    if not message_ids:
        return {
            "success": True,
            "messages_labeled": 0,
            "message": "No messages to label",
        }

    modified_count = 0
    errors = []
    batch_size = 100

    for i in range(0, len(message_ids), batch_size):
        batch = message_ids[i : i + batch_size]

        try:
            service.users().messages().batchModify(
                userId="me",
                body={
                    "ids": batch,
                    "addLabelIds": [label_id],
                },
            ).execute()

            modified_count += len(batch)

            if progress_callback:
                progress_callback(modified_count, len(message_ids))

        except HttpError as e:
            errors.append({"batch_start": i, "error": str(e)})

    return {
        "success": len(errors) == 0,
        "messages_labeled": modified_count,
        "total_messages": len(message_ids),
        "errors": errors if errors else None,
    }


def create_filter_for_senders(
    senders: list[str],
    label_id: str,
    service: Resource | None = None,
) -> dict[str, Any]:
    """
    Create a Gmail filter to auto-label future emails from specified senders.

    Args:
        senders: List of sender email addresses.
        label_id: ID of the label to apply.
        service: Gmail API service.

    Returns:
        Dictionary with filter creation results.
    """
    if service is None:
        service = get_gmail_service()

    if not senders:
        return {
            "success": False,
            "error": "No senders provided",
        }

    # Build filter criteria: from:sender1 OR from:sender2 OR ...
    # Gmail filter uses "from:" query syntax
    from_queries = [f"from:{sender}" for sender in senders]

    # Gmail has a limit on filter criteria length, so we may need to chunk
    # For now, handle up to ~50 senders which should be under the limit
    if len(senders) > 50:
        return {
            "success": False,
            "error": f"Too many senders ({len(senders)}). Maximum 50 senders per filter.",
        }

    filter_criteria = " OR ".join(from_queries)

    # Build the filter body
    filter_body = {
        "criteria": {
            "from": " ".join(senders),  # Gmail API uses space-separated for OR
        },
        "action": {
            "addLabelIds": [label_id],
        },
    }

    try:
        result = (
            service.users()
            .settings()
            .filters()
            .create(userId="me", body=filter_body)
            .execute()
        )
        return {
            "success": True,
            "filter_id": result.get("id"),
            "senders_count": len(senders),
        }
    except HttpError as e:
        error_msg = str(e)
        if "Filter already exists" in error_msg:
            return {
                "success": False,
                "error": "A similar filter already exists",
            }
        return {
            "success": False,
            "error": error_msg,
        }
