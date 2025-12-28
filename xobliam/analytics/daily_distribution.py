"""Daily email distribution analysis."""

from collections import defaultdict
from datetime import datetime
from typing import Any

import pandas as pd


def get_day_of_week_distribution(
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Get email distribution by day of week.

    Args:
        messages: List of message dictionaries with 'date' field.

    Returns:
        Dictionary with day counts and statistics.
    """
    day_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    counts = [0] * 7

    for msg in messages:
        date_str = msg.get("date")
        if not date_str:
            continue

        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            counts[dt.weekday()] += 1
        except (ValueError, AttributeError):
            continue

    total = sum(counts)
    busiest_idx = counts.index(max(counts)) if counts else 0
    quietest_idx = counts.index(min(counts)) if counts else 0

    distribution = []
    for i, name in enumerate(day_names):
        distribution.append(
            {
                "day": i,
                "day_name": name,
                "count": counts[i],
                "percentage": round((counts[i] / total) * 100, 2) if total > 0 else 0.0,
            }
        )

    return {
        "distribution": distribution,
        "busiest_day": day_names[busiest_idx],
        "busiest_count": counts[busiest_idx],
        "quietest_day": day_names[quietest_idx],
        "quietest_count": counts[quietest_idx],
        "weekday_total": sum(counts[:5]),
        "weekend_total": sum(counts[5:]),
        "weekday_avg": round(sum(counts[:5]) / 5, 2),
        "weekend_avg": round(sum(counts[5:]) / 2, 2),
    }


def get_calendar_distribution(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Get email distribution by calendar date.

    Args:
        messages: List of message dictionaries with 'date' field.

    Returns:
        List of date distribution dicts, sorted by date.
    """
    date_counts: dict[str, int] = defaultdict(int)

    for msg in messages:
        date_str = msg.get("date")
        if not date_str:
            continue

        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            date_key = dt.strftime("%Y-%m-%d")
            date_counts[date_key] += 1
        except (ValueError, AttributeError):
            continue

    results = []
    for date_key, count in sorted(date_counts.items()):
        try:
            dt = datetime.strptime(date_key, "%Y-%m-%d")
            results.append(
                {
                    "date": date_key,
                    "count": count,
                    "day_name": dt.strftime("%A"),
                    "is_weekend": dt.weekday() >= 5,
                }
            )
        except ValueError:
            continue

    return results


def get_calendar_dataframe(messages: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Create a pandas DataFrame for calendar visualization.

    Args:
        messages: List of message dictionaries.

    Returns:
        DataFrame with date, count, day_name, is_weekend columns.
    """
    distribution = get_calendar_distribution(messages)
    return pd.DataFrame(distribution)


def get_busiest_dates(
    messages: list[dict[str, Any]],
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """
    Get the dates with most emails.

    Args:
        messages: List of message dictionaries.
        top_n: Number of top dates to return.

    Returns:
        List of busiest date dicts.
    """
    distribution = get_calendar_distribution(messages)
    sorted_dates = sorted(distribution, key=lambda x: x["count"], reverse=True)
    return sorted_dates[:top_n]


def get_quietest_dates(
    messages: list[dict[str, Any]],
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """
    Get the dates with fewest emails (that have at least one).

    Args:
        messages: List of message dictionaries.
        top_n: Number of quietest dates to return.

    Returns:
        List of quietest date dicts.
    """
    distribution = get_calendar_distribution(messages)
    sorted_dates = sorted(distribution, key=lambda x: x["count"])
    return sorted_dates[:top_n]


def get_daily_stats(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Get overall daily statistics.

    Args:
        messages: List of message dictionaries.

    Returns:
        Dictionary with daily statistics.
    """
    distribution = get_calendar_distribution(messages)

    if not distribution:
        return {
            "total_days": 0,
            "total_emails": 0,
            "avg_per_day": 0.0,
            "max_per_day": 0,
            "min_per_day": 0,
            "std_dev": 0.0,
        }

    counts = [d["count"] for d in distribution]
    total_emails = sum(counts)
    total_days = len(counts)

    avg = total_emails / total_days if total_days > 0 else 0
    variance = sum((c - avg) ** 2 for c in counts) / total_days if total_days > 0 else 0
    std_dev = variance**0.5

    return {
        "total_days": total_days,
        "total_emails": total_emails,
        "avg_per_day": round(avg, 2),
        "max_per_day": max(counts),
        "min_per_day": min(counts),
        "std_dev": round(std_dev, 2),
    }


def get_weekly_trends(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Get email volume trends by week.

    Args:
        messages: List of message dictionaries.

    Returns:
        List of weekly volume dicts.
    """
    week_counts: dict[str, int] = defaultdict(int)

    for msg in messages:
        date_str = msg.get("date")
        if not date_str:
            continue

        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            # ISO week: YYYY-WXX format
            week_key = dt.strftime("%Y-W%W")
            week_counts[week_key] += 1
        except (ValueError, AttributeError):
            continue

    results = []
    for week_key in sorted(week_counts.keys()):
        results.append(
            {
                "week": week_key,
                "count": week_counts[week_key],
            }
        )

    return results
