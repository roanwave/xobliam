"""Label audit and optimization suggestions."""

from collections import defaultdict
from itertools import combinations
from typing import Any


def find_redundant_labels(
    messages: list[dict[str, Any]],
    threshold: float = 0.90,
) -> list[dict[str, Any]]:
    """
    Find label pairs that always (or nearly always) co-occur.

    Args:
        messages: List of message dictionaries with 'labels' field.
        threshold: Co-occurrence rate threshold (0.0 to 1.0).

    Returns:
        List of redundancy candidates with label pairs and rates.
    """
    # Count individual label occurrences
    label_counts: dict[str, int] = defaultdict(int)
    # Count pair co-occurrences
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)

    for msg in messages:
        labels = msg.get("labels", [])
        # Filter to user labels (skip system labels like INBOX, SENT, etc.)
        user_labels = [
            l
            for l in labels
            if not l.startswith("CATEGORY_")
            and l not in ("INBOX", "SENT", "DRAFT", "SPAM", "TRASH", "UNREAD", "STARRED", "IMPORTANT")
        ]

        for label in user_labels:
            label_counts[label] += 1

        # Count all pairs
        for pair in combinations(sorted(user_labels), 2):
            pair_counts[pair] += 1

    # Find pairs with high co-occurrence
    redundant = []
    for (label_a, label_b), pair_count in pair_counts.items():
        count_a = label_counts[label_a]
        count_b = label_counts[label_b]

        if count_a == 0 or count_b == 0:
            continue

        # Co-occurrence rate relative to smaller label
        min_count = min(count_a, count_b)
        co_occurrence_rate = pair_count / min_count

        if co_occurrence_rate >= threshold:
            redundant.append(
                {
                    "label_a": label_a,
                    "label_b": label_b,
                    "count_a": count_a,
                    "count_b": count_b,
                    "pair_count": pair_count,
                    "co_occurrence_rate": round(co_occurrence_rate * 100, 2),
                    "suggestion": f"Consider merging '{label_a}' and '{label_b}' "
                    f"({co_occurrence_rate:.0%} co-occurrence)",
                }
            )

    return sorted(redundant, key=lambda x: x["co_occurrence_rate"], reverse=True)


def find_split_candidates(
    messages: list[dict[str, Any]],
    min_count: int = 20,
    min_unique_senders: int = 10,
) -> list[dict[str, Any]]:
    """
    Find labels that might benefit from splitting (high volume + diverse senders).

    Args:
        messages: List of message dictionaries.
        min_count: Minimum message count to consider.
        min_unique_senders: Minimum unique senders to be a split candidate.

    Returns:
        List of split candidates with label stats.
    """
    label_data: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "senders": set(), "subjects": []}
    )

    for msg in messages:
        labels = msg.get("labels", [])
        sender = msg.get("sender", "")
        subject = msg.get("subject", "")

        # Filter to user labels
        user_labels = [
            l
            for l in labels
            if not l.startswith("CATEGORY_")
            and l not in ("INBOX", "SENT", "DRAFT", "SPAM", "TRASH", "UNREAD", "STARRED", "IMPORTANT")
        ]

        for label in user_labels:
            label_data[label]["count"] += 1
            label_data[label]["senders"].add(sender)
            if len(label_data[label]["subjects"]) < 100:  # Limit for memory
                label_data[label]["subjects"].append(subject)

    candidates = []
    for label, data in label_data.items():
        unique_senders = len(data["senders"])

        if data["count"] >= min_count and unique_senders >= min_unique_senders:
            candidates.append(
                {
                    "label": label,
                    "count": data["count"],
                    "unique_senders": unique_senders,
                    "sender_diversity": round(unique_senders / data["count"], 2),
                    "suggestion": f"Label '{label}' has {unique_senders} unique senders - "
                    "consider splitting by sender type",
                }
            )

    return sorted(candidates, key=lambda x: x["unique_senders"], reverse=True)


def suggest_new_labels(
    messages: list[dict[str, Any]],
    min_cluster_size: int = 5,
) -> list[dict[str, Any]]:
    """
    Suggest new labels based on patterns in unlabeled emails.

    Args:
        messages: List of message dictionaries.
        min_cluster_size: Minimum emails from same domain to suggest label.

    Returns:
        List of label suggestions.
    """
    # Find unlabeled messages (only system labels)
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

    unlabeled_by_domain: dict[str, list] = defaultdict(list)

    for msg in messages:
        labels = set(msg.get("labels", []))

        # Check if only system labels
        has_user_labels = bool(labels - system_labels)

        if not has_user_labels:
            sender = msg.get("sender", "")
            if "@" in sender:
                domain = sender.split("@")[1]
                unlabeled_by_domain[domain].append(msg)

    suggestions = []
    for domain, msgs in unlabeled_by_domain.items():
        if len(msgs) >= min_cluster_size:
            # Analyze subjects to suggest label name
            subjects = [m.get("subject", "") for m in msgs]
            common_words = _find_common_words(subjects)

            label_name = domain.split(".")[0].title()
            if common_words:
                label_name = f"{label_name}/{common_words[0]}"

            suggestions.append(
                {
                    "suggested_label": label_name,
                    "domain": domain,
                    "message_count": len(msgs),
                    "sample_subjects": subjects[:5],
                    "common_words": common_words[:5],
                }
            )

    return sorted(suggestions, key=lambda x: x["message_count"], reverse=True)


def _find_common_words(subjects: list[str], min_occurrence: int = 3) -> list[str]:
    """Find commonly occurring words across subjects."""
    word_counts: dict[str, int] = defaultdict(int)

    stop_words = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "and",
        "but",
        "if",
        "or",
        "because",
        "until",
        "while",
        "your",
        "you",
        "re",
        "fwd",
    }

    for subject in subjects:
        words = subject.lower().split()
        for word in words:
            # Clean word
            word = "".join(c for c in word if c.isalnum())
            if len(word) > 2 and word not in stop_words:
                word_counts[word] += 1

    return [
        word
        for word, count in sorted(
            word_counts.items(), key=lambda x: x[1], reverse=True
        )
        if count >= min_occurrence
    ]


def get_label_stats(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Get statistics for each label.

    Args:
        messages: List of message dictionaries.

    Returns:
        List of label statistics.
    """
    label_data: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "unread": 0, "senders": set()}
    )

    for msg in messages:
        labels = msg.get("labels", [])
        sender = msg.get("sender", "")
        is_unread = msg.get("is_unread", False)

        for label in labels:
            label_data[label]["count"] += 1
            label_data[label]["senders"].add(sender)
            if is_unread:
                label_data[label]["unread"] += 1

    results = []
    for label, data in label_data.items():
        count = data["count"]
        unread = data["unread"]
        unique_senders = len(data["senders"])

        results.append(
            {
                "label": label,
                "count": count,
                "unread": unread,
                "read_rate": round(((count - unread) / count) * 100, 2)
                if count > 0
                else 0.0,
                "unique_senders": unique_senders,
            }
        )

    return sorted(results, key=lambda x: x["count"], reverse=True)
