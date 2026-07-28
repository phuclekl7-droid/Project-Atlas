"""
Tests for Feature #95: Interview Mock Partner.
"""

import pytest

from src.plugins.interview_mock import InterviewMockPlugin, InterviewSession


class TestInterviewMockPlugin:
    """Tests for the InterviewMockPlugin class."""

    def test_empty_input(self):
        plugin = InterviewMockPlugin()
        result = plugin.execute("")
        assert not result.success

    def test_start_interview(self):
        plugin = InterviewMockPlugin()
        result = plugin.execute("software engineer junior")
        assert result.success
        assert "Mock Interview" in result.output
        assert "software engineer" in result.output.lower()

    def test_start_interview_data_scientist(self):
        plugin = InterviewMockPlugin()
        result = plugin.execute("data scientist senior start")
        assert result.success
        assert "Mock Interview" in result.output
        assert "data scientist" in result.output.lower()

    def test_start_interview_devops(self):
        plugin = InterviewMockPlugin()
        result = plugin.execute("devops mid")
        assert result.success
        assert "devops" in result.output.lower()

    def test_answer_before_question(self):
        """Should fail if no question was asked."""
        plugin = InterviewMockPlugin()
        result = plugin.execute("answer my answer here")
        assert not result.success
        # Should start a new session if "answer" is the first command without a session

    def test_next_without_session(self):
        plugin = InterviewMockPlugin()
        result = plugin.execute("next")
        assert not result.success

    def test_stop_without_session(self):
        plugin = InterviewMockPlugin()
        result = plugin.execute("stop")
        # It's okay - stop just checks is_active
        assert result.success

    def test_role_level_parsing(self):
        plugin = InterviewMockPlugin()
        result = plugin.execute("product manager senior")
        assert result.success
        assert "product manager" in result.output.lower()

    def test_feedback_without_answers(self):
        plugin = InterviewMockPlugin()
        result = plugin.execute("feedback")
        assert not result.success

    def test_feedback_after_session(self):
        plugin = InterviewMockPlugin()
        # Start interview
        result = plugin.execute("software engineer junior start")
        assert result.success

        # The session should be active now
        session = plugin._sessions.get("default")
        if session and session.is_active:
            # Add a mock answer
            session.answers.append("I would use Python with Flask framework")
            result = plugin.execute("feedback")
            assert result.success
            assert "Feedback" in result.output


class TestInterviewSession:
    """Tests for the InterviewSession dataclass."""

    def test_default_values(self):
        session = InterviewSession()
        assert session.role == "software engineer"
        assert session.level == "mid"
        assert not session.is_active
        assert session.total_questions == 5

    def test_custom_values(self):
        session = InterviewSession(role="devops", level="senior", total_questions=10)
        assert session.role == "devops"
        assert session.level == "senior"
        assert session.total_questions == 10
