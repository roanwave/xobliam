"""Gmail message fetching with pagination and rate limiting."""

import base64
import os
import re
import time
from datetime import datetime, timedelta
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any, Callable

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from xobliam.auth import get_gmail_service

from .cache import MessageCache


def get_analysis_days() -> int:
    """Get the number of days to analyze from environment."""
    return int(os.getenv("ANALYSIS_DAYS", "90"))


def parse_email_address(raw: str) -> str:
    """Extract email address from a raw header value."""
    _, email = parseaddr(raw)
    return email.lower() if email else raw.lower()


def parse_date(headers: list[dict]) -> str | None:
    """Parse the Date header into ISO format."""
    for header in headers:
        if header.get("name", "").lower() == "date":
            try:
                dt = parsedate_to_datetime(header.get("value", ""))
                return dt.isoformat()
            except Exception:
                return None
    return None


def get_header_value(headers: list[dict], name: str) -> str:
    """Get a header value by name."""
    name_lower = name.lower()
    for header in headers:
        if header.get("name", "").lower() == name_lower:
            return header.get("value", "")
    return ""


def has_attachments(payload: dict) -> bool:
    """Check if message has attachments."""
    parts = payload.get("parts", [])
    for part in parts:
        if part.get("filename"):
            return True
        # Check nested parts
        if has_attachments(part):
            return True
    return False


def extract_message_metadata(
    message: dict,
    label_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Extract relevant metadata from a Gmail API message response.

    Args:
        message: Raw message from Gmail API.
        label_map: Optional mapping of label IDs to human-readable names.

    Returns:
        Dictionary with extracted metadata.
    """
    payload = message.get("payload", {})
    headers = payload.get("headers", [])
    label_ids = message.get("labelIds", [])

    # Convert label IDs to names if mapping provided
    if label_map:
        labels = [label_map.get(lid, lid) for lid in label_ids]
    else:
        labels = label_ids

    return {
        "message_id": message.get("id"),
        "thread_id": message.get("threadId"),
        "date": parse_date(headers),
        "sender": parse_email_address(get_header_value(headers, "From")),
        "recipients": get_header_value(headers, "To"),
        "subject": get_header_value(headers, "Subject"),
        "labels": labels,
        "is_unread": "UNREAD" in label_ids,
        "has_attachments": has_attachments(payload),
        "snippet": message.get("snippet", ""),
    }


def fetch_messages(
    days: int | None = None,
    service: Resource | None = None,
    cache: MessageCache | None = None,
    use_cache: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
    max_results_per_page: int = 500,
) -> list[dict[str, Any]]:
    """
    Fetch messages from Gmail API with pagination and caching.

    Args:
        days: Number of days to fetch. Defaults to ANALYSIS_DAYS env var.
        service: Gmail API service. Created if not provided.
        cache: Message cache instance. Created if not provided.
        use_cache: Whether to use cached messages if fresh.
        progress_callback: Optional callback for progress updates (current, total).
        max_results_per_page: Maximum results per API page (max 500).

    Returns:
        List of message metadata dictionaries.
    """
    if days is None:
        days = get_analysis_days()

    if cache is None:
        cache = MessageCache()

    # Check cache first
    if use_cache and cache.is_fresh():
        cached = cache.get_cached_messages(since_days=days)
        if cached:
            return cached

    # Clear old messages before fetching fresh ones
    # This ensures deleted messages and stale label assignments don't persist
    cache.clear_messages()

    # Fetch from API
    if service is None:
        service = get_gmail_service()

    # Fetch labels first to build ID-to-name mapping
    # (This also clears and refreshes the labels table)
    from .labels import fetch_labels

    fetch_labels(service=service, cache=cache, use_cache=False)
    label_map = cache.get_label_id_to_name_map()

    # Build date query
    after_date = datetime.utcnow() - timedelta(days=days)
    query = f"after:{after_date.strftime('%Y/%m/%d')}"

    messages = []
    page_token = None
    total_fetched = 0

    while True:
        # Fetch message IDs with pagination
        try:
            results = (
                service.users()
                .messages()
                .list(
                    userId="me",
                    q=query,
                    maxResults=max_results_per_page,
                    pageToken=page_token,
                )
                .execute()
            )
        except HttpError as e:
            if e.resp.status == 429:
                # Rate limited, exponential backoff
                _handle_rate_limit(1)
                continue
            raise

        message_refs = results.get("messages", [])

        if not message_refs:
            break

        # Fetch full message details in batches
        batch_messages = _fetch_message_batch(service, message_refs, label_map=label_map)
        messages.extend(batch_messages)

        total_fetched += len(batch_messages)

        if progress_callback:
            # Estimate total based on result size estimate
            estimated_total = results.get("resultSizeEstimate", total_fetched)
            progress_callback(total_fetched, estimated_total)

        page_token = results.get("nextPageToken")
        if not page_token:
            break

    # Cache the results
    cache.cache_messages(messages)

    return messages


def _fetch_message_batch(
    service: Resource,
    message_refs: list[dict],
    batch_size: int = 100,
    label_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch full message details for a batch of message references.

    Args:
        service: Gmail API service.
        message_refs: List of message reference dicts with 'id' keys.
        batch_size: Number of messages to fetch in parallel.
        label_map: Optional mapping of label IDs to human-readable names.

    Returns:
        List of extracted message metadata.
    """
    messages = []
    retries = 0
    max_retries = 5

    for i in range(0, len(message_refs), batch_size):
        batch_refs = message_refs[i : i + batch_size]

        for ref in batch_refs:
            while retries < max_retries:
                try:
                    msg = (
                        service.users()
                        .messages()
                        .get(
                            userId="me",
                            id=ref["id"],
                            format="metadata",
                            metadataHeaders=["From", "To", "Subject", "Date"],
                        )
                        .execute()
                    )
                    messages.append(extract_message_metadata(msg, label_map))
                    retries = 0
                    break
                except HttpError as e:
                    if e.resp.status == 429:
                        retries += 1
                        _handle_rate_limit(retries)
                    else:
                        # Skip this message on other errors
                        break

        # Small delay between batches to avoid rate limits
        time.sleep(0.1)

    return messages


def _handle_rate_limit(retry_count: int) -> None:
    """Handle rate limiting with exponential backoff."""
    wait_time = min(2**retry_count, 60)  # Max 60 seconds
    time.sleep(wait_time)


def fetch_message_full(
    message_id: str,
    service: Resource | None = None,
) -> dict[str, Any]:
    """
    Fetch a single message with full body content.

    Args:
        message_id: The message ID to fetch.
        service: Gmail API service. Created if not provided.

    Returns:
        Full message data including body.
    """
    if service is None:
        service = get_gmail_service()

    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )

    metadata = extract_message_metadata(msg)

    # Extract body
    payload = msg.get("payload", {})
    body = _extract_body(payload)
    metadata["body"] = body

    return metadata


def _extract_body(payload: dict) -> str:
    """Extract text body from message payload."""
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")

    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8")
        # Recursively check nested parts
        nested = _extract_body(part)
        if nested:
            return nested

    return ""


def get_thread_messages(
    thread_id: str,
    service: Resource | None = None,
) -> list[dict[str, Any]]:
    """
    Get all messages in a thread.

    Args:
        thread_id: The thread ID to fetch.
        service: Gmail API service. Created if not provided.

    Returns:
        List of message metadata for all messages in thread.
    """
    if service is None:
        service = get_gmail_service()

    thread = (
        service.users()
        .threads()
        .get(userId="me", id=thread_id, format="metadata")
        .execute()
    )

    return [extract_message_metadata(msg) for msg in thread.get("messages", [])]
