"""Analytics module for email pattern analysis."""

from .daily_distribution import (
    get_busiest_dates,
    get_calendar_distribution,
    get_day_of_week_distribution,
)
from .label_audit import (
    find_redundant_labels,
    find_split_candidates,
    get_label_stats,
    suggest_new_labels,
)
from .open_rate import calculate_open_rate, get_sender_engagement
from .sender_analysis import get_frequent_senders, get_sender_domains
from .time_patterns import analyze_time_patterns, get_top_senders_per_slot

__all__ = [
    "analyze_time_patterns",
    "get_top_senders_per_slot",
    "calculate_open_rate",
    "get_sender_engagement",
    "get_frequent_senders",
    "get_sender_domains",
    "get_day_of_week_distribution",
    "get_calendar_distribution",
    "get_busiest_dates",
    "find_redundant_labels",
    "find_split_candidates",
    "get_label_stats",
    "suggest_new_labels",
]
