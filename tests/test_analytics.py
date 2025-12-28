"""Tests for the analytics module."""

from datetime import datetime, timedelta

import pytest

from xobliam.analytics import (
    analyze_time_patterns,
    calculate_open_rate,
    find_redundant_labels,
    get_day_of_week_distribution,
    get_frequent_senders,
    suggest_new_labels,
)


@pytest.fixture
def sample_messages():
    """Generate sample messages for testing."""
    messages = []
    now = datetime.utcnow()

    # Create messages with various characteristics
    for i in range(100):
        # Vary the date across days
        date = now - timedelta(days=i % 30, hours=i % 24)

        # Vary senders
        senders = [
            "newsletter@company.com",
            "john@example.com",
            "support@service.com",
            "promo@store.com",
            "team@work.com",
        ]
        sender = senders[i % len(senders)]

        # Vary read status
        is_unread = i % 3 == 0

        # Vary labels
        if i % 5 == 0:
            labels = ["INBOX", "Work", "Important"]
        elif i % 3 == 0:
            labels = ["INBOX", "Work"]
        else:
            labels = ["INBOX"]

        messages.append({
            "message_id": f"msg{i}",
            "thread_id": f"thread{i}",
            "date": date.isoformat(),
            "sender": sender,
            "recipients": "user@example.com",
            "subject": f"Test Subject {i}",
            "labels": labels,
            "is_unread": is_unread,
            "has_attachments": i % 10 == 0,
            "snippet": f"Test snippet {i}",
        })

    return messages


class TestOpenRate:
    """Tests for open rate calculation."""

    def test_calculate_open_rate(self, sample_messages):
        """Test open rate calculation."""
        result = calculate_open_rate(sample_messages)

        assert "total" in result
        assert "read" in result
        assert "unread" in result
        assert "open_rate" in result

        assert result["total"] == 100
        assert result["read"] + result["unread"] == 100
        assert 0 <= result["open_rate"] <= 100

    def test_empty_messages(self):
        """Test with empty message list."""
        result = calculate_open_rate([])

        assert result["total"] == 0
        assert result["open_rate"] == 0.0


class TestTimePatterns:
    """Tests for time pattern analysis."""

    def test_analyze_time_patterns(self, sample_messages):
        """Test time pattern analysis."""
        result = analyze_time_patterns(sample_messages)

        assert "matrix" in result
        assert "day_totals" in result
        assert "hour_totals" in result
        assert "peak_slot" in result
        assert "peak_day" in result
        assert "peak_hour" in result

        # Matrix should be 7x24
        assert len(result["matrix"]) == 7
        assert all(len(row) == 24 for row in result["matrix"])

        # Day and hour totals
        assert len(result["day_totals"]) == 7
        assert len(result["hour_totals"]) == 24

        # Peak values should be valid
        assert 0 <= result["peak_slot"][0] <= 6
        assert 0 <= result["peak_slot"][1] <= 23


class TestSenderAnalysis:
    """Tests for sender analysis."""

    def test_get_frequent_senders(self, sample_messages):
        """Test frequent sender extraction."""
        senders = get_frequent_senders(sample_messages)

        assert len(senders) > 0
        assert all("sender" in s for s in senders)
        assert all("count" in s for s in senders)
        assert all("read_rate" in s for s in senders)

        # Should be sorted by count descending
        counts = [s["count"] for s in senders]
        assert counts == sorted(counts, reverse=True)

    def test_frequent_senders_top_n(self, sample_messages):
        """Test limiting number of senders."""
        senders = get_frequent_senders(sample_messages, top_n=3)
        assert len(senders) == 3


class TestDailyDistribution:
    """Tests for daily distribution analysis."""

    def test_day_of_week_distribution(self, sample_messages):
        """Test day of week distribution."""
        result = get_day_of_week_distribution(sample_messages)

        assert "distribution" in result
        assert "busiest_day" in result
        assert "quietest_day" in result
        assert "weekday_total" in result
        assert "weekend_total" in result

        # Distribution should have 7 days
        assert len(result["distribution"]) == 7

        # Day names should be present
        day_names = [d["day_name"] for d in result["distribution"]]
        assert "Monday" in day_names
        assert "Sunday" in day_names


class TestLabelAudit:
    """Tests for label audit functions."""

    def test_find_redundant_labels(self):
        """Test finding redundant label pairs."""
        # Create messages where labels A and B always co-occur
        messages = []
        for i in range(20):
            messages.append({
                "message_id": f"msg{i}",
                "labels": ["LabelA", "LabelB"],  # Always together
                "sender": "test@example.com",
                "subject": f"Test {i}",
            })

        # Add some with only LabelA
        for i in range(5):
            messages.append({
                "message_id": f"solo{i}",
                "labels": ["LabelA"],
                "sender": "test@example.com",
                "subject": f"Solo {i}",
            })

        redundant = find_redundant_labels(messages, threshold=0.80)

        # Should find LabelA and LabelB as redundant (20/20 = 100% for LabelB)
        assert len(redundant) > 0
        pair = redundant[0]
        assert "label_a" in pair
        assert "label_b" in pair
        assert pair["co_occurrence_rate"] >= 80

    def test_suggest_new_labels(self, sample_messages):
        """Test new label suggestions."""
        suggestions = suggest_new_labels(sample_messages)

        # Should return list of suggestions
        assert isinstance(suggestions, list)

        if suggestions:
            suggestion = suggestions[0]
            assert "suggested_label" in suggestion
            assert "domain" in suggestion
            assert "message_count" in suggestion
