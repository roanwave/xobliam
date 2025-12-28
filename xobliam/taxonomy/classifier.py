"""Email classification by sender type."""

from collections import defaultdict
from typing import Any

from .rules import CATEGORY_ACTIONS, SENDER_TYPES


def classify_message(
    message: dict[str, Any],
    user_domain: str | None = None,
) -> str:
    """
    Classify a message into a sender type category.

    Args:
        message: Message dictionary with sender, subject, snippet fields.
        user_domain: User's email domain for professional detection.

    Returns:
        Category name string.
    """
    sender = message.get("sender", "").lower()
    subject = message.get("subject", "").lower()
    snippet = message.get("snippet", "").lower()

    # Combine subject and snippet for signal detection
    content = f"{subject} {snippet}"

    best_match = "unknown"
    best_priority = 999

    for category, rules in SENDER_TYPES.items():
        if category == "unknown":
            continue

        score = 0
        priority = rules.get("priority", 100)

        # Check from_patterns
        from_patterns = rules.get("from_patterns", [])
        for pattern in from_patterns:
            if pattern.lower() in sender:
                score += 3
                break

        # Check subject_patterns
        subject_patterns = rules.get("subject_patterns", [])
        for pattern in subject_patterns:
            if pattern.lower() in subject:
                score += 2
                break

        # Check signals in content
        signals = rules.get("signals", [])
        for signal in signals:
            if signal.lower() in content:
                score += 1

        # Handle professional detection
        if category == "professional" and user_domain:
            if user_domain.lower() in sender:
                score += 5

        # Handle low volume personal emails
        if category == "personal" and rules.get("low_volume"):
            # Personal domains get a base match but low priority
            for pattern in from_patterns:
                if pattern.lower() in sender:
                    score += 1
                    break

        # Update best match
        if score > 0 and (score > 0 or priority < best_priority):
            if best_match == "unknown" or priority < best_priority:
                best_match = category
                best_priority = priority

    return best_match


def classify_batch(
    messages: list[dict[str, Any]],
    user_domain: str | None = None,
) -> list[dict[str, Any]]:
    """
    Classify a batch of messages.

    Args:
        messages: List of message dictionaries.
        user_domain: User's email domain for professional detection.

    Returns:
        List of messages with added 'category' field.
    """
    results = []
    for msg in messages:
        msg_copy = msg.copy()
        msg_copy["category"] = classify_message(msg, user_domain)
        results.append(msg_copy)
    return results


def get_category_stats(
    messages: list[dict[str, Any]],
    user_domain: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Get statistics for each category.

    Args:
        messages: List of message dictionaries.
        user_domain: User's email domain for professional detection.

    Returns:
        Dictionary mapping category to stats.
    """
    category_data: dict[str, dict] = defaultdict(
        lambda: {
            "count": 0,
            "unread": 0,
            "senders": set(),
            "subjects": [],
        }
    )

    for msg in messages:
        category = classify_message(msg, user_domain)
        category_data[category]["count"] += 1

        if msg.get("is_unread", False):
            category_data[category]["unread"] += 1

        sender = msg.get("sender", "")
        category_data[category]["senders"].add(sender)

        if len(category_data[category]["subjects"]) < 10:
            category_data[category]["subjects"].append(msg.get("subject", ""))

    results = {}
    for category, data in category_data.items():
        count = data["count"]
        unread = data["unread"]
        read = count - unread

        results[category] = {
            "count": count,
            "unread": unread,
            "read": read,
            "read_rate": round((read / count) * 100, 2) if count > 0 else 0.0,
            "unique_senders": len(data["senders"]),
            "top_senders": list(data["senders"])[:5],
            "sample_subjects": data["subjects"],
            "description": SENDER_TYPES.get(category, {}).get("description", ""),
            "actions": CATEGORY_ACTIONS.get(category, {}),
        }

    return results


def get_unlabeled_taxonomy(
    messages: list[dict[str, Any]],
    user_domain: str | None = None,
) -> dict[str, Any]:
    """
    Get taxonomy for unlabeled emails.

    Args:
        messages: List of message dictionaries.
        user_domain: User's email domain.

    Returns:
        Dictionary with category breakdown and stats.
    """
    system_labels = {
        "INBOX",
        "SENT",
        "DRAFT",
        "SPAM",
        "TRASH",
        "UNREAD",
        "STARRED",
        "IMPORTANT",
        "CATEGORY_PERSONAL",
        "CATEGORY_SOCIAL",
        "CATEGORY_PROMOTIONS",
        "CATEGORY_UPDATES",
        "CATEGORY_FORUMS",
    }

    unlabeled = []
    for msg in messages:
        labels = set(msg.get("labels", []))
        has_user_labels = bool(labels - system_labels)
        if not has_user_labels:
            unlabeled.append(msg)

    stats = get_category_stats(unlabeled, user_domain)

    return {
        "total_unlabeled": len(unlabeled),
        "categories": stats,
        "category_distribution": {
            cat: data["count"] for cat, data in stats.items()
        },
    }


def get_sender_category_map(
    messages: list[dict[str, Any]],
    user_domain: str | None = None,
) -> dict[str, str]:
    """
    Create a mapping of senders to their most common category.

    Args:
        messages: List of message dictionaries.
        user_domain: User's email domain.

    Returns:
        Dictionary mapping sender email to category.
    """
    sender_categories: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for msg in messages:
        sender = msg.get("sender", "")
        category = classify_message(msg, user_domain)
        sender_categories[sender][category] += 1

    result = {}
    for sender, categories in sender_categories.items():
        # Get most common category for this sender
        most_common = max(categories.items(), key=lambda x: x[1])
        result[sender] = most_common[0]

    return result


def get_category_senders(
    messages: list[dict[str, Any]],
    category: str,
    user_domain: str | None = None,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """
    Get all senders in a specific category.

    Args:
        messages: List of message dictionaries.
        category: Category to filter by.
        user_domain: User's email domain.
        top_n: Limit results to top N senders by volume.

    Returns:
        List of sender statistics for the category.
    """
    sender_data: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "unread": 0}
    )

    for msg in messages:
        msg_category = classify_message(msg, user_domain)
        if msg_category == category:
            sender = msg.get("sender", "")
            sender_data[sender]["count"] += 1
            if msg.get("is_unread", False):
                sender_data[sender]["unread"] += 1

    results = []
    for sender, data in sender_data.items():
        count = data["count"]
        unread = data["unread"]
        results.append({
            "sender": sender,
            "count": count,
            "unread": unread,
            "read_rate": round(((count - unread) / count) * 100, 2) if count > 0 else 0.0,
        })

    sorted_results = sorted(results, key=lambda x: x["count"], reverse=True)

    if top_n:
        return sorted_results[:top_n]
    return sorted_results
