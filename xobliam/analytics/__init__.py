"""Analytics module for email pattern analysis."""

from .daily_distribution import (
    get_busiest_dates,
    get_calendar_distribution,
    get_day_of_week_distribution,
)
from .label_audit import (
    analyze_engagement_efficiency,
    calculate_coherence_scores,
    find_label_overlaps,
    find_redundant_labels,
    find_split_candidates,
    generate_recommendations,
    get_label_health_summary,
    get_label_sender_breakdown,
    get_label_stats,
    suggest_new_labels,
)
from .open_rate import calculate_open_rate, get_sender_engagement
from .sender_analysis import get_frequent_senders, get_sender_domains
from .time_patterns import (
    analyze_time_patterns,
    get_day_hourly_breakdown,
    get_top_senders_per_slot,
)

__all__ = [
    "analyze_engagement_efficiency",
    "analyze_time_patterns",
    "calculate_coherence_scores",
    "calculate_open_rate",
    "find_label_overlaps",
    "find_redundant_labels",
    "find_split_candidates",
    "generate_recommendations",
    "get_busiest_dates",
    "get_calendar_distribution",
    "get_day_hourly_breakdown",
    "get_day_of_week_distribution",
    "get_frequent_senders",
    "get_label_health_summary",
    "get_label_sender_breakdown",
    "get_label_stats",
    "get_sender_domains",
    "get_sender_engagement",
    "get_top_senders_per_slot",
    "suggest_new_labels",
]
