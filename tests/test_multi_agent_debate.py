"""Tests for Multi-Agent Debate (Feature 63)."""

import pytest
from src.core.multi_agent_debate import DebateOrchestrator, DebateResult, DebateRound


class TestDebateResult:
    """Test DebateResult data model."""

    def test_empty_result(self):
        result = DebateResult(topic="Test topic")
        assert result.topic == "Test topic"
        assert result.rounds == []
        assert result.total_rounds == 0

    def test_to_dict(self):
        result = DebateResult(
            topic="AI Regulation",
            total_rounds=2,
            total_calls=5,
            latency_ms=15000.0,
            conclusion="Balanced conclusion here",
        )
        d = result.to_dict()
        assert d["topic"] == "AI Regulation"
        assert d["total_rounds"] == 2
        assert d["conclusion"] == "Balanced conclusion here"


class TestDebateRound:
    """Test DebateRound data model."""

    def test_round_attributes(self):
        r = DebateRound(
            round_number=1,
            pro_argument="Pro says this",
            con_argument="Con says that",
        )
        assert r.round_number == 1
        assert r.pro_argument == "Pro says this"
        assert r.con_argument == "Con says that"


class TestDebateOrchestrator:
    """Test debate orchestrator with mocks."""

    def test_init(self, mocker):
        mock_router = mocker.MagicMock()
        orch = DebateOrchestrator(mock_router, rounds=3)
        assert orch._default_rounds == 3

    def test_debate_with_mock(self, mocker):
        """Test debate flow with mock responses."""
        mock_router = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.text = "This is a test argument from the agent."
        mock_router.generate.return_value = mock_response

        orch = DebateOrchestrator(mock_router, rounds=1)

        result = orch.debate(
            topic="Should AI be regulated?",
            rounds=1,
        )

        assert isinstance(result, DebateResult)
        assert result.topic == "Should AI be regulated?"
        assert result.total_rounds == 1
        assert len(result.rounds) == 1

    def test_debate_router_called(self, mocker):
        """Test that model router is called for each agent."""
        mock_router = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.text = "Argument text"
        mock_router.generate.return_value = mock_response

        orch = DebateOrchestrator(mock_router, rounds=1)
        orch.debate("Test topic", rounds=1)

        # Should be called at least 3 times: pro, con, judge
        assert mock_router.generate.call_count >= 3

    def test_debate_result_has_conclusion(self, mocker):
        mock_router = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.text = "Argument text"
        mock_router.generate.return_value = mock_response

        orch = DebateOrchestrator(mock_router, rounds=1)
        result = orch.debate("Test topic", rounds=1)

        assert isinstance(result.conclusion, str)
        assert len(result.conclusion) > 0

    def test_custom_agent_roles(self, mocker):
        mock_router = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.text = "Argument"
        mock_router.generate.return_value = mock_response

        orch = DebateOrchestrator(mock_router)
        result = orch.debate(
            "Test topic",
            rounds=1,
            pro_role="Tech CEO",
            con_role="Ethics Professor",
        )
        assert result.pro_agent_name == "Tech CEO"
        assert result.con_agent_name == "Ethics Professor"
