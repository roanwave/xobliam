"""Execute email deletions with Gmail API."""

import time
from typing import Any, Callable

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from xobliam.auth import get_gmail_service
from xobliam.fetcher import MessageCache


def delete_messages(
    message_ids: list[str],
    service: Resource | None = None,
    cache: MessageCache | None = None,
    dry_run: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
    batch_size: int = 100,
) -> dict[str, Any]:
    """
    Delete messages from Gmail.

    Args:
        message_ids: List of message IDs to delete.
        service: Gmail API service. Created if not provided.
        cache: Message cache to update after deletion.
        dry_run: If True, don't actually delete (just simulate).
        progress_callback: Optional callback for progress updates.
        batch_size: Number of messages to delete in each batch.

    Returns:
        Dictionary with deletion results.
    """
    if not message_ids:
        return {
            "success": True,
            "deleted": 0,
            "failed": 0,
            "dry_run": dry_run,
            "errors": [],
        }

    if service is None and not dry_run:
        service = get_gmail_service()

    if cache is None:
        cache = MessageCache()

    deleted = 0
    failed = 0
    errors = []

    total = len(message_ids)

    for i in range(0, total, batch_size):
        batch = message_ids[i : i + batch_size]

        for msg_id in batch:
            if dry_run:
                # Simulate deletion
                deleted += 1
            else:
                try:
                    _delete_single_message(service, msg_id)
                    deleted += 1
                except HttpError as e:
                    failed += 1
                    errors.append({
                        "message_id": msg_id,
                        "error": str(e),
                    })
                except Exception as e:
                    failed += 1
                    errors.append({
                        "message_id": msg_id,
                        "error": str(e),
                    })

            if progress_callback:
                progress_callback(deleted + failed, total)

        # Small delay between batches to avoid rate limits
        if not dry_run and i + batch_size < total:
            time.sleep(0.5)

    # Update cache to remove deleted messages
    if deleted > 0:
        successfully_deleted = [
            msg_id
            for msg_id in message_ids
            if msg_id not in [e["message_id"] for e in errors]
        ]
        cache.delete_messages(successfully_deleted)

    return {
        "success": failed == 0,
        "deleted": deleted,
        "failed": failed,
        "dry_run": dry_run,
        "errors": errors[:10],  # Limit errors in response
        "total_errors": len(errors),
    }


def _delete_single_message(service: Resource, message_id: str) -> None:
    """
    Delete a single message.

    Uses trash instead of permanent delete for safety.
    """
    # Move to trash (can be recovered)
    service.users().messages().trash(userId="me", id=message_id).execute()


def permanently_delete_messages(
    message_ids: list[str],
    service: Resource | None = None,
    cache: MessageCache | None = None,
    dry_run: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """
    Permanently delete messages (cannot be recovered).

    Args:
        message_ids: List of message IDs to delete.
        service: Gmail API service.
        cache: Message cache to update.
        dry_run: If True, don't actually delete.
        progress_callback: Optional progress callback.
        confirm: Must be True to actually delete.

    Returns:
        Dictionary with deletion results.
    """
    if not confirm and not dry_run:
        return {
            "success": False,
            "deleted": 0,
            "failed": 0,
            "dry_run": dry_run,
            "error": "Permanent deletion requires confirm=True",
        }

    if not message_ids:
        return {
            "success": True,
            "deleted": 0,
            "failed": 0,
            "dry_run": dry_run,
            "errors": [],
        }

    if service is None and not dry_run:
        service = get_gmail_service()

    if cache is None:
        cache = MessageCache()

    deleted = 0
    failed = 0
    errors = []
    total = len(message_ids)

    for i, msg_id in enumerate(message_ids):
        if dry_run:
            deleted += 1
        else:
            try:
                service.users().messages().delete(userId="me", id=msg_id).execute()
                deleted += 1
            except HttpError as e:
                failed += 1
                errors.append({"message_id": msg_id, "error": str(e)})
            except Exception as e:
                failed += 1
                errors.append({"message_id": msg_id, "error": str(e)})

        if progress_callback:
            progress_callback(i + 1, total)

        # Rate limiting
        if not dry_run and (i + 1) % 50 == 0:
            time.sleep(0.5)

    # Update cache
    if deleted > 0:
        successfully_deleted = [
            msg_id
            for msg_id in message_ids
            if msg_id not in [e["message_id"] for e in errors]
        ]
        cache.delete_messages(successfully_deleted)

    return {
        "success": failed == 0,
        "deleted": deleted,
        "failed": failed,
        "dry_run": dry_run,
        "permanent": True,
        "errors": errors[:10],
        "total_errors": len(errors),
    }


def empty_trash(
    service: Resource | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Empty the trash folder.

    Args:
        service: Gmail API service.
        dry_run: If True, don't actually empty.

    Returns:
        Dictionary with result.
    """
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "message": "Would empty trash",
        }

    if service is None:
        service = get_gmail_service()

    try:
        # Get trash message count first
        results = (
            service.users()
            .messages()
            .list(userId="me", labelIds=["TRASH"], maxResults=1)
            .execute()
        )
        count = results.get("resultSizeEstimate", 0)

        # Empty trash
        service.users().messages().batchDelete(
            userId="me",
            body={"ids": []},  # Empty to trigger full trash deletion
        ).execute()

        return {
            "success": True,
            "dry_run": False,
            "approximate_deleted": count,
        }
    except HttpError as e:
        return {
            "success": False,
            "dry_run": False,
            "error": str(e),
        }


def restore_from_trash(
    message_ids: list[str],
    service: Resource | None = None,
    cache: MessageCache | None = None,
) -> dict[str, Any]:
    """
    Restore messages from trash.

    Args:
        message_ids: List of message IDs to restore.
        service: Gmail API service.
        cache: Message cache to update.

    Returns:
        Dictionary with restore results.
    """
    if not message_ids:
        return {
            "success": True,
            "restored": 0,
            "failed": 0,
        }

    if service is None:
        service = get_gmail_service()

    restored = 0
    failed = 0
    errors = []

    for msg_id in message_ids:
        try:
            service.users().messages().untrash(userId="me", id=msg_id).execute()
            restored += 1
        except HttpError as e:
            failed += 1
            errors.append({"message_id": msg_id, "error": str(e)})

    return {
        "success": failed == 0,
        "restored": restored,
        "failed": failed,
        "errors": errors[:10],
    }
