"""Find deletion candidates based on safety scores."""

from typing import Any

from .safety_scorer import calculate_safety_score, get_score_breakdown


# Safety tiers
SAFETY_TIERS = {
    "very_safe": {"min": 90, "max": 100, "color": "green", "label": "Very Safe"},
    "likely_safe": {"min": 70, "max": 89, "color": "yellow", "label": "Likely Safe"},
    "review": {"min": 50, "max": 69, "color": "orange", "label": "Review Carefully"},
    "keep": {"min": 0, "max": 49, "color": "red", "label": "Keep"},
}


def get_safety_tier(score: int) -> dict[str, Any]:
    """
    Get the safety tier for a given score.

    Args:
        score: Safety score from 0-100.

    Returns:
        Tier dictionary with name, color, and label.
    """
    for tier_name, tier in SAFETY_TIERS.items():
        if tier["min"] <= score <= tier["max"]:
            return {
                "name": tier_name,
                "color": tier["color"],
                "label": tier["label"],
                "min": tier["min"],
                "max": tier["max"],
            }

    return SAFETY_TIERS["keep"]


def find_deletion_candidates(
    messages: list[dict[str, Any]],
    user_context: dict[str, Any] | None = None,
    min_score: int = 50,
    include_breakdown: bool = False,
) -> list[dict[str, Any]]:
    """
    Find messages that are candidates for deletion.

    Args:
        messages: List of message dictionaries.
        user_context: User context for scoring.
        min_score: Minimum safety score to include.
        include_breakdown: Whether to include score breakdown.

    Returns:
        List of candidates sorted by score (highest first).
    """
    candidates = []

    for msg in messages:
        score = calculate_safety_score(msg, user_context)

        if score >= min_score:
            candidate = {
                "message_id": msg.get("message_id"),
                "thread_id": msg.get("thread_id"),
                "sender": msg.get("sender"),
                "subject": msg.get("subject"),
                "date": msg.get("date"),
                "score": score,
                "tier": get_safety_tier(score),
                "is_unread": msg.get("is_unread", False),
                "has_attachments": msg.get("has_attachments", False),
                "labels": msg.get("labels", []),
            }

            if include_breakdown:
                candidate["breakdown"] = get_score_breakdown(msg, user_context)

            candidates.append(candidate)

    return sorted(candidates, key=lambda x: x["score"], reverse=True)


def find_candidates_by_tier(
    messages: list[dict[str, Any]],
    user_context: dict[str, Any] | None = None,
    tier: str = "very_safe",
) -> list[dict[str, Any]]:
    """
    Find candidates matching a specific safety tier.

    Args:
        messages: List of message dictionaries.
        user_context: User context for scoring.
        tier: Tier name ('very_safe', 'likely_safe', 'review', 'keep').

    Returns:
        List of candidates in the specified tier.
    """
    tier_config = SAFETY_TIERS.get(tier)
    if not tier_config:
        return []

    min_score = tier_config["min"]
    max_score = tier_config["max"]

    candidates = find_deletion_candidates(
        messages,
        user_context,
        min_score=min_score,
    )

    return [c for c in candidates if c["score"] <= max_score]


def get_deletion_summary(
    messages: list[dict[str, Any]],
    user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get a summary of deletion candidates by tier.

    Args:
        messages: List of message dictionaries.
        user_context: User context for scoring.

    Returns:
        Dictionary with tier counts and totals.
    """
    tier_counts = {tier: 0 for tier in SAFETY_TIERS}

    for msg in messages:
        score = calculate_safety_score(msg, user_context)
        tier = get_safety_tier(score)
        tier_counts[tier["name"]] += 1

    return {
        "total_messages": len(messages),
        "tier_counts": tier_counts,
        "deletable": tier_counts.get("very_safe", 0) + tier_counts.get("likely_safe", 0),
        "needs_review": tier_counts.get("review", 0),
        "keep": tier_counts.get("keep", 0),
    }


def find_candidates_by_sender(
    messages: list[dict[str, Any]],
    user_context: dict[str, Any] | None = None,
    min_score: int = 70,
) -> dict[str, list[dict[str, Any]]]:
    """
    Group deletion candidates by sender.

    Args:
        messages: List of message dictionaries.
        user_context: User context for scoring.
        min_score: Minimum safety score.

    Returns:
        Dictionary mapping sender to list of candidates.
    """
    candidates = find_deletion_candidates(messages, user_context, min_score)

    by_sender: dict[str, list] = {}
    for candidate in candidates:
        sender = candidate["sender"]
        if sender not in by_sender:
            by_sender[sender] = []
        by_sender[sender].append(candidate)

    return by_sender


def get_bulk_delete_recommendations(
    messages: list[dict[str, Any]],
    user_context: dict[str, Any] | None = None,
    min_sender_count: int = 5,
    min_avg_score: float = 80.0,
) -> list[dict[str, Any]]:
    """
    Find senders whose emails can be bulk deleted.

    Args:
        messages: List of message dictionaries.
        user_context: User context for scoring.
        min_sender_count: Minimum messages from sender.
        min_avg_score: Minimum average safety score.

    Returns:
        List of sender recommendations for bulk deletion.
    """
    sender_scores: dict[str, list[int]] = {}

    for msg in messages:
        sender = msg.get("sender", "")
        score = calculate_safety_score(msg, user_context)
        if sender not in sender_scores:
            sender_scores[sender] = []
        sender_scores[sender].append(score)

    recommendations = []
    for sender, scores in sender_scores.items():
        if len(scores) >= min_sender_count:
            avg_score = sum(scores) / len(scores)
            if avg_score >= min_avg_score:
                recommendations.append({
                    "sender": sender,
                    "count": len(scores),
                    "avg_score": round(avg_score, 2),
                    "min_score": min(scores),
                    "max_score": max(scores),
                    "recommendation": "Bulk delete recommended",
                })

    return sorted(recommendations, key=lambda x: x["avg_score"], reverse=True)


def estimate_cleanup_impact(
    messages: list[dict[str, Any]],
    user_context: dict[str, Any] | None = None,
    min_score: int = 70,
) -> dict[str, Any]:
    """
    Estimate the impact of cleanup at different score thresholds.

    Args:
        messages: List of message dictionaries.
        user_context: User context for scoring.
        min_score: Base minimum score to consider.

    Returns:
        Dictionary with impact at different thresholds.
    """
    thresholds = [90, 80, 70, 60, 50]
    impacts = {}

    for threshold in thresholds:
        candidates = find_deletion_candidates(messages, user_context, min_score=threshold)
        impacts[threshold] = {
            "count": len(candidates),
            "percentage": round((len(candidates) / len(messages)) * 100, 2)
            if messages
            else 0.0,
        }

    return {
        "total_messages": len(messages),
        "impacts_by_threshold": impacts,
        "recommended_threshold": 70,
    }
