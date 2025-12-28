"""Open rate and engagement metrics."""

from collections import defaultdict
from typing import Any


def calculate_open_rate(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calculate overall open rate as engagement proxy.

    Open rate = (total - unread) / total

    Args:
        messages: List of message dictionaries with 'is_unread' field.

    Returns:
        Dictionary with total, read, unread counts and open_rate percentage.
    """
    if not messages:
        return {
            "total": 0,
            "read": 0,
            "unread": 0,
            "open_rate": 0.0,
        }

    total = len(messages)
    unread = sum(1 for msg in messages if msg.get("is_unread", False))
    read = total - unread

    return {
        "total": total,
        "read": read,
        "unread": unread,
        "open_rate": round((read / total) * 100, 2) if total > 0 else 0.0,
    }


def get_sender_engagement(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Calculate engagement metrics per sender.

    Args:
        messages: List of message dictionaries.

    Returns:
        List of sender engagement dicts, sorted by volume.
        Each dict has: sender, total, read, unread, open_rate
    """
    sender_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "unread": 0}
    )

    for msg in messages:
        sender = msg.get("sender", "unknown")
        sender_stats[sender]["total"] += 1
        if msg.get("is_unread", False):
            sender_stats[sender]["unread"] += 1

    results = []
    for sender, stats in sender_stats.items():
        total = stats["total"]
        unread = stats["unread"]
        read = total - unread
        results.append(
            {
                "sender": sender,
                "total": total,
                "read": read,
                "unread": unread,
                "open_rate": round((read / total) * 100, 2) if total > 0 else 0.0,
            }
        )

    return sorted(results, key=lambda x: x["total"], reverse=True)


def get_low_engagement_senders(
    messages: list[dict[str, Any]],
    min_emails: int = 5,
    max_open_rate: float = 20.0,
) -> list[dict[str, Any]]:
    """
    Find senders with low engagement (low open rate).

    Args:
        messages: List of message dictionaries.
        min_emails: Minimum email count to be considered.
        max_open_rate: Maximum open rate to be considered low engagement.

    Returns:
        List of low engagement sender dicts, sorted by volume.
    """
    engagement = get_sender_engagement(messages)

    return [
        sender
        for sender in engagement
        if sender["total"] >= min_emails and sender["open_rate"] <= max_open_rate
    ]


def get_high_engagement_senders(
    messages: list[dict[str, Any]],
    min_emails: int = 5,
    min_open_rate: float = 80.0,
) -> list[dict[str, Any]]:
    """
    Find senders with high engagement (high open rate).

    Args:
        messages: List of message dictionaries.
        min_emails: Minimum email count to be considered.
        min_open_rate: Minimum open rate to be considered high engagement.

    Returns:
        List of high engagement sender dicts, sorted by volume.
    """
    engagement = get_sender_engagement(messages)

    return [
        sender
        for sender in engagement
        if sender["total"] >= min_emails and sender["open_rate"] >= min_open_rate
    ]


def get_engagement_by_label(
    messages: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Calculate engagement metrics per label.

    Args:
        messages: List of message dictionaries with 'labels' field.

    Returns:
        Dictionary mapping label to engagement metrics.
    """
    label_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "unread": 0}
    )

    for msg in messages:
        labels = msg.get("labels", [])
        for label in labels:
            label_stats[label]["total"] += 1
            if msg.get("is_unread", False):
                label_stats[label]["unread"] += 1

    results = {}
    for label, stats in label_stats.items():
        total = stats["total"]
        unread = stats["unread"]
        read = total - unread
        results[label] = {
            "total": total,
            "read": read,
            "unread": unread,
            "open_rate": round((read / total) * 100, 2) if total > 0 else 0.0,
        }

    return results
