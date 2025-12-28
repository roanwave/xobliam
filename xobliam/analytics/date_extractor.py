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

# Context type detection for sanity checks
DELIVERY_KEYWORDS = ["deliver", "arrival", "arrive", "ship", "order", "package", "tracking"]
APPOINTMENT_KEYWORDS = ["appointment", "meeting", "call", "scheduled", "visit", "session"]
SALE_KEYWORDS = ["sale", "offer", "discount", "deal", "promo", "expires", "ending", "through"]

# Maximum days from email sent date for each context type
MAX_DAYS_BY_TYPE = {
    "delivery": 30,
    "appointment": 90,
    "sale": 60,
    "default": 180,  # 6 months max for unknown types
}

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


def infer_year_from_email_date(
    month: int,
    day: int,
    email_sent_date: datetime,
) -> int:
    """
    Infer the correct year for a date based on email sent date.

    Logic:
    - If the date (month/day) is within 30 days AFTER email sent → use email's year
    - If the date (month/day) is within 14 days BEFORE email sent → use email's year
    - Otherwise, use next year only if it makes the date closer to email sent date
    """
    email_year = email_sent_date.year

    try:
        # Try with email's year first
        candidate_same_year = datetime(email_year, month, day)
    except ValueError:
        return email_year  # Invalid date, just return email year

    # Calculate days difference from email sent date
    diff_same_year = (candidate_same_year - email_sent_date).days

    # If date is within reasonable range of email sent date, use email's year
    # Allow 14 days before (date might be mentioned as "starting on X")
    # Allow 30 days after (most events/deliveries are within a month)
    if -14 <= diff_same_year <= 30:
        return email_year

    # Try next year
    try:
        candidate_next_year = datetime(email_year + 1, month, day)
        diff_next_year = (candidate_next_year - email_sent_date).days
    except ValueError:
        return email_year

    # Try previous year (in case email is from early January about late December)
    try:
        candidate_prev_year = datetime(email_year - 1, month, day)
        diff_prev_year = (candidate_prev_year - email_sent_date).days
    except ValueError:
        diff_prev_year = -999

    # Choose the year that puts the date closest to (but after) email sent date
    # Prefer dates that are 0-180 days after email sent
    candidates = [
        (email_year, diff_same_year),
        (email_year + 1, diff_next_year),
    ]
    if diff_prev_year >= -14:
        candidates.append((email_year - 1, diff_prev_year))

    # Filter to reasonable candidates (within -14 to +180 days of email)
    valid = [(y, d) for y, d in candidates if -14 <= d <= 180]

    if valid:
        # Return year with smallest positive difference (or smallest negative if all negative)
        valid.sort(key=lambda x: (x[1] < 0, abs(x[1])))
        return valid[0][0]

    # Fallback: use email's year
    return email_year


def parse_date_from_match(
    match_text: str,
    email_sent_date: datetime | None = None,
) -> datetime | None:
    """
    Parse a date string into a datetime object.

    Args:
        match_text: The date string to parse.
        email_sent_date: The date the email was sent (for year inference).
    """
    if email_sent_date is None:
        email_sent_date = datetime.now()

    # Clean the match text
    text = match_text.strip().lower()

    # Pattern: MM/DD/YYYY or MM/DD/YY or MM/DD
    match = re.match(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", text)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        year_str = match.group(3)

        if year_str:
            year = int(year_str)
            if year < 100:
                year += 2000
        else:
            # No year specified - infer from email sent date
            year = infer_year_from_email_date(month, day, email_sent_date)

        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    # Pattern: Month DD, YYYY or Month DD
    for month_name, month_num in MONTH_NAMES.items():
        pattern = rf"{month_name}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{{4}}))?(?:\s+at\s+(\d{{1,2}})(?::(\d{{2}}))?\s*(am|pm)?)?"
        match = re.search(pattern, text)
        if match:
            day = int(match.group(1))
            year_str = match.group(2)
            hour = int(match.group(3)) if match.group(3) else None
            minute = int(match.group(4)) if match.group(4) else 0
            ampm = match.group(5) if match.group(5) else None

            if year_str:
                year = int(year_str)
            else:
                # No year specified - infer from email sent date
                year = infer_year_from_email_date(month_num, day, email_sent_date)

            if hour and ampm:
                if ampm.lower() == "pm" and hour < 12:
                    hour += 12
                elif ampm.lower() == "am" and hour == 12:
                    hour = 0

            try:
                if hour is not None:
                    return datetime(year, month_num, day, hour, minute)
                else:
                    return datetime(year, month_num, day)
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


def detect_context_type(text: str) -> str:
    """Detect the type of date context for sanity checking."""
    text_lower = text.lower()

    for keyword in DELIVERY_KEYWORDS:
        if keyword in text_lower:
            return "delivery"

    for keyword in APPOINTMENT_KEYWORDS:
        if keyword in text_lower:
            return "appointment"

    for keyword in SALE_KEYWORDS:
        if keyword in text_lower:
            return "sale"

    return "default"


def is_date_reasonable(
    parsed_date: datetime,
    email_sent_date: datetime,
    context_type: str,
) -> bool:
    """
    Check if a parsed date is reasonable given the email sent date and context.

    Returns True if the date passes sanity checks.
    """
    days_from_email = (parsed_date - email_sent_date).days

    # Date shouldn't be more than 14 days before email was sent
    if days_from_email < -14:
        return False

    # Check against maximum days for this context type
    max_days = MAX_DAYS_BY_TYPE.get(context_type, MAX_DAYS_BY_TYPE["default"])
    if days_from_email > max_days:
        return False

    return True


def extract_dates_from_text(
    text: str,
    email_sent_date: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Extract all dates from text with context.

    Args:
        text: The text to extract dates from.
        email_sent_date: The date the email was sent (for year inference).
    """
    if not text:
        return []

    if email_sent_date is None:
        email_sent_date = datetime.now()

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
                      r"appointment|webinar|event|rsvp|register|last\s+(?:day|chance)|due|offer|sale|deliver|arrive|ship)"

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

            # Detect context type for sanity checking
            context_type = detect_context_type(context_window)

            # Parse the date using email sent date for year inference
            parsed_date = parse_date_from_match(match_text, email_sent_date)
            if not parsed_date:
                continue

            # Sanity check: is the date reasonable given email sent date and context?
            if not is_date_reasonable(parsed_date, email_sent_date, context_type):
                continue

            # Only include dates that are still in the future relative to TODAY
            if parsed_date < now:
                continue

            # Don't include dates more than 1 year from now
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
                "context_type": context_type,
                "match_text": match_text,
            })

    return results


def parse_email_date(date_str: str | None) -> datetime | None:
    """Parse email date string to datetime."""
    if not date_str:
        return None

    try:
        # Try ISO format first (most common in our cache)
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        pass

    # Try common email date formats
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def extract_dates_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract dates from a single email message."""
    results = []

    # Combine subject and snippet for searching
    subject = message.get("subject", "") or ""
    snippet = message.get("snippet", "") or ""
    combined_text = f"{subject} {snippet}"

    # Get email sent date for year inference
    email_sent_date = parse_email_date(message.get("date"))
    if email_sent_date is None:
        email_sent_date = datetime.now()

    # Extract dates using email sent date for context
    dates = extract_dates_from_text(combined_text, email_sent_date)

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
            "email_date": email_sent_date.strftime("%Y-%m-%d") if email_sent_date else None,
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
