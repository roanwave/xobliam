"""Suggest existing labels for unlabeled emails based on similarity."""

import re
from collections import Counter, defaultdict
from typing import Any


def extract_domain(email: str) -> str:
    """Extract domain from email address."""
    match = re.search(r"@([a-zA-Z0-9.-]+)", email)
    return match.group(1).lower() if match else ""


def extract_keywords(text: str, min_length: int = 3) -> list[str]:
    """Extract meaningful keywords from text."""
    if not text:
        return []

    # Common stop words to filter out
    stop_words = {
        "the", "and", "for", "you", "your", "are", "our", "this", "that",
        "with", "from", "have", "has", "was", "were", "been", "will",
        "can", "all", "new", "one", "get", "now", "just", "more", "out",
        "about", "into", "what", "how", "when", "where", "who", "why",
        "not", "but", "they", "their", "there", "here", "some", "any",
        "most", "other", "than", "then", "only", "also", "very", "just",
        "please", "thanks", "thank", "hello", "dear", "best", "regards",
        "email", "message", "click", "link", "view", "read", "see",
        "today", "week", "month", "year", "time", "day", "days",
    }

    # Extract words
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

    # Filter and return
    return [w for w in words if w not in stop_words and len(w) >= min_length]


def build_label_profile(
    messages: list[dict[str, Any]],
    label_name: str,
) -> dict[str, Any]:
    """
    Build a profile for a label based on its messages.

    Returns:
        Dictionary with sender domains, subject keywords, and their frequencies.
    """
    sender_domains = Counter()
    sender_emails = Counter()
    subject_keywords = Counter()
    snippet_keywords = Counter()

    message_count = 0

    for msg in messages:
        labels = msg.get("labels", [])
        if label_name not in labels:
            continue

        message_count += 1

        # Track sender info
        sender = msg.get("sender", "")
        domain = extract_domain(sender)
        if domain:
            sender_domains[domain] += 1
        if sender:
            sender_emails[sender.lower()] += 1

        # Track subject keywords
        subject = msg.get("subject", "") or ""
        for kw in extract_keywords(subject):
            subject_keywords[kw] += 1

        # Track snippet keywords
        snippet = msg.get("snippet", "") or ""
        for kw in extract_keywords(snippet):
            snippet_keywords[kw] += 1

    if message_count == 0:
        return None

    # Normalize frequencies
    return {
        "label": label_name,
        "message_count": message_count,
        "sender_domains": dict(sender_domains.most_common(20)),
        "sender_emails": dict(sender_emails.most_common(20)),
        "subject_keywords": dict(subject_keywords.most_common(30)),
        "snippet_keywords": dict(snippet_keywords.most_common(30)),
        # Combined top keywords
        "top_keywords": list((subject_keywords + snippet_keywords).most_common(20)),
    }


def build_all_label_profiles(
    messages: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build profiles for all user labels."""
    # Get all unique user labels
    all_labels = set()
    for msg in messages:
        for label in msg.get("labels", []):
            # Skip system labels
            if label.upper() in {"INBOX", "SENT", "DRAFT", "TRASH", "SPAM", "STARRED",
                                 "IMPORTANT", "UNREAD", "CATEGORY_PERSONAL",
                                 "CATEGORY_SOCIAL", "CATEGORY_PROMOTIONS",
                                 "CATEGORY_UPDATES", "CATEGORY_FORUMS"}:
                continue
            all_labels.add(label)

    profiles = {}
    for label in all_labels:
        profile = build_label_profile(messages, label)
        if profile and profile["message_count"] >= 3:  # Need at least 3 messages
            profiles[label] = profile

    return profiles


def score_message_against_profile(
    message: dict[str, Any],
    profile: dict[str, Any],
) -> tuple[float, list[str]]:
    """
    Score how well a message matches a label profile.

    Returns:
        Tuple of (score 0-100, list of match reasons).
    """
    score = 0.0
    reasons = []

    # Sender email exact match (strong signal)
    sender = message.get("sender", "").lower()
    if sender in profile["sender_emails"]:
        score += 40
        reasons.append(f"sender matches {profile['label']} pattern")

    # Sender domain match (moderate signal)
    domain = extract_domain(sender)
    if domain and domain in profile["sender_domains"]:
        domain_freq = profile["sender_domains"][domain]
        domain_score = min(25, domain_freq * 5)
        score += domain_score
        if not reasons:  # Only add if not already matched by email
            reasons.append(f"sender domain matches {profile['label']} emails")

    # Subject keyword matches
    subject = message.get("subject", "") or ""
    subject_kws = set(extract_keywords(subject))
    profile_subject_kws = set(profile["subject_keywords"].keys())
    subject_overlap = subject_kws & profile_subject_kws

    if subject_overlap:
        # Weight by how common these keywords are in the profile
        kw_score = 0
        matched_kws = []
        for kw in subject_overlap:
            freq = profile["subject_keywords"].get(kw, 0)
            if freq >= 3:  # Only count keywords that appear at least 3 times
                kw_score += min(5, freq)
                matched_kws.append(kw)

        if matched_kws:
            score += min(20, kw_score)
            reasons.append(f"subject contains '{', '.join(matched_kws[:3])}'")

    # Snippet keyword matches (weaker signal)
    snippet = message.get("snippet", "") or ""
    snippet_kws = set(extract_keywords(snippet))
    profile_snippet_kws = set(profile["snippet_keywords"].keys())
    snippet_overlap = snippet_kws & profile_snippet_kws

    if snippet_overlap and len(snippet_overlap) >= 3:
        score += min(15, len(snippet_overlap) * 2)

    return min(100, score), reasons


def suggest_labels_for_unlabeled(
    messages: list[dict[str, Any]],
    min_score: float = 35,
) -> dict[str, list[dict[str, Any]]]:
    """
    Suggest existing labels for unlabeled messages.

    Args:
        messages: List of all message dictionaries.
        min_score: Minimum match score to suggest (0-100).

    Returns:
        Dictionary mapping label names to lists of suggested messages.
    """
    from xobliam.smart_delete import filter_unlabeled_messages

    # Build profiles from labeled messages
    profiles = build_all_label_profiles(messages)

    if not profiles:
        return {}

    # Get unlabeled messages
    unlabeled = filter_unlabeled_messages(messages)

    # Score each unlabeled message against each profile
    suggestions = defaultdict(list)

    for msg in unlabeled:
        best_label = None
        best_score = 0
        best_reasons = []

        for label_name, profile in profiles.items():
            score, reasons = score_message_against_profile(msg, profile)
            if score >= min_score and score > best_score:
                best_label = label_name
                best_score = score
                best_reasons = reasons

        if best_label:
            suggestions[best_label].append({
                "message_id": msg.get("message_id"),
                "sender": msg.get("sender", ""),
                "subject": msg.get("subject", ""),
                "score": best_score,
                "reasons": best_reasons,
            })

    # Sort suggestions by score within each label
    for label in suggestions:
        suggestions[label].sort(key=lambda x: x["score"], reverse=True)

    # Convert to regular dict and sort by match count
    result = dict(sorted(
        suggestions.items(),
        key=lambda x: len(x[1]),
        reverse=True,
    ))

    return result


def get_suggestion_summary(
    messages: list[dict[str, Any]],
    min_score: float = 35,
) -> dict[str, Any]:
    """
    Get a summary of label suggestions for unlabeled emails.

    Returns:
        Dictionary with suggestion counts and details.
    """
    suggestions = suggest_labels_for_unlabeled(messages, min_score)

    total_suggestions = sum(len(msgs) for msgs in suggestions.values())

    # Group by sender within each label
    label_details = {}
    for label, msgs in suggestions.items():
        by_sender = defaultdict(list)
        for msg in msgs:
            by_sender[msg["sender"]].append(msg)

        sender_summary = []
        for sender, sender_msgs in sorted(by_sender.items(), key=lambda x: len(x[1]), reverse=True):
            sender_summary.append({
                "sender": sender,
                "count": len(sender_msgs),
                "reasons": sender_msgs[0]["reasons"] if sender_msgs else [],
                "message_ids": [m["message_id"] for m in sender_msgs],
            })

        label_details[label] = {
            "total_matches": len(msgs),
            "unique_senders": len(by_sender),
            "senders": sender_summary,
        }

    return {
        "total_suggestions": total_suggestions,
        "label_count": len(suggestions),
        "labels": label_details,
    }
