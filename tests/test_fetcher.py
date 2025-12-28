"""Tests for the fetcher module."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from xobliam.fetcher.cache import MessageCache


class TestMessageCache:
    """Tests for MessageCache class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield Path(f.name)

    @pytest.fixture
    def cache(self, temp_db):
        """Create a MessageCache with temporary database."""
        return MessageCache(db_path=temp_db)

    @pytest.fixture
    def sample_messages(self):
        """Sample message data for testing."""
        return [
            {
                "message_id": "msg1",
                "thread_id": "thread1",
                "date": datetime.utcnow().isoformat(),
                "sender": "test@example.com",
                "recipients": "user@example.com",
                "subject": "Test Subject 1",
                "labels": ["INBOX", "UNREAD"],
                "is_unread": True,
                "has_attachments": False,
                "snippet": "This is a test email",
            },
            {
                "message_id": "msg2",
                "thread_id": "thread2",
                "date": (datetime.utcnow() - timedelta(days=30)).isoformat(),
                "sender": "another@example.com",
                "recipients": "user@example.com",
                "subject": "Test Subject 2",
                "labels": ["INBOX"],
                "is_unread": False,
                "has_attachments": True,
                "snippet": "Another test email",
            },
        ]

    def test_cache_messages(self, cache, sample_messages):
        """Test caching messages."""
        count = cache.cache_messages(sample_messages)
        assert count == 2

    def test_get_cached_messages(self, cache, sample_messages):
        """Test retrieving cached messages."""
        cache.cache_messages(sample_messages)
        messages = cache.get_cached_messages()

        assert len(messages) == 2
        assert messages[0]["message_id"] == "msg1"
        assert messages[0]["is_unread"] is True
        assert messages[0]["labels"] == ["INBOX", "UNREAD"]

    def test_get_cached_messages_with_days_filter(self, cache, sample_messages):
        """Test filtering messages by days."""
        cache.cache_messages(sample_messages)

        # Get messages from last 7 days (should only get msg1)
        recent = cache.get_cached_messages(since_days=7)
        assert len(recent) == 1
        assert recent[0]["message_id"] == "msg1"

    def test_get_single_message(self, cache, sample_messages):
        """Test retrieving a single message."""
        cache.cache_messages(sample_messages)

        msg = cache.get_message("msg1")
        assert msg is not None
        assert msg["sender"] == "test@example.com"

        # Non-existent message
        msg = cache.get_message("nonexistent")
        assert msg is None

    def test_cache_labels(self, cache):
        """Test caching labels."""
        labels = [
            {"id": "Label_1", "name": "Work", "type": "user", "messagesTotal": 100},
            {"id": "Label_2", "name": "Personal", "type": "user", "messagesTotal": 50},
        ]

        count = cache.cache_labels(labels)
        assert count == 2

        cached = cache.get_cached_labels()
        assert len(cached) == 2
        assert cached[0]["name"] in ("Work", "Personal")

    def test_is_fresh(self, cache, sample_messages):
        """Test cache freshness check."""
        # Empty cache is not fresh
        assert cache.is_fresh() is False

        # After caching, should be fresh
        cache.cache_messages(sample_messages)
        assert cache.is_fresh(max_age_hours=1) is True

    def test_get_message_count(self, cache, sample_messages):
        """Test message count."""
        assert cache.get_message_count() == 0

        cache.cache_messages(sample_messages)
        assert cache.get_message_count() == 2

    def test_clear(self, cache, sample_messages):
        """Test clearing cache."""
        cache.cache_messages(sample_messages)
        assert cache.get_message_count() == 2

        cache.clear()
        assert cache.get_message_count() == 0
        assert cache.is_fresh() is False

    def test_delete_messages(self, cache, sample_messages):
        """Test deleting specific messages."""
        cache.cache_messages(sample_messages)
        assert cache.get_message_count() == 2

        deleted = cache.delete_messages(["msg1"])
        assert deleted == 1
        assert cache.get_message_count() == 1

        # Verify correct message was deleted
        remaining = cache.get_cached_messages()
        assert remaining[0]["message_id"] == "msg2"


class TestMessageParsing:
    """Tests for message parsing functions."""

    def test_parse_email_address(self):
        """Test email address parsing."""
        from xobliam.fetcher.messages import parse_email_address

        assert parse_email_address("test@example.com") == "test@example.com"
        assert parse_email_address("Test User <test@example.com>") == "test@example.com"
        assert parse_email_address("TEST@EXAMPLE.COM") == "test@example.com"

    def test_get_header_value(self):
        """Test header value extraction."""
        from xobliam.fetcher.messages import get_header_value

        headers = [
            {"name": "From", "value": "sender@example.com"},
            {"name": "Subject", "value": "Test Subject"},
            {"name": "Date", "value": "Mon, 1 Jan 2024 12:00:00 +0000"},
        ]

        assert get_header_value(headers, "From") == "sender@example.com"
        assert get_header_value(headers, "subject") == "Test Subject"  # Case insensitive
        assert get_header_value(headers, "NonExistent") == ""

    def test_has_attachments(self):
        """Test attachment detection."""
        from xobliam.fetcher.messages import has_attachments

        # No attachments
        payload = {"parts": [{"mimeType": "text/plain"}]}
        assert has_attachments(payload) is False

        # With attachment
        payload = {"parts": [{"filename": "document.pdf"}]}
        assert has_attachments(payload) is True

        # Nested attachment
        payload = {"parts": [{"parts": [{"filename": "nested.pdf"}]}]}
        assert has_attachments(payload) is True
