"""Tests for the smart delete module."""

from datetime import datetime, timedelta

import pytest

from xobliam.smart_delete import (
    calculate_safety_score,
    find_deletion_candidates,
    get_safety_tier,
)
from xobliam.smart_delete.safety_scorer import get_score_breakdown


class TestSafetyScorer:
    """Tests for safety scoring."""

    def test_base_score(self):
        """Test that base score is 50."""
        message = {
            "sender": "test@example.com",
            "subject": "Test",
            "snippet": "",
            "is_unread": False,
            "has_attachments": False,
            "labels": [],
            "date": datetime.utcnow().isoformat(),
        }

        # Without any positive or negative signals, score should be around base
        result = calculate_safety_score(message)
        assert isinstance(result, dict)
        assert "score" in result
        assert 40 <= result["score"] <= 60

    def test_unsubscribe_increases_score(self):
        """Test that unsubscribe link increases score."""
        message = {
            "sender": "newsletter@company.com",
            "subject": "Weekly Update",
            "snippet": "Click here to unsubscribe from this newsletter",
            "is_unread": False,
            "has_attachments": False,
            "labels": [],
            "date": datetime.utcnow().isoformat(),
        }

        result = calculate_safety_score(message)
        # Should be higher than base due to unsubscribe signal
        assert result["score"] > 50

    def test_unread_increases_score(self):
        """Test that unread status increases score."""
        read_message = {
            "sender": "test@example.com",
            "subject": "Test",
            "snippet": "",
            "is_unread": False,
            "has_attachments": False,
            "labels": [],
            "date": datetime.utcnow().isoformat(),
        }

        unread_message = {
            **read_message,
            "is_unread": True,
        }

        read_result = calculate_safety_score(read_message)
        unread_result = calculate_safety_score(unread_message)

        assert unread_result["score"] > read_result["score"]

    def test_attachments_decrease_score(self):
        """Test that attachments decrease score."""
        no_attach = {
            "sender": "test@example.com",
            "subject": "Test",
            "snippet": "",
            "is_unread": False,
            "has_attachments": False,
            "labels": [],
            "date": datetime.utcnow().isoformat(),
        }

        with_attach = {
            **no_attach,
            "has_attachments": True,
        }

        no_attach_result = calculate_safety_score(no_attach)
        with_attach_result = calculate_safety_score(with_attach)

        assert with_attach_result["score"] < no_attach_result["score"]

    def test_starred_decreases_score(self):
        """Test that starred/important decreases score."""
        normal = {
            "sender": "test@example.com",
            "subject": "Test",
            "snippet": "",
            "is_unread": False,
            "has_attachments": False,
            "labels": ["INBOX"],
            "date": datetime.utcnow().isoformat(),
        }

        starred = {
            **normal,
            "labels": ["INBOX", "STARRED"],
        }

        normal_result = calculate_safety_score(normal)
        starred_result = calculate_safety_score(starred)

        assert starred_result["score"] < normal_result["score"]

    def test_recent_message_decreases_score(self):
        """Test that recent messages have lower score."""
        recent = {
            "sender": "test@example.com",
            "subject": "Test",
            "snippet": "",
            "is_unread": False,
            "has_attachments": False,
            "labels": [],
            "date": datetime.utcnow().isoformat(),
        }

        old = {
            **recent,
            "date": (datetime.utcnow() - timedelta(days=60)).isoformat(),
        }

        recent_result = calculate_safety_score(recent)
        old_result = calculate_safety_score(old)

        assert old_result["score"] > recent_result["score"]

    def test_user_context_domain(self):
        """Test that user domain affects score."""
        message = {
            "sender": "colleague@mycompany.com",
            "subject": "Meeting",
            "snippet": "",
            "is_unread": False,
            "has_attachments": False,
            "labels": [],
            "date": datetime.utcnow().isoformat(),
        }

        # Without user domain context
        result_no_context = calculate_safety_score(message, {})

        # With user domain (same as sender)
        result_with_context = calculate_safety_score(
            message, {"user_domain": "mycompany.com"}
        )

        # Score should be lower when sender is from user's domain
        assert result_with_context["score"] < result_no_context["score"]

    def test_score_clamped_to_0_100(self):
        """Test that score is always between 0 and 100."""
        # Very safe email
        very_safe = {
            "sender": "promo@marketing.com",
            "subject": "50% off sale",
            "snippet": "Unsubscribe from these promotional emails",
            "is_unread": True,
            "has_attachments": False,
            "labels": [],
            "date": (datetime.utcnow() - timedelta(days=90)).isoformat(),
        }

        # Very risky email
        risky = {
            "sender": "boss@mycompany.com",
            "subject": "Re: Important contract",
            "snippet": "Please review the attached contract",
            "is_unread": False,
            "has_attachments": True,
            "labels": ["STARRED", "IMPORTANT"],
            "date": datetime.utcnow().isoformat(),
            "thread_id": "thread123",
        }

        safe_result = calculate_safety_score(very_safe)
        risky_result = calculate_safety_score(
            risky,
            {
                "user_domain": "mycompany.com",
                "replied_threads": {"thread123"},
            },
        )

        assert 0 <= safe_result["score"] <= 100
        assert 0 <= risky_result["score"] <= 100


class TestScoreBreakdown:
    """Tests for score breakdown."""

    def test_breakdown_structure(self):
        """Test breakdown returns expected structure."""
        message = {
            "sender": "test@example.com",
            "subject": "Test",
            "snippet": "Unsubscribe",
            "is_unread": True,
            "has_attachments": False,
            "labels": [],
            "date": datetime.utcnow().isoformat(),
        }

        breakdown = get_score_breakdown(message)

        assert "score" in breakdown
        assert "factors" in breakdown
        assert isinstance(breakdown["factors"], list)

        # Should have base score factor
        factor_names = [f["factor"] for f in breakdown["factors"]]
        assert "Base score" in factor_names


class TestSafetyTier:
    """Tests for safety tier classification."""

    def test_very_safe_tier(self):
        """Test very safe tier (90-100)."""
        tier = get_safety_tier(95)

        assert tier["name"] == "very_safe"
        assert tier["color"] == "green"
        assert tier["label"] == "Very Safe"

    def test_likely_safe_tier(self):
        """Test likely safe tier (70-89)."""
        tier = get_safety_tier(80)

        assert tier["name"] == "likely_safe"
        assert tier["color"] == "yellow"

    def test_review_tier(self):
        """Test review tier (50-69)."""
        tier = get_safety_tier(60)

        assert tier["name"] == "review"
        assert tier["color"] == "orange"

    def test_keep_tier(self):
        """Test keep tier (<50)."""
        tier = get_safety_tier(30)

        assert tier["name"] == "keep"
        assert tier["color"] == "red"

    def test_boundary_values(self):
        """Test boundary values between tiers."""
        assert get_safety_tier(90)["name"] == "very_safe"
        assert get_safety_tier(89)["name"] == "likely_safe"
        assert get_safety_tier(70)["name"] == "likely_safe"
        assert get_safety_tier(69)["name"] == "review"
        assert get_safety_tier(50)["name"] == "review"
        assert get_safety_tier(49)["name"] == "keep"


class TestCandidateFinder:
    """Tests for deletion candidate finder."""

    @pytest.fixture
    def sample_messages(self):
        """Sample messages with varying safety levels."""
        return [
            {
                "message_id": "safe1",
                "sender": "promo@marketing.com",
                "subject": "Sale!",
                "snippet": "Unsubscribe here",
                "is_unread": True,
                "has_attachments": False,
                "labels": [],
                "date": (datetime.utcnow() - timedelta(days=60)).isoformat(),
            },
            {
                "message_id": "risky1",
                "sender": "boss@work.com",
                "subject": "Re: Project",
                "snippet": "Important update",
                "is_unread": False,
                "has_attachments": True,
                "labels": ["STARRED"],
                "date": datetime.utcnow().isoformat(),
            },
        ]

    def test_find_deletion_candidates(self, sample_messages):
        """Test finding deletion candidates."""
        candidates = find_deletion_candidates(sample_messages, min_score=50)

        assert isinstance(candidates, list)
        assert all("message_id" in c for c in candidates)
        assert all("score" in c for c in candidates)
        assert all("tier" in c for c in candidates)

    def test_candidates_sorted_by_score(self, sample_messages):
        """Test that candidates are sorted by score descending."""
        candidates = find_deletion_candidates(sample_messages, min_score=0)

        scores = [c["score"] for c in candidates]
        assert scores == sorted(scores, reverse=True)

    def test_min_score_filter(self, sample_messages):
        """Test minimum score filtering."""
        candidates_50 = find_deletion_candidates(sample_messages, min_score=50)
        candidates_80 = find_deletion_candidates(sample_messages, min_score=80)

        # Higher threshold should return fewer candidates
        assert len(candidates_80) <= len(candidates_50)

        # All returned candidates should meet threshold
        for c in candidates_80:
            assert c["score"] >= 80
