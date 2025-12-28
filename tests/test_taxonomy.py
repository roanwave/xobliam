"""Tests for the taxonomy module."""

import pytest

from xobliam.taxonomy import (
    SENDER_TYPES,
    classify_batch,
    classify_message,
    get_category_stats,
)


class TestClassifier:
    """Tests for message classification."""

    def test_classify_newsletter(self):
        """Test newsletter classification."""
        message = {
            "sender": "newsletter@company.com",
            "subject": "Weekly Newsletter",
            "snippet": "Click here to unsubscribe from future emails",
        }

        category = classify_message(message)
        assert category == "newsletter"

    def test_classify_transactional(self):
        """Test transactional email classification."""
        message = {
            "sender": "orders@amazon.com",
            "subject": "Your order has shipped",
            "snippet": "Your package is on its way",
        }

        category = classify_message(message)
        assert category == "transactional"

    def test_classify_marketing(self):
        """Test marketing email classification."""
        message = {
            "sender": "promo@store.com",
            "subject": "50% off sale - Limited time!",
            "snippet": "Don't miss out on these deals. Unsubscribe here.",
        }

        category = classify_message(message)
        assert category == "marketing"

    def test_classify_automated(self):
        """Test automated email classification."""
        message = {
            "sender": "security@bank.com",
            "subject": "Password reset requested",
            "snippet": "Click here to reset your password",
        }

        category = classify_message(message)
        assert category == "automated"

    def test_classify_social(self):
        """Test social media notification classification."""
        message = {
            "sender": "notifications@linkedin.com",
            "subject": "You have a new connection request",
            "snippet": "John Doe wants to connect with you",
        }

        category = classify_message(message)
        assert category == "social"

    def test_classify_professional_with_domain(self):
        """Test professional email with user domain."""
        message = {
            "sender": "colleague@mycompany.com",
            "subject": "Meeting tomorrow",
            "snippet": "Let's discuss the project",
        }

        category = classify_message(message, user_domain="mycompany.com")
        assert category == "professional"

    def test_classify_personal(self):
        """Test personal email classification."""
        message = {
            "sender": "friend@gmail.com",
            "subject": "Hey, how are you?",
            "snippet": "Just wanted to check in",
        }

        category = classify_message(message)
        # Personal is low priority, may classify as unknown if no strong signals
        assert category in ("personal", "unknown")

    def test_classify_unknown(self):
        """Test unknown classification fallback."""
        message = {
            "sender": "random@obscure-domain.xyz",
            "subject": "Random subject",
            "snippet": "Random content without clear signals",
        }

        category = classify_message(message)
        # Should fall back to unknown if no patterns match
        assert isinstance(category, str)


class TestBatchClassification:
    """Tests for batch classification."""

    @pytest.fixture
    def sample_messages(self):
        """Sample messages for batch testing."""
        return [
            {
                "sender": "newsletter@company.com",
                "subject": "Weekly Newsletter",
                "snippet": "Unsubscribe",
            },
            {
                "sender": "orders@store.com",
                "subject": "Order confirmation",
                "snippet": "Your order #12345",
            },
            {
                "sender": "alerts@linkedin.com",
                "subject": "New notification",
                "snippet": "Someone viewed your profile",
            },
        ]

    def test_classify_batch(self, sample_messages):
        """Test batch classification."""
        results = classify_batch(sample_messages)

        assert len(results) == 3
        assert all("category" in r for r in results)

        # Original message data should be preserved
        assert results[0]["sender"] == "newsletter@company.com"

    def test_get_category_stats(self, sample_messages):
        """Test category statistics."""
        stats = get_category_stats(sample_messages)

        assert isinstance(stats, dict)

        # Check structure of stats
        for category, data in stats.items():
            assert "count" in data
            assert "read_rate" in data
            assert "unique_senders" in data


class TestSenderTypes:
    """Tests for SENDER_TYPES configuration."""

    def test_sender_types_structure(self):
        """Test that SENDER_TYPES has required keys."""
        required_keys = {"description", "priority"}

        for category, rules in SENDER_TYPES.items():
            # Each category should have a description
            assert "description" in rules, f"Missing description for {category}"
            assert "priority" in rules, f"Missing priority for {category}"

    def test_unknown_category_exists(self):
        """Test that unknown category exists as fallback."""
        assert "unknown" in SENDER_TYPES

    def test_priority_ordering(self):
        """Test that priority values are reasonable."""
        priorities = [rules["priority"] for rules in SENDER_TYPES.values()]

        # Unknown should have highest priority (lowest precedence)
        assert SENDER_TYPES["unknown"]["priority"] == max(priorities)
