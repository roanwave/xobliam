"""Sender analysis and ranking."""

from collections import defaultdict
from datetime import datetime
from typing import Any


def get_frequent_senders(
    messages: list[dict[str, Any]],
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """
    Get senders ranked by email volume with engagement metrics.

    Args:
        messages: List of message dictionaries.
        top_n: Number of top senders to return. None for all.

    Returns:
        List of sender dicts sorted by volume, each containing:
        - sender: email address
        - count: total emails
        - read_count: emails that were read
        - unread_count: emails still unread
        - read_rate: percentage read
        - first_email: date of first email
        - last_email: date of last email
        - has_attachments_count: emails with attachments
    """
    sender_data: dict[str, dict] = defaultdict(
        lambda: {
            "count": 0,
            "unread": 0,
            "attachments": 0,
            "dates": [],
        }
    )

    for msg in messages:
        sender = msg.get("sender", "unknown")
        sender_data[sender]["count"] += 1

        if msg.get("is_unread", False):
            sender_data[sender]["unread"] += 1

        if msg.get("has_attachments", False):
            sender_data[sender]["attachments"] += 1

        date_str = msg.get("date")
        if date_str:
            sender_data[sender]["dates"].append(date_str)

    results = []
    for sender, data in sender_data.items():
        count = data["count"]
        unread = data["unread"]
        read = count - unread
        dates = sorted(data["dates"])

        results.append(
            {
                "sender": sender,
                "count": count,
                "read_count": read,
                "unread_count": unread,
                "read_rate": round((read / count) * 100, 2) if count > 0 else 0.0,
                "first_email": dates[0] if dates else None,
                "last_email": dates[-1] if dates else None,
                "has_attachments_count": data["attachments"],
            }
        )

    sorted_results = sorted(results, key=lambda x: x["count"], reverse=True)

    if top_n:
        return sorted_results[:top_n]
    return sorted_results


def get_sender_domains(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Get email volume by sender domain.

    Args:
        messages: List of message dictionaries.

    Returns:
        List of domain dicts sorted by volume.
    """
    domain_data: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "unread": 0, "senders": set()}
    )

    for msg in messages:
        sender = msg.get("sender", "")
        if "@" in sender:
            domain = sender.split("@")[1]
        else:
            domain = "unknown"

        domain_data[domain]["count"] += 1
        domain_data[domain]["senders"].add(sender)

        if msg.get("is_unread", False):
            domain_data[domain]["unread"] += 1

    results = []
    for domain, data in domain_data.items():
        count = data["count"]
        unread = data["unread"]
        read = count - unread

        results.append(
            {
                "domain": domain,
                "count": count,
                "read_count": read,
                "unread_count": unread,
                "read_rate": round((read / count) * 100, 2) if count > 0 else 0.0,
                "unique_senders": len(data["senders"]),
            }
        )

    return sorted(results, key=lambda x: x["count"], reverse=True)


def get_one_time_senders(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Find senders who only sent one email.

    Args:
        messages: List of message dictionaries.

    Returns:
        List of one-time sender dicts with message details.
    """
    senders = get_frequent_senders(messages)
    return [s for s in senders if s["count"] == 1]


def get_recent_new_senders(
    messages: list[dict[str, Any]],
    days: int = 7,
) -> list[dict[str, Any]]:
    """
    Find senders whose first email was within recent days.

    Args:
        messages: List of message dictionaries.
        days: Number of days to consider as recent.

    Returns:
        List of new sender dicts.
    """
    senders = get_frequent_senders(messages)
    cutoff = datetime.utcnow().isoformat()

    new_senders = []
    for sender in senders:
        first_email = sender.get("first_email")
        if first_email:
            try:
                first_dt = datetime.fromisoformat(first_email.replace("Z", "+00:00"))
                days_ago = (datetime.utcnow() - first_dt.replace(tzinfo=None)).days
                if days_ago <= days:
                    sender["days_since_first"] = days_ago
                    new_senders.append(sender)
            except (ValueError, AttributeError):
                continue

    return new_senders


def get_sender_summary(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Get summary statistics about senders.

    Args:
        messages: List of message dictionaries.

    Returns:
        Dictionary with sender statistics.
    """
    senders = get_frequent_senders(messages)

    if not senders:
        return {
            "total_senders": 0,
            "one_time_senders": 0,
            "repeat_senders": 0,
            "top_sender": None,
            "avg_emails_per_sender": 0.0,
        }

    one_time = len([s for s in senders if s["count"] == 1])
    total_emails = sum(s["count"] for s in senders)

    return {
        "total_senders": len(senders),
        "one_time_senders": one_time,
        "repeat_senders": len(senders) - one_time,
        "top_sender": senders[0] if senders else None,
        "avg_emails_per_sender": round(total_emails / len(senders), 2),
    }
