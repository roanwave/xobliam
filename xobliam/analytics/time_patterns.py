"""Time pattern analysis for email activity."""

from collections import defaultdict
from datetime import datetime
from typing import Any

import pandas as pd


def analyze_time_patterns(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Analyze email volume by day of week and hour.

    Args:
        messages: List of message dictionaries with 'date' field.

    Returns:
        Dictionary with:
        - matrix: 7x24 matrix of email counts (day x hour)
        - day_totals: Total emails per day of week
        - hour_totals: Total emails per hour
        - peak_slot: (day, hour) tuple of busiest time
    """
    # Initialize 7x24 matrix (Monday=0 to Sunday=6, hours 0-23)
    matrix = [[0 for _ in range(24)] for _ in range(7)]

    for msg in messages:
        date_str = msg.get("date")
        if not date_str:
            continue

        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            day = dt.weekday()  # 0=Monday, 6=Sunday
            hour = dt.hour
            matrix[day][hour] += 1
        except (ValueError, AttributeError):
            continue

    # Calculate totals
    day_totals = [sum(matrix[day]) for day in range(7)]
    hour_totals = [sum(matrix[day][hour] for day in range(7)) for hour in range(24)]

    # Find peak slot
    peak_count = 0
    peak_slot = (0, 0)
    for day in range(7):
        for hour in range(24):
            if matrix[day][hour] > peak_count:
                peak_count = matrix[day][hour]
                peak_slot = (day, hour)

    day_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    return {
        "matrix": matrix,
        "day_totals": day_totals,
        "hour_totals": hour_totals,
        "peak_slot": peak_slot,
        "peak_day": day_names[peak_slot[0]],
        "peak_hour": peak_slot[1],
        "peak_count": peak_count,
        "day_names": day_names,
    }


def get_top_senders_per_slot(
    messages: list[dict[str, Any]],
    top_n: int = 3,
) -> dict[tuple[int, int], list[tuple[str, int]]]:
    """
    Get top senders for each day/hour slot.

    Args:
        messages: List of message dictionaries.
        top_n: Number of top senders to return per slot.

    Returns:
        Dictionary mapping (day, hour) to list of (sender, count) tuples.
    """
    # Count senders per slot
    slot_senders: dict[tuple[int, int], dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )

    for msg in messages:
        date_str = msg.get("date")
        sender = msg.get("sender")
        if not date_str or not sender:
            continue

        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            slot = (dt.weekday(), dt.hour)
            slot_senders[slot][sender] += 1
        except (ValueError, AttributeError):
            continue

    # Get top senders per slot
    result = {}
    for slot, senders in slot_senders.items():
        sorted_senders = sorted(senders.items(), key=lambda x: x[1], reverse=True)
        result[slot] = sorted_senders[:top_n]

    return result


def get_time_pattern_dataframe(messages: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Create a pandas DataFrame for time pattern visualization.

    Args:
        messages: List of message dictionaries.

    Returns:
        DataFrame with columns: day, hour, count, day_name
    """
    patterns = analyze_time_patterns(messages)
    matrix = patterns["matrix"]
    day_names = patterns["day_names"]

    rows = []
    for day in range(7):
        for hour in range(24):
            rows.append(
                {
                    "day": day,
                    "hour": hour,
                    "count": matrix[day][hour],
                    "day_name": day_names[day],
                }
            )

    return pd.DataFrame(rows)


def get_busiest_times(
    messages: list[dict[str, Any]],
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """
    Get the busiest time slots.

    Args:
        messages: List of message dictionaries.
        top_n: Number of top slots to return.

    Returns:
        List of dictionaries with day, hour, count, and formatted time.
    """
    patterns = analyze_time_patterns(messages)
    matrix = patterns["matrix"]
    day_names = patterns["day_names"]

    slots = []
    for day in range(7):
        for hour in range(24):
            slots.append(
                {
                    "day": day,
                    "day_name": day_names[day],
                    "hour": hour,
                    "count": matrix[day][hour],
                    "time_label": f"{day_names[day]} {hour:02d}:00",
                }
            )

    sorted_slots = sorted(slots, key=lambda x: x["count"], reverse=True)
    return sorted_slots[:top_n]


def get_quiet_times(
    messages: list[dict[str, Any]],
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """
    Get the quietest time slots (with at least some activity).

    Args:
        messages: List of message dictionaries.
        top_n: Number of quietest slots to return.

    Returns:
        List of dictionaries with day, hour, count, and formatted time.
    """
    patterns = analyze_time_patterns(messages)
    matrix = patterns["matrix"]
    day_names = patterns["day_names"]

    slots = []
    for day in range(7):
        for hour in range(24):
            if matrix[day][hour] > 0:  # Only include slots with activity
                slots.append(
                    {
                        "day": day,
                        "day_name": day_names[day],
                        "hour": hour,
                        "count": matrix[day][hour],
                        "time_label": f"{day_names[day]} {hour:02d}:00",
                    }
                )

    sorted_slots = sorted(slots, key=lambda x: x["count"])
    return sorted_slots[:top_n]
