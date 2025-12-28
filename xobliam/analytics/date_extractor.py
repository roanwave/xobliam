"""Extract dates and deadlines from email messages."""

import re
from datetime import datetime, timedelta
from typing import Any


# Month name mappings
MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# Context keywords that indicate important dates
CONTEXT_KEYWORDS = [
    "expires", "expire", "expiring", "expiration",
    "through", "until", "by", "before", "deadline",
    "ends", "ending", "last day", "last chance",
    "scheduled", "appointment", "meeting", "call",
    "webinar", "event", "conference", "seminar",
    "rsvp", "register", "registration",
    "sale", "offer", "discount", "deal", "promo",
    "due", "submit", "reminder",
]

# Promo code patterns
PROMO_PATTERNS = [
    r"(?:code|promo|coupon|use)[:\s]+([A-Z0-9]{3,15})",
    r"(?:enter|apply)[:\s]+([A-Z0-9]{3,15})",
    r"\b([A-Z]{2,}[0-9]{1,}[A-Z0-9]*)\b",  # Common code format like SAVE20, BLEH
]


def extract_promo_code(text: str) -> str | None:
    """Extract promotional/discount code from text."""
    text_upper = text.upper()

    for pattern in PROMO_PATTERNS[:2]:  # Check explicit patterns first
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            code = match.group(1).upper()
            if len(code) >= 3 and len(code) <= 15:
                return code

    # Check for standalone codes (be more conservative)
    # Look for all-caps words that look like codes
    code_match = re.search(r"\b([A-Z]{2,}[0-9]+[A-Z0-9]*)\b", text_upper)
    if code_match:
        code = code_match.group(1)
        # Filter out common false positives
        if code not in {"AM", "PM", "EST", "PST", "CST", "GMT", "USD", "USA"}:
            return code

    return None


def parse_date_from_match(
    match_text: str,
    reference_date: datetime | None = None,
) -> datetime | None:
    """Parse a date string into a datetime object."""
    if reference_date is None:
        reference_date = datetime.now()

    current_year = reference_date.year
    next_year = current_year + 1

    # Clean the match text
    text = match_text.strip().lower()

    # Pattern: MM/DD/YYYY or MM/DD/YY
    match = re.match(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", text)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        year = match.group(3)
        if year:
            year = int(year)
            if year < 100:
                year += 2000
        else:
            # Infer year - if date is in the past, assume next year
            year = current_year

        try:
            dt = datetime(year, month, day)
            if dt < reference_date and not match.group(3):
                dt = datetime(next_year, month, day)
            return dt
        except ValueError:
            return None

    # Pattern: Month DD, YYYY or Month DD
    for month_name, month_num in MONTH_NAMES.items():
        pattern = rf"{month_name}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{{4}}))?(?:\s+at\s+(\d{{1,2}})(?::(\d{{2}}))?\s*(am|pm)?)?"
        match = re.search(pattern, text)
        if match:
            day = int(match.group(1))
            year = int(match.group(2)) if match.group(2) else current_year
            hour = int(match.group(3)) if match.group(3) else None
            minute = int(match.group(4)) if match.group(4) else 0
            ampm = match.group(5) if match.group(5) else None

            if hour and ampm:
                if ampm.lower() == "pm" and hour < 12:
                    hour += 12
                elif ampm.lower() == "am" and hour == 12:
                    hour = 0

            try:
                if hour is not None:
                    dt = datetime(year, month_num, day, hour, minute)
                else:
                    dt = datetime(year, month_num, day)

                if dt < reference_date and not match.group(2):
                    dt = dt.replace(year=next_year)
                return dt
            except ValueError:
                return None

    return None


def extract_context(text: str, date_start: int, date_end: int, words: int = 12) -> str:
    """Extract context around a date match."""
    # Get text before and after the date
    before = text[:date_start]
    after = text[date_end:]

    # Get words before
    before_words = before.split()[-words:]
    # Get words after
    after_words = after.split()[:words]

    context = " ".join(before_words + after_words)

    # Clean up
    context = re.sub(r"\s+", " ", context).strip()

    # Find the most relevant context keyword
    context_lower = context.lower()
    for keyword in CONTEXT_KEYWORDS:
        if keyword in context_lower:
            # Extract phrase around keyword
            idx = context_lower.find(keyword)
            start = max(0, idx - 20)
            end = min(len(context), idx + len(keyword) + 30)
            return context[start:end].strip()

    return context[:60] if context else ""


def extract_dates_from_text(text: str) -> list[dict[str, Any]]:
    """Extract all dates from text with context."""
    if not text:
        return []

    results = []
    now = datetime.now()

    # Combined patterns to search for dates
    date_patterns = [
        # MM/DD/YYYY or MM/DD/YY or MM/DD
        (r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)", "numeric"),
        # Month DD, YYYY or Month DD with optional time
        (r"((?:january|february|march|april|may|june|july|august|september|october|november|december|"
         r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*,?\s*\d{4})?(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?)", "month_name"),
    ]

    # Context trigger patterns - only extract dates near these keywords
    context_triggers = r"(?:through|until|by|before|expires?|expiring|ends?|ending|deadline|scheduled|" \
                      r"appointment|webinar|event|rsvp|register|last\s+(?:day|chance)|due|offer|sale)"

    text_lower = text.lower()

    for pattern, pattern_type in date_patterns:
        for match in re.finditer(pattern, text_lower, re.IGNORECASE):
            match_text = match.group(1)
            match_start = match.start()
            match_end = match.end()

            # Check if there's a context trigger nearby (within 50 chars before or after)
            context_window_start = max(0, match_start - 50)
            context_window_end = min(len(text_lower), match_end + 50)
            context_window = text_lower[context_window_start:context_window_end]

            if not re.search(context_triggers, context_window):
                continue

            # Parse the date
            parsed_date = parse_date_from_match(match_text)
            if not parsed_date:
                continue

            # Only include future dates (within 1 year)
            if parsed_date < now:
                continue
            if parsed_date > now + timedelta(days=365):
                continue

            # Extract context
            context = extract_context(text, match_start, match_end)

            results.append({
                "date": parsed_date,
                "date_str": parsed_date.strftime("%m/%d/%Y"),
                "has_time": parsed_date.hour != 0 or parsed_date.minute != 0,
                "time_str": parsed_date.strftime("%I:%M %p").lstrip("0") if parsed_date.hour != 0 else None,
                "context": context,
                "match_text": match_text,
            })

    return results


def extract_dates_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract dates from a single email message."""
    results = []

    # Combine subject and snippet for searching
    subject = message.get("subject", "") or ""
    snippet = message.get("snippet", "") or ""
    combined_text = f"{subject} {snippet}"

    # Extract dates
    dates = extract_dates_from_text(combined_text)

    # Extract promo code from full text
    promo_code = extract_promo_code(combined_text)

    for date_info in dates:
        results.append({
            **date_info,
            "message_id": message.get("message_id"),
            "sender": message.get("sender", ""),
            "subject": subject,
            "snippet": snippet,
            "promo_code": promo_code,
        })

    return results


def extract_dates_from_messages(
    messages: list[dict[str, Any]],
    unlabeled_only: bool = True,
) -> list[dict[str, Any]]:
    """
    Extract dates from multiple messages.

    Args:
        messages: List of message dictionaries.
        unlabeled_only: If True, only process unlabeled messages.

    Returns:
        List of date extractions sorted by date (soonest first).
    """
    from xobliam.smart_delete import filter_unlabeled_messages

    if unlabeled_only:
        messages = filter_unlabeled_messages(messages)

    all_results = []
    seen_dates = set()  # Deduplicate by (message_id, date)

    for msg in messages:
        msg_dates = extract_dates_from_message(msg)
        for date_info in msg_dates:
            key = (date_info["message_id"], date_info["date_str"])
            if key not in seen_dates:
                seen_dates.add(key)
                all_results.append(date_info)

    # Sort by date (soonest first)
    all_results.sort(key=lambda x: x["date"])

    return all_results
