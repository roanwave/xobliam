"""Safety scoring for email deletion candidates."""

import re
from datetime import datetime
from typing import Any

from xobliam.taxonomy import classify_message


def calculate_safety_score(
    message: dict[str, Any],
    user_context: dict[str, Any] | None = None,
) -> int:
    """
    Calculate a safety score for deleting a message.

    Higher score = safer to delete (0-100).

    Args:
        message: Message dictionary with metadata.
        user_context: Context about user behavior including:
            - user_domain: User's email domain
            - deleted_senders: Set of senders previously deleted
            - replied_threads: Set of thread IDs user replied to
            - high_engagement_senders: Set of senders user engages with

    Returns:
        Safety score from 0 to 100.
    """
    if user_context is None:
        user_context = {}

    score = 50  # Base score

    # POSITIVE signals (safer to delete)
    if _has_unsubscribe_link(message):
        score += 20

    if _is_unread_since_receipt(message):
        score += 15

    if _sender_previously_deleted(message, user_context):
        score += 10

    age_days = _message_age_days(message)
    if age_days > 30:
        score += 10
    elif age_days > 60:
        score += 5  # Additional bonus for older messages

    if not message.get("has_attachments", False):
        score += 5

    if not _user_replied_in_thread(message, user_context):
        score += 5

    if _is_promotional_classification(message, user_context):
        score += 5

    # NEGATIVE signals (riskier to delete)
    if _user_replied_in_thread(message, user_context):
        score -= 40

    if message.get("has_attachments", False):
        score -= 30

    if _is_from_user_domain(message, user_context):
        score -= 25

    if _is_starred_or_important(message):
        score -= 20

    if age_days < 7:
        score -= 15

    if _is_high_engagement_sender(message, user_context):
        score -= 10

    if _contains_transactional_keywords(message):
        score -= 10

    if _thread_message_count(message, user_context) > 1:
        score -= 5

    # Clamp to 0-100 range
    return max(0, min(100, score))


def _has_unsubscribe_link(message: dict[str, Any]) -> bool:
    """Check if message has unsubscribe indicators."""
    snippet = message.get("snippet", "").lower()
    subject = message.get("subject", "").lower()
    content = f"{snippet} {subject}"

    unsubscribe_patterns = [
        "unsubscribe",
        "opt out",
        "opt-out",
        "manage preferences",
        "email preferences",
        "stop receiving",
        "remove yourself",
    ]

    return any(pattern in content for pattern in unsubscribe_patterns)


def _is_unread_since_receipt(message: dict[str, Any]) -> bool:
    """Check if message has never been read."""
    return message.get("is_unread", False)


def _sender_previously_deleted(
    message: dict[str, Any],
    user_context: dict[str, Any],
) -> bool:
    """Check if user has previously deleted emails from this sender."""
    sender = message.get("sender", "").lower()
    deleted_senders = user_context.get("deleted_senders", set())
    return sender in deleted_senders


def _message_age_days(message: dict[str, Any]) -> int:
    """Calculate message age in days."""
    date_str = message.get("date")
    if not date_str:
        return 0

    try:
        msg_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        age = datetime.utcnow() - msg_date.replace(tzinfo=None)
        return age.days
    except (ValueError, AttributeError):
        return 0


def _user_replied_in_thread(
    message: dict[str, Any],
    user_context: dict[str, Any],
) -> bool:
    """Check if user has replied in this thread."""
    thread_id = message.get("thread_id")
    if not thread_id:
        return False

    replied_threads = user_context.get("replied_threads", set())
    return thread_id in replied_threads


def _is_promotional_classification(
    message: dict[str, Any],
    user_context: dict[str, Any],
) -> bool:
    """Check if message is classified as marketing/promotional."""
    user_domain = user_context.get("user_domain")
    category = classify_message(message, user_domain)
    return category in ("marketing", "newsletter")


def _is_from_user_domain(
    message: dict[str, Any],
    user_context: dict[str, Any],
) -> bool:
    """Check if sender is from user's domain."""
    user_domain = user_context.get("user_domain", "")
    if not user_domain:
        return False

    sender = message.get("sender", "").lower()
    return user_domain.lower() in sender


def _is_starred_or_important(message: dict[str, Any]) -> bool:
    """Check if message is starred or marked important."""
    labels = message.get("labels", [])
    return "STARRED" in labels or "IMPORTANT" in labels


def _is_high_engagement_sender(
    message: dict[str, Any],
    user_context: dict[str, Any],
) -> bool:
    """Check if sender is one the user frequently engages with."""
    sender = message.get("sender", "").lower()
    high_engagement = user_context.get("high_engagement_senders", set())
    return sender in high_engagement


def _contains_transactional_keywords(message: dict[str, Any]) -> bool:
    """Check if message contains transactional keywords."""
    subject = message.get("subject", "").lower()
    snippet = message.get("snippet", "").lower()
    content = f"{subject} {snippet}"

    transactional_patterns = [
        r"order\s*#?\d+",
        r"invoice\s*#?\d+",
        r"receipt",
        r"confirmation",
        r"payment",
        r"statement",
        r"contract",
        r"agreement",
        r"password reset",
        r"verification code",
        r"security alert",
        r"account\s+alert",
    ]

    for pattern in transactional_patterns:
        if re.search(pattern, content):
            return True

    return False


def _thread_message_count(
    message: dict[str, Any],
    user_context: dict[str, Any],
) -> int:
    """Get the number of messages in this thread."""
    # This would need thread data to be accurate
    # For now, we'll use the presence of "Re:" as a proxy
    subject = message.get("subject", "")
    if subject.lower().startswith("re:") or subject.lower().startswith("fwd:"):
        return 2  # At least 2 messages
    return 1


def get_score_breakdown(
    message: dict[str, Any],
    user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get a detailed breakdown of the safety score.

    Args:
        message: Message dictionary.
        user_context: User context dictionary.

    Returns:
        Dictionary with score and breakdown of factors.
    """
    if user_context is None:
        user_context = {}

    factors = []

    # Base score
    factors.append({"factor": "Base score", "impact": 50})

    # Positive factors
    if _has_unsubscribe_link(message):
        factors.append({"factor": "Has unsubscribe link", "impact": 20})

    if _is_unread_since_receipt(message):
        factors.append({"factor": "Unread since receipt", "impact": 15})

    if _sender_previously_deleted(message, user_context):
        factors.append({"factor": "Sender previously deleted", "impact": 10})

    age_days = _message_age_days(message)
    if age_days > 30:
        factors.append({"factor": f"Message age ({age_days} days)", "impact": 10})

    if not message.get("has_attachments", False):
        factors.append({"factor": "No attachments", "impact": 5})

    if not _user_replied_in_thread(message, user_context):
        factors.append({"factor": "No reply in thread", "impact": 5})

    if _is_promotional_classification(message, user_context):
        factors.append({"factor": "Promotional classification", "impact": 5})

    # Negative factors
    if _user_replied_in_thread(message, user_context):
        factors.append({"factor": "User replied in thread", "impact": -40})

    if message.get("has_attachments", False):
        factors.append({"factor": "Has attachments", "impact": -30})

    if _is_from_user_domain(message, user_context):
        factors.append({"factor": "From user's domain", "impact": -25})

    if _is_starred_or_important(message):
        factors.append({"factor": "Starred or important", "impact": -20})

    if age_days < 7:
        factors.append({"factor": f"Recent message ({age_days} days)", "impact": -15})

    if _is_high_engagement_sender(message, user_context):
        factors.append({"factor": "High engagement sender", "impact": -10})

    if _contains_transactional_keywords(message):
        factors.append({"factor": "Contains transactional keywords", "impact": -10})

    if _thread_message_count(message, user_context) > 1:
        factors.append({"factor": "Part of thread", "impact": -5})

    total_score = calculate_safety_score(message, user_context)

    return {
        "score": total_score,
        "factors": factors,
        "message_id": message.get("message_id"),
        "sender": message.get("sender"),
        "subject": message.get("subject"),
    }
