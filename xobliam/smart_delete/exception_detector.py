"""Exception detection for Smart Delete.

Scans email content for patterns that suggest the email shouldn't be deleted,
even if it otherwise looks like a safe deletion candidate.
"""

import re
from typing import Any


# Order/Shipping patterns
ORDER_PATTERNS = [
    (r"order\s*#?\s*:?\s*(\d{5,})", "order_number"),
    (r"confirmation\s*#?\s*:?\s*(\w{6,})", "confirmation_number"),
    (r"#(\d{6,})", "order_number"),
]

# Tracking number patterns (UPS, USPS, FedEx)
TRACKING_PATTERNS = [
    (r"\b(1Z[A-Z0-9]{16})\b", "ups"),  # UPS
    (r"\b(94\d{20,22})\b", "usps"),  # USPS
    (r"\b(92\d{20,22})\b", "usps"),  # USPS
    (r"\b(\d{12,22})\b(?=.*(?:track|ship|deliver))", "generic"),  # Generic near keywords
    (r"\b(\d{15})\b", "fedex"),  # FedEx Express
    (r"\b(\d{20})\b", "fedex"),  # FedEx Ground
]

SHIPPING_KEYWORDS = [
    "shipped", "delivered", "tracking", "out for delivery",
    "in transit", "package", "shipment", "carrier",
]

# Financial patterns
FINANCIAL_AMOUNT_PATTERN = r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)"
ACCOUNT_PATTERNS = [
    (r"account\s*#?\s*:?\s*(\*{2,}[\d]{2,4})", "masked_account"),
    (r"account\s+ending\s+in\s+(\d{4})", "account_ending"),
    (r"\*{3,}(\d{4})", "masked_last4"),
]

FINANCIAL_KEYWORDS = [
    "payment", "statement", "balance", "transaction", "invoice",
    "billing", "charged", "credit", "debit", "refund",
    "autopay", "due date", "payment due", "amount due",
]

# Appointment/Reservation patterns
APPOINTMENT_KEYWORDS = [
    "appointment", "reservation", "booking", "scheduled for",
    "confirmed for", "reminder", "upcoming visit",
]

CONFIRMATION_CODE_PATTERN = r"\b([A-Z0-9]{6})\b"
TIME_PATTERN = r"\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))\b"
DATE_TIME_PATTERN = r"(?:at|on)\s+(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)"

# Travel patterns
TRAVEL_KEYWORDS = [
    "flight", "itinerary", "boarding pass", "hotel",
    "check-in", "check-out", "airline", "airport",
    "departure", "arrival", "gate", "terminal",
]

AIRPORT_CODE_PATTERN = r"\b([A-Z]{3})\b"  # 3-letter codes
FLIGHT_NUMBER_PATTERN = r"\b([A-Z]{2}\d{1,4})\b"  # e.g., UA123, AA1234

# Security patterns
SECURITY_KEYWORDS = [
    "password reset", "verify your", "security alert",
    "unusual activity", "sign-in attempt", "login attempt",
    "two-factor", "2fa", "verification code", "security code",
    "suspicious", "unauthorized", "confirm your identity",
]

# Legal/Important patterns
LEGAL_KEYWORDS = [
    "terms of service", "privacy policy", "agreement",
    "contract", "policy update", "action required",
    "respond by", "deadline", "legal notice",
    "important notice", "account suspension", "final notice",
]


def extract_dollar_amounts(text: str) -> list[float]:
    """Extract dollar amounts from text."""
    amounts = []
    for match in re.finditer(FINANCIAL_AMOUNT_PATTERN, text):
        amount_str = match.group(1).replace(",", "")
        try:
            amounts.append(float(amount_str))
        except ValueError:
            pass
    return amounts


def has_keyword_match(text: str, keywords: list[str]) -> str | None:
    """Check if text contains any keyword, return the matched keyword."""
    text_lower = text.lower()
    for keyword in keywords:
        if keyword in text_lower:
            return keyword
    return None


def detect_order_shipping(text: str) -> list[dict[str, Any]]:
    """Detect order numbers, tracking numbers, and shipping-related content."""
    exceptions = []
    text_lower = text.lower()

    # Check for order numbers
    for pattern, pattern_type in ORDER_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            exceptions.append({
                "type": "order_number",
                "detail": f"Order #{match.group(1)}",
                "severity": 40,
            })
            break

    # Check for tracking numbers
    for pattern, carrier in TRACKING_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            tracking = match.group(1)
            # Only include if it's a plausible tracking number
            if len(tracking) >= 12:
                exceptions.append({
                    "type": "tracking_number",
                    "detail": f"{carrier.upper()}: {tracking[:15]}...",
                    "severity": 45,
                })
                break

    # Check for shipping keywords without specific numbers
    if not exceptions:
        keyword = has_keyword_match(text_lower, SHIPPING_KEYWORDS)
        if keyword:
            exceptions.append({
                "type": "shipping",
                "detail": f"Contains '{keyword}'",
                "severity": 25,
            })

    return exceptions


def detect_financial(text: str) -> list[dict[str, Any]]:
    """Detect financial content: amounts, account numbers, keywords."""
    exceptions = []
    text_lower = text.lower()

    # Check for significant dollar amounts (>$100)
    amounts = extract_dollar_amounts(text)
    significant_amounts = [a for a in amounts if a >= 100]
    if significant_amounts:
        max_amount = max(significant_amounts)
        exceptions.append({
            "type": "financial_amount",
            "detail": f"Contains ${max_amount:,.2f}",
            "severity": 50,
        })

    # Check for account numbers
    for pattern, pattern_type in ACCOUNT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            exceptions.append({
                "type": "account_number",
                "detail": f"Account {match.group(1)}",
                "severity": 40,
            })
            break

    # Check for bill due dates
    if "due date" in text_lower or "payment due" in text_lower:
        # Try to extract the date
        date_match = re.search(r"due\s*(?:date|by)?[:\s]*(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)", text, re.IGNORECASE)
        if date_match:
            exceptions.append({
                "type": "bill_due",
                "detail": f"Due date: {date_match.group(1)}",
                "severity": 55,
            })
        else:
            exceptions.append({
                "type": "bill_due",
                "detail": "Contains due date reference",
                "severity": 45,
            })

    # Check for financial keywords (lower severity if no amounts/accounts found)
    if not exceptions:
        keyword = has_keyword_match(text_lower, FINANCIAL_KEYWORDS)
        if keyword:
            exceptions.append({
                "type": "financial",
                "detail": f"Contains '{keyword}'",
                "severity": 20,
            })

    return exceptions


def detect_appointments(text: str) -> list[dict[str, Any]]:
    """Detect appointment and reservation content."""
    exceptions = []
    text_lower = text.lower()

    keyword = has_keyword_match(text_lower, APPOINTMENT_KEYWORDS)
    if not keyword:
        return []

    # Found appointment keyword - now look for details
    severity = 35

    # Look for time
    time_match = re.search(TIME_PATTERN, text)
    if time_match:
        exceptions.append({
            "type": "appointment",
            "detail": f"Scheduled at {time_match.group(1)}",
            "severity": 50,
        })
        return exceptions

    # Look for confirmation code
    codes = re.findall(CONFIRMATION_CODE_PATTERN, text)
    # Filter out common false positives
    codes = [c for c in codes if c not in {"UNSUBSCRIBE", "UPDATE", "MANAGE"}]
    if codes:
        exceptions.append({
            "type": "reservation",
            "detail": f"Confirmation: {codes[0]}",
            "severity": 45,
        })
        return exceptions

    # Generic appointment keyword match
    exceptions.append({
        "type": "appointment",
        "detail": f"Contains '{keyword}'",
        "severity": severity,
    })

    return exceptions


def detect_travel(text: str) -> list[dict[str, Any]]:
    """Detect travel-related content: flights, hotels, itineraries."""
    exceptions = []
    text_lower = text.lower()

    keyword = has_keyword_match(text_lower, TRAVEL_KEYWORDS)
    if not keyword:
        return []

    # Found travel keyword - look for details
    severity = 40

    # Look for flight numbers
    flight_match = re.search(FLIGHT_NUMBER_PATTERN, text)
    if flight_match:
        exceptions.append({
            "type": "flight",
            "detail": f"Flight {flight_match.group(1)}",
            "severity": 55,
        })
        return exceptions

    # Look for airport codes (need at least 2 for a route)
    airport_codes = re.findall(AIRPORT_CODE_PATTERN, text)
    # Filter to likely airport codes (exclude common words)
    common_words = {"THE", "AND", "FOR", "YOU", "YOUR", "ARE", "WAS", "HAS", "HIS", "HER"}
    airport_codes = [c for c in airport_codes if c not in common_words]
    if len(airport_codes) >= 2:
        route = f"{airport_codes[0]}→{airport_codes[1]}"
        exceptions.append({
            "type": "flight",
            "detail": f"Route: {route}",
            "severity": 55,
        })
        return exceptions

    # Generic travel match
    exceptions.append({
        "type": "travel",
        "detail": f"Contains '{keyword}'",
        "severity": severity,
    })

    return exceptions


def detect_security(text: str) -> list[dict[str, Any]]:
    """Detect security-related content."""
    exceptions = []
    text_lower = text.lower()

    keyword = has_keyword_match(text_lower, SECURITY_KEYWORDS)
    if keyword:
        # Security alerts are high severity
        exceptions.append({
            "type": "security",
            "detail": f"Contains '{keyword}'",
            "severity": 60,
        })

    return exceptions


def detect_legal_important(text: str) -> list[dict[str, Any]]:
    """Detect legal notices and important action items."""
    exceptions = []
    text_lower = text.lower()

    keyword = has_keyword_match(text_lower, LEGAL_KEYWORDS)
    if keyword:
        severity = 45
        # Higher severity for action-required items
        if keyword in ["action required", "respond by", "deadline", "final notice"]:
            severity = 60

        exceptions.append({
            "type": "legal_important",
            "detail": f"Contains '{keyword}'",
            "severity": severity,
        })

    return exceptions


def detect_personal_indicators(
    message: dict[str, Any],
    user_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Detect personal/engagement indicators that suggest importance."""
    exceptions = []

    # Check for attachments
    if message.get("has_attachments"):
        exceptions.append({
            "type": "has_attachments",
            "detail": "Contains attachments",
            "severity": 30,
        })

    # Check if part of multi-message thread
    # (Would need thread info - skip for now if not available)

    # Check if sender is someone user has replied to
    if user_context:
        sender = message.get("sender", "").lower()
        replied_senders = user_context.get("replied_senders", set())
        if sender in replied_senders:
            exceptions.append({
                "type": "replied_sender",
                "detail": "Previously replied to this sender",
                "severity": 35,
            })

        # Check for important names from user context
        important_names = user_context.get("important_names", [])
        text = f"{message.get('subject', '')} {message.get('snippet', '')}".lower()
        for name in important_names:
            if name.lower() in text:
                exceptions.append({
                    "type": "important_name",
                    "detail": f"Mentions '{name}'",
                    "severity": 40,
                })
                break

    return exceptions


def detect_exceptions(
    message: dict[str, Any],
    user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Scan message for content that suggests it shouldn't be deleted.

    Args:
        message: Message dict with subject, snippet, labels, etc.
        user_context: Optional context (replied senders, important names, etc.)

    Returns:
        {
            "has_exceptions": True/False,
            "exceptions": [
                {"type": "tracking_number", "detail": "UPS: 1Z999AA1...", "severity": 45},
                {"type": "financial_amount", "detail": "Contains $805.82", "severity": 50},
            ],
            "exception_score": 0-100  # Higher = more likely important
        }
    """
    # Combine subject and snippet for scanning
    subject = message.get("subject", "") or ""
    snippet = message.get("snippet", "") or ""
    combined_text = f"{subject} {snippet}"

    if not combined_text.strip():
        return {
            "has_exceptions": False,
            "exceptions": [],
            "exception_score": 0,
        }

    all_exceptions = []

    # Run all detectors
    all_exceptions.extend(detect_order_shipping(combined_text))
    all_exceptions.extend(detect_financial(combined_text))
    all_exceptions.extend(detect_appointments(combined_text))
    all_exceptions.extend(detect_travel(combined_text))
    all_exceptions.extend(detect_security(combined_text))
    all_exceptions.extend(detect_legal_important(combined_text))
    all_exceptions.extend(detect_personal_indicators(message, user_context))

    # Deduplicate by type (keep highest severity)
    seen_types = {}
    for exc in all_exceptions:
        exc_type = exc["type"]
        if exc_type not in seen_types or exc["severity"] > seen_types[exc_type]["severity"]:
            seen_types[exc_type] = exc

    unique_exceptions = list(seen_types.values())

    # Calculate overall exception score (max of individual severities, with bonus for multiple)
    if unique_exceptions:
        max_severity = max(e["severity"] for e in unique_exceptions)
        # Add small bonus for multiple exceptions
        bonus = min(10, (len(unique_exceptions) - 1) * 5)
        exception_score = min(100, max_severity + bonus)
    else:
        exception_score = 0

    return {
        "has_exceptions": len(unique_exceptions) > 0,
        "exceptions": unique_exceptions,
        "exception_score": exception_score,
    }
