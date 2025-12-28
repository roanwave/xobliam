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


def get_day_hourly_breakdown(
    messages: list[dict[str, Any]],
    day_name: str | None = None,
    day_index: int | None = None,
) -> dict[str, Any]:
    """
    Get hourly breakdown for a specific day of the week.

    Args:
        messages: List of message dictionaries.
        day_name: Day name (e.g., "Friday"). Used if day_index not provided.
        day_index: Day index (0=Monday, 6=Sunday).

    Returns:
        Dictionary with hourly breakdown and focus mode recommendations.
    """
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # Resolve day index
    if day_index is None:
        if day_name:
            day_name_lower = day_name.lower()
            for i, name in enumerate(day_names):
                if name.lower() == day_name_lower:
                    day_index = i
                    break
        if day_index is None:
            # Default to busiest day
            patterns = analyze_time_patterns(messages)
            day_index = patterns["peak_slot"][0]

    # Get hourly counts for this day
    patterns = analyze_time_patterns(messages)
    hourly_counts = patterns["matrix"][day_index]
    total_for_day = sum(hourly_counts)

    # Group into time blocks
    time_blocks = [
        {"label": "12am - 6am", "start": 0, "end": 6},
        {"label": "6am - 9am", "start": 6, "end": 9},
        {"label": "9am - 12pm", "start": 9, "end": 12},
        {"label": "12pm - 3pm", "start": 12, "end": 15},
        {"label": "3pm - 6pm", "start": 15, "end": 18},
        {"label": "6pm - 9pm", "start": 18, "end": 21},
        {"label": "9pm - 12am", "start": 21, "end": 24},
    ]

    blocks = []
    max_count = 0
    for block in time_blocks:
        count = sum(hourly_counts[block["start"]:block["end"]])
        max_count = max(max_count, count)
        blocks.append({
            "label": block["label"],
            "start_hour": block["start"],
            "end_hour": block["end"],
            "count": count,
        })

    # Add percentage and visual bars
    for block in blocks:
        block["percentage"] = round((block["count"] / total_for_day) * 100, 1) if total_for_day > 0 else 0
        block["bar_width"] = round((block["count"] / max_count) * 10) if max_count > 0 else 0
        block["is_peak"] = block["count"] == max_count and max_count > 0

    # Find quiet hours for focus mode recommendations
    quiet_blocks = [b for b in blocks if b["count"] < (max_count * 0.3)]
    quiet_times = [b["label"] for b in quiet_blocks]

    # Find peak hours
    peak_blocks = [b for b in blocks if b["is_peak"] or b["count"] >= (max_count * 0.8)]
    peak_times = [b["label"] for b in peak_blocks]

    return {
        "day_name": day_names[day_index],
        "day_index": day_index,
        "total_emails": total_for_day,
        "blocks": blocks,
        "hourly_counts": hourly_counts,
        "quiet_times": quiet_times,
        "peak_times": peak_times,
        "focus_mode_suggestion": f"Low traffic: {', '.join(quiet_times)}" if quiet_times else "No clear quiet periods",
    }
