"""Label audit and optimization analysis."""

from collections import defaultdict
from itertools import combinations
from typing import Any


# System labels to exclude from user label analysis
SYSTEM_LABELS = {
    "INBOX",
    "SENT",
    "DRAFT",
    "SPAM",
    "TRASH",
    "UNREAD",
    "STARRED",
    "IMPORTANT",
    "CHAT",
    "CATEGORY_PERSONAL",
    "CATEGORY_SOCIAL",
    "CATEGORY_PROMOTIONS",
    "CATEGORY_UPDATES",
    "CATEGORY_FORUMS",
}


def _is_user_label(label: str) -> bool:
    """Check if a label is a user-created label (not system)."""
    return label not in SYSTEM_LABELS and not label.startswith("CATEGORY_")


def _get_user_labels(labels: list[str]) -> list[str]:
    """Filter to only user-created labels."""
    return [l for l in labels if _is_user_label(l)]


def _extract_domain(sender: str) -> str:
    """Extract domain from sender email."""
    if "@" in sender:
        return sender.split("@")[-1].lower()
    return ""


def _has_unsubscribe_signal(msg: dict[str, Any]) -> bool:
    """Check if message appears to be marketing (has unsubscribe indicators)."""
    subject = (msg.get("subject") or "").lower()
    snippet = (msg.get("snippet") or "").lower()
    labels = msg.get("labels", [])

    # Check for promotional category
    if "CATEGORY_PROMOTIONS" in labels:
        return True

    # Check for unsubscribe keywords
    unsubscribe_keywords = ["unsubscribe", "opt out", "opt-out", "preferences", "manage subscriptions"]
    text = f"{subject} {snippet}"
    return any(kw in text for kw in unsubscribe_keywords)


def get_label_stats(
    messages: list[dict[str, Any]],
    all_labels: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Get statistics for each label including usage counts and percentages.

    Args:
        messages: List of message dictionaries.
        all_labels: Optional list of all labels from cache (to include abandoned labels).

    Returns:
        Dictionary with label statistics and summary info.
    """
    label_data: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "unread": 0, "senders": set(), "domains": set()}
    )

    # Pre-populate with all known labels (including abandoned ones)
    if all_labels:
        for label_info in all_labels:
            label_name = label_info.get("name", "")
            label_type = label_info.get("type", "")

            if label_type == "system":
                continue
            if not _is_user_label(label_name):
                continue
            if label_name:
                _ = label_data[label_name]

    total_messages = len(messages)
    unlabeled_count = 0

    for msg in messages:
        labels = msg.get("labels", [])
        sender = msg.get("sender", "")
        domain = _extract_domain(sender)
        is_unread = msg.get("is_unread", False)

        user_labels = _get_user_labels(labels)
        if not user_labels:
            unlabeled_count += 1

        for label in labels:
            label_data[label]["count"] += 1
            label_data[label]["senders"].add(sender)
            if domain:
                label_data[label]["domains"].add(domain)
            if is_unread:
                label_data[label]["unread"] += 1

    results = []
    for label, data in label_data.items():
        count = data["count"]
        unread = data["unread"]
        unique_senders = len(data["senders"])
        unique_domains = len(data["domains"])

        results.append({
            "label": label,
            "count": count,
            "percentage": round((count / total_messages) * 100, 2) if total_messages > 0 else 0.0,
            "unread": unread,
            "read_rate": round(((count - unread) / count) * 100, 2) if count > 0 else 0.0,
            "unique_senders": unique_senders,
            "unique_domains": unique_domains,
            "is_system": not _is_user_label(label),
        })

    sorted_labels = sorted(results, key=lambda x: x["count"], reverse=True)

    return {
        "labels": sorted_labels,
        "total_messages": total_messages,
        "unlabeled_count": unlabeled_count,
        "unlabeled_percentage": round((unlabeled_count / total_messages) * 100, 2)
        if total_messages > 0 else 0.0,
    }


def calculate_coherence_scores(
    messages: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Calculate coherence score for each label (0-100).

    High coherence = emails are from same sender/domain (focused label)
    Low coherence = many different unrelated senders (too broad)

    Args:
        messages: List of message dictionaries.

    Returns:
        Dictionary mapping label names to coherence data.
    """
    label_data: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "senders": set(), "domains": set(), "top_senders": defaultdict(int)}
    )

    for msg in messages:
        labels = msg.get("labels", [])
        sender = msg.get("sender", "")
        domain = _extract_domain(sender)

        for label in _get_user_labels(labels):
            label_data[label]["count"] += 1
            label_data[label]["senders"].add(sender)
            if domain:
                label_data[label]["domains"].add(domain)
            label_data[label]["top_senders"][sender] += 1

    results = {}
    for label, data in label_data.items():
        count = data["count"]
        if count == 0:
            continue

        unique_senders = len(data["senders"])
        unique_domains = len(data["domains"])

        # Calculate coherence based on concentration
        # Single sender = 100, many senders relative to count = lower score
        if unique_senders == 1:
            coherence = 100
        elif unique_domains == 1:
            coherence = 90  # Same domain is still fairly coherent
        else:
            # Score based on how concentrated the senders are
            # If ratio of senders to messages is low, it's more coherent
            sender_ratio = unique_senders / count
            domain_ratio = unique_domains / count

            # Lower ratio = higher coherence
            # ratio of 1.0 means every email is from different sender = low coherence
            # ratio of 0.1 means 10 emails per sender on average = high coherence
            coherence = max(0, min(100, int((1 - sender_ratio) * 70 + (1 - domain_ratio) * 30)))

        # Find top sender
        top_senders = sorted(data["top_senders"].items(), key=lambda x: x[1], reverse=True)[:3]
        top_sender_pct = (top_senders[0][1] / count * 100) if top_senders else 0

        results[label] = {
            "coherence_score": coherence,
            "unique_senders": unique_senders,
            "unique_domains": unique_domains,
            "count": count,
            "top_sender": top_senders[0][0] if top_senders else None,
            "top_sender_pct": round(top_sender_pct, 1),
            "assessment": _get_coherence_assessment(coherence, unique_senders, count),
        }

    return results


def _get_coherence_assessment(coherence: int, unique_senders: int, count: int) -> str:
    """Get human-readable coherence assessment."""
    if coherence >= 90:
        return "Highly focused"
    elif coherence >= 70:
        return "Well organized"
    elif coherence >= 50:
        return "Moderately broad"
    elif coherence >= 30:
        return "Consider splitting"
    else:
        return "Too broad - split recommended"


def find_label_overlaps(
    messages: list[dict[str, Any]],
    min_overlap: float = 0.50,
) -> list[dict[str, Any]]:
    """
    Find label pairs with significant overlap.

    Args:
        messages: List of message dictionaries.
        min_overlap: Minimum overlap percentage (0.0 to 1.0).

    Returns:
        List of overlapping label pairs with merge recommendations.
    """
    label_counts: dict[str, int] = defaultdict(int)
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    label_messages: dict[str, set] = defaultdict(set)

    for i, msg in enumerate(messages):
        labels = msg.get("labels", [])
        user_labels = _get_user_labels(labels)

        for label in user_labels:
            label_counts[label] += 1
            label_messages[label].add(i)

        for pair in combinations(sorted(user_labels), 2):
            pair_counts[pair] += 1

    overlaps = []
    for (label_a, label_b), pair_count in pair_counts.items():
        count_a = label_counts[label_a]
        count_b = label_counts[label_b]

        if count_a == 0 or count_b == 0:
            continue

        # Calculate overlap as percentage of smaller label
        min_count = min(count_a, count_b)
        overlap_rate = pair_count / min_count

        if overlap_rate >= min_overlap:
            # Determine which label is the subset
            if count_a <= count_b:
                smaller, larger = label_a, label_b
                smaller_count, larger_count = count_a, count_b
            else:
                smaller, larger = label_b, label_a
                smaller_count, larger_count = count_b, count_a

            # Generate recommendation
            if overlap_rate >= 0.95:
                action = "MERGE"
                recommendation = f"{smaller} and {larger} are nearly identical ({overlap_rate:.0%} overlap)"
            elif overlap_rate >= 0.80:
                action = "MERGE"
                recommendation = f"{smaller} and {larger} share {overlap_rate:.0%} of emails — consider merging"
            else:
                action = "REVIEW"
                recommendation = f"{smaller} and {larger} share {overlap_rate:.0%} of emails"

            overlaps.append({
                "label_a": label_a,
                "label_b": label_b,
                "count_a": count_a,
                "count_b": count_b,
                "overlap_count": pair_count,
                "overlap_rate": round(overlap_rate * 100, 1),
                "action": action,
                "recommendation": recommendation,
            })

    return sorted(overlaps, key=lambda x: x["overlap_rate"], reverse=True)


def analyze_engagement_efficiency(
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compare each label's read rate to inbox average.

    Args:
        messages: List of message dictionaries.

    Returns:
        Dictionary with engagement analysis per label and summary.
    """
    # Calculate inbox average
    total_count = len(messages)
    total_unread = sum(1 for m in messages if m.get("is_unread", False))
    inbox_read_rate = ((total_count - total_unread) / total_count * 100) if total_count > 0 else 0

    # Calculate per-label stats
    label_data: dict[str, dict] = defaultdict(lambda: {"count": 0, "unread": 0})

    for msg in messages:
        labels = msg.get("labels", [])
        is_unread = msg.get("is_unread", False)

        for label in _get_user_labels(labels):
            label_data[label]["count"] += 1
            if is_unread:
                label_data[label]["unread"] += 1

    results = {}
    working_well = []
    needs_attention = []

    for label, data in label_data.items():
        count = data["count"]
        if count == 0:
            continue

        unread = data["unread"]
        read_rate = (count - unread) / count * 100
        diff = read_rate - inbox_read_rate

        efficiency = {
            "count": count,
            "read_rate": round(read_rate, 1),
            "inbox_average": round(inbox_read_rate, 1),
            "difference": round(diff, 1),
        }

        if diff >= 10:
            efficiency["status"] = "above_average"
            efficiency["assessment"] = f"You read {read_rate:.0f}% vs {inbox_read_rate:.0f}% average — this label is working"
            if count >= 10:
                working_well.append(label)
        elif diff >= -10:
            efficiency["status"] = "average"
            efficiency["assessment"] = f"Read rate ({read_rate:.0f}%) is near inbox average ({inbox_read_rate:.0f}%)"
        else:
            efficiency["status"] = "below_average"
            if read_rate < 10 and count >= 20:
                efficiency["assessment"] = f"You read {read_rate:.0f}% of these — consider unsubscribing or deleting"
                needs_attention.append(label)
            else:
                efficiency["assessment"] = f"Read rate ({read_rate:.0f}%) is below inbox average ({inbox_read_rate:.0f}%)"

        results[label] = efficiency

    return {
        "labels": results,
        "inbox_read_rate": round(inbox_read_rate, 1),
        "working_well": working_well,
        "needs_attention": needs_attention,
    }


def generate_recommendations(
    messages: list[dict[str, Any]],
    all_labels: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Generate prioritized actionable recommendations for label optimization.

    Args:
        messages: List of message dictionaries.
        all_labels: Optional list of all labels from cache.

    Returns:
        Prioritized list of recommendations.
    """
    recommendations = []

    # Get all analysis data
    overlaps = find_label_overlaps(messages, min_overlap=0.80)
    coherence = calculate_coherence_scores(messages)
    engagement = analyze_engagement_efficiency(messages)
    stats = get_label_stats(messages, all_labels=all_labels)

    # 1. Identical/near-identical label pairs (highest priority)
    for overlap in overlaps:
        if overlap["overlap_rate"] >= 95:
            recommendations.append({
                "priority": 1,
                "action": "MERGE",
                "label": f"{overlap['label_a']} + {overlap['label_b']}",
                "reason": f"Identical ({overlap['overlap_rate']:.0f}% overlap)",
                "detail": overlap["recommendation"],
                "impact": "high",
            })
        elif overlap["overlap_rate"] >= 80:
            recommendations.append({
                "priority": 2,
                "action": "MERGE",
                "label": f"{overlap['label_a']} + {overlap['label_b']}",
                "reason": f"High overlap ({overlap['overlap_rate']:.0f}%)",
                "detail": overlap["recommendation"],
                "impact": "medium",
            })

    # 2. Zero read rate labels with significant volume (filter bugs or unsubscribe candidates)
    for label, eng in engagement["labels"].items():
        if eng["read_rate"] == 0 and eng["count"] >= 10:
            coh = coherence.get(label, {})
            if coh.get("unique_senders", 0) == 1:
                recommendations.append({
                    "priority": 2,
                    "action": "FIX",
                    "label": label,
                    "reason": f"0% read rate, single sender",
                    "detail": f"May be a filter bug — {eng['count']} emails never opened",
                    "impact": "medium",
                })
            else:
                recommendations.append({
                    "priority": 3,
                    "action": "REVIEW",
                    "label": label,
                    "reason": f"0% read rate",
                    "detail": f"{eng['count']} emails at 0% read — unsubscribe or delete?",
                    "impact": "medium",
                })

    # 3. Low engagement labels (< 10% read rate with volume)
    for label in engagement["needs_attention"]:
        eng = engagement["labels"].get(label, {})
        if eng.get("read_rate", 100) > 0:  # Skip 0% (handled above)
            recommendations.append({
                "priority": 4,
                "action": "REVIEW",
                "label": label,
                "reason": f"Low engagement ({eng['read_rate']:.0f}% read)",
                "detail": f"{eng['count']} emails — consider unsubscribing",
                "impact": "low",
            })

    # 4. Abandoned labels
    user_labels = [l for l in stats["labels"] if not l["is_system"]]
    abandoned = [l for l in user_labels if l["count"] == 0]
    if abandoned:
        recommendations.append({
            "priority": 5,
            "action": "CLEANUP",
            "label": f"{len(abandoned)} abandoned labels",
            "reason": "No emails in timeframe",
            "detail": f"Labels: {', '.join(l['label'] for l in abandoned[:5])}" +
                      (f" and {len(abandoned) - 5} more" if len(abandoned) > 5 else ""),
            "impact": "low",
        })

    # 5. Low coherence labels (too broad)
    for label, coh in coherence.items():
        if coh["coherence_score"] < 30 and coh["count"] >= 20:
            recommendations.append({
                "priority": 6,
                "action": "SPLIT",
                "label": label,
                "reason": f"Low coherence ({coh['coherence_score']})",
                "detail": f"{coh['unique_senders']} different senders — consider splitting",
                "impact": "low",
            })

    # Sort by priority
    return sorted(recommendations, key=lambda x: x["priority"])


def get_label_health_summary(
    messages: list[dict[str, Any]],
    all_labels: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Get overall label health summary.

    Args:
        messages: List of message dictionaries.
        all_labels: Optional list of all labels from cache.

    Returns:
        Summary of label health metrics.
    """
    stats = get_label_stats(messages, all_labels=all_labels)
    engagement = analyze_engagement_efficiency(messages)
    overlaps = find_label_overlaps(messages, min_overlap=0.80)

    user_labels = [l for l in stats["labels"] if not l["is_system"]]

    # Count labels by health status
    working_well = 0
    needs_attention = 0
    abandoned = 0

    for label in user_labels:
        if label["count"] == 0:
            abandoned += 1
        elif label["read_rate"] >= 30:
            working_well += 1
        elif label["read_rate"] < 10 and label["count"] >= 20:
            needs_attention += 1

    redundant_pairs = len([o for o in overlaps if o["overlap_rate"] >= 80])

    return {
        "total_user_labels": len(user_labels),
        "working_well": working_well,
        "needs_attention": needs_attention,
        "redundant_pairs": redundant_pairs,
        "abandoned": abandoned,
        "inbox_read_rate": engagement["inbox_read_rate"],
    }


def find_redundant_labels(
    messages: list[dict[str, Any]],
    threshold: float = 0.90,
) -> list[dict[str, Any]]:
    """
    Find label pairs that always (or nearly always) co-occur.
    Wrapper around find_label_overlaps for backward compatibility.

    Args:
        messages: List of message dictionaries.
        threshold: Co-occurrence rate threshold (0.0 to 1.0).

    Returns:
        List of redundancy candidates.
    """
    overlaps = find_label_overlaps(messages, min_overlap=threshold)

    # Convert to old format for compatibility
    return [{
        "label_a": o["label_a"],
        "label_b": o["label_b"],
        "count_a": o["count_a"],
        "count_b": o["count_b"],
        "pair_count": o["overlap_count"],
        "co_occurrence_rate": o["overlap_rate"],
        "suggestion": o["recommendation"],
    } for o in overlaps]


def find_split_candidates(
    messages: list[dict[str, Any]],
    min_count: int = 20,
    min_unique_senders: int = 10,
) -> list[dict[str, Any]]:
    """
    Find labels that might benefit from splitting (low coherence).

    Args:
        messages: List of message dictionaries.
        min_count: Minimum message count to consider.
        min_unique_senders: Minimum unique senders to be a split candidate.

    Returns:
        List of split candidates.
    """
    coherence = calculate_coherence_scores(messages)

    candidates = []
    for label, data in coherence.items():
        if data["count"] >= min_count and data["unique_senders"] >= min_unique_senders:
            if data["coherence_score"] < 50:  # Low coherence
                candidates.append({
                    "label": label,
                    "count": data["count"],
                    "unique_senders": data["unique_senders"],
                    "coherence_score": data["coherence_score"],
                    "sender_diversity": round(data["unique_senders"] / data["count"], 2),
                    "suggestion": f"Label '{label}' has low coherence ({data['coherence_score']}) — "
                                  f"{data['unique_senders']} different senders",
                })

    return sorted(candidates, key=lambda x: x["coherence_score"])


def suggest_new_labels(
    messages: list[dict[str, Any]],
    min_cluster_size: int = 5,
    min_read_rate: float = 0.30,
) -> list[dict[str, Any]]:
    """
    Suggest new labels for unlabeled emails worth organizing.

    Only suggests labels for emails that:
    - Have high engagement (read rate > 30%)
    - Don't appear to be marketing (no unsubscribe signals)

    Args:
        messages: List of message dictionaries.
        min_cluster_size: Minimum emails from same domain to suggest.
        min_read_rate: Minimum read rate to consider (0.0 to 1.0).

    Returns:
        List of label suggestions for engaged, non-marketing emails.
    """
    # Find unlabeled messages
    unlabeled_by_domain: dict[str, list] = defaultdict(list)

    for msg in messages:
        labels = msg.get("labels", [])
        user_labels = _get_user_labels(labels)

        # Skip if already has user labels
        if user_labels:
            continue

        # Skip marketing emails
        if _has_unsubscribe_signal(msg):
            continue

        sender = msg.get("sender", "")
        domain = _extract_domain(sender)
        if domain:
            unlabeled_by_domain[domain].append(msg)

    suggestions = []
    for domain, msgs in unlabeled_by_domain.items():
        if len(msgs) < min_cluster_size:
            continue

        # Calculate read rate for this cluster
        read_count = sum(1 for m in msgs if not m.get("is_unread", False))
        read_rate = read_count / len(msgs)

        # Skip low engagement clusters
        if read_rate < min_read_rate:
            continue

        # Generate label name
        label_name = domain.split(".")[0].title()

        suggestions.append({
            "suggested_label": label_name,
            "domain": domain,
            "message_count": len(msgs),
            "read_rate": round(read_rate * 100, 1),
            "sample_subjects": [m.get("subject", "")[:60] for m in msgs[:3]],
        })

    return sorted(suggestions, key=lambda x: x["message_count"], reverse=True)
