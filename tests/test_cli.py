"""
Unit tests for the CLI tool (src/cli/main.py).

Tests use Typer's CliRunner to simulate CLI invocations
and mock the backend initialization to avoid real DB/settings.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.plugin import PluginResult

runner = CliRunner()


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_backend():
    """Mock the entire _init_backend function."""
    mock_settings = MagicMock()
    mock_settings.model_provider = "mock"
    mock_settings.memory_path = ":memory:"
    mock_settings.max_context_messages = 10
    mock_settings.to_dict.return_value = {
        "model_provider": "mock",
        "ollama_url": "http://localhost:11434",
        "log_level": "INFO",
        "max_context_messages": 10,
    }

    mock_memory = MagicMock()
    mock_memory.list_sessions.return_value = []
    mock_memory.create_session.return_value = "test_session_01"
    mock_memory.get_session.return_value = MagicMock(
        id="test_session_01", name="Test Session",
        created_at="2024-01-01T00:00:00Z", updated_at="2024-01-01T00:00:00Z",
        message_count=5,
    )

    mock_model_router = MagicMock()
    mock_model_router.model.model_name = "mock-v1"

    mock_plugin_loader = MagicMock()
    mock_plugin_loader.list_plugins.return_value = [
        {"name": "calculator", "description": "Basic math"},
        {"name": "weather", "description": "Weather forecast"},
    ]
    mock_plugin_loader.get.return_value = MagicMock()

    mock_kb = MagicMock()
    mock_kb.list_documents.return_value = []
    mock_kb.get_stats.return_value = {"documents": 0, "chunks": 0}
    mock_kb.add_file.return_value = "doc_12345"

    mock_workflow = MagicMock()
    mock_workflow.process.return_value = MagicMock(
        source="llm",
        output_text="Hello from Mock!",
        response=MagicMock(text="Hello from Mock!"),
        plugin_result=None,
        context_used=2,
        latency_ms=150.0,
        success=True,
    )
    mock_workflow.get_stats.return_value = {
        "total_processed": 5,
        "total_llm_calls": 3,
        "total_plugin_calls": 2,
        "total_kb_lookups": 0,
        "total_cache_hits": 1,
        "context_limit": 10,
    }

    return (
        mock_settings,
        mock_memory,
        mock_model_router,
        mock_plugin_loader,
        mock_kb,
        mock_workflow,
    )


# ============================================================
# Basic App Tests
# ============================================================


class TestCliBasic:
    def test_help(self):
        """--help should display available commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "chat" in result.stdout
        assert "sessions" in result.stdout
        assert "knowledge" in result.stdout
        assert "plugins" in result.stdout
        assert "config" in result.stdout
        assert "version" in result.stdout

    def test_version(self):
        """--version should show version info (via version command)."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "project-atlas" in result.stdout.lower() or "v" in result.stdout

    def test_no_args_shows_help(self):
        """No arguments should show help."""
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Usage" in result.stdout or "Commands" in result.stdout


# ============================================================
# Chat Command Tests
# ============================================================


class TestChatCommand:
    def test_chat_single_message(self, mock_backend):
        """Single message chat should return a response."""
        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["chat", "Hello!"])

        assert result.exit_code == 0
        assert "Hello from Mock" in result.stdout

    def test_chat_empty_message_shows_error(self, mock_backend):
        """Empty message should not crash."""
        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["chat", ""])

        assert result.exit_code == 0  # Should handle gracefully

    def test_chat_with_session(self, mock_backend):
        """Chat with explicit session ID should work."""
        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["chat", "Hello!", "--session", "existing_id"])

        assert result.exit_code == 0

    def test_chat_workflow_error(self, mock_backend):
        """Workflow error should be caught."""
        mock_settings, mock_memory, mock_model_router, mock_plugin_loader, mock_kb, mock_workflow = mock_backend
        mock_workflow.process.side_effect = Exception("API connection failed")

        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["chat", "Hello!"])

        assert result.exit_code == 1


# ============================================================
# Sessions Command Tests
# ============================================================


class TestSessionsCommand:
    def test_sessions_list(self, mock_backend):
        """sessions list should show sessions."""
        mock_settings, mock_memory, *_ = mock_backend
        mock_memory.list_sessions.return_value = [
            MagicMock(id="s1", name="Chat 1", message_count=3, updated_at="2024-01-01T00:00:00Z"),
            MagicMock(id="s2", name="Chat 2", message_count=5, updated_at="2024-01-02T00:00:00Z"),
        ]

        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["sessions", "list"])

        assert result.exit_code == 0
        assert "s1" in result.stdout
        assert "Chat 1" in result.stdout
        assert "s2" in result.stdout

    def test_sessions_list_empty(self, mock_backend):
        """sessions list with no sessions should show message."""
        mock_settings, mock_memory, *_ = mock_backend
        mock_memory.list_sessions.return_value = []

        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["sessions", "list"])

        assert result.exit_code == 0
        assert "No sessions" in result.stdout

    def test_sessions_show(self, mock_backend):
        """sessions show should display session details."""
        mock_settings, mock_memory, *_ = mock_backend
        mock_memory.get_session.return_value = MagicMock(
            id="s1", name="Chat 1", message_count=3,
            created_at="2024-01-01T00:00:00Z", updated_at="2024-01-01T00:00:00Z",
        )
        mock_memory.get_messages.return_value = [
            MagicMock(id=1, role="user", content="Hello", session_id="s1",
                      created_at="2024-01-01T00:00:00Z", tokens=0),
            MagicMock(id=2, role="assistant", content="Hi there!", session_id="s1",
                      created_at="2024-01-01T00:00:00Z", tokens=0),
        ]

        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["sessions", "show", "s1"])

        assert result.exit_code == 0
        assert "Chat 1" in result.stdout
        assert "Hello" in result.stdout

    def test_sessions_show_not_found(self, mock_backend):
        """sessions show for non-existent ID should error."""
        mock_settings, mock_memory, *_ = mock_backend
        mock_memory.get_session.return_value = None

        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["sessions", "show", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_sessions_delete(self, mock_backend):
        """sessions delete with --force should work."""
        mock_settings, mock_memory, *_ = mock_backend
        mock_memory.get_session.return_value = MagicMock(
            id="s1", name="Chat 1", message_count=3,
        )

        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["sessions", "delete", "s1", "--force"])

        assert result.exit_code == 0
        mock_memory.delete_session.assert_called_once_with("s1")

    def test_sessions_rename(self, mock_backend):
        """sessions rename should update name."""
        mock_settings, mock_memory, *_ = mock_backend
        mock_memory.get_session.return_value = MagicMock(
            id="s1", name="Old Name", message_count=3,
        )

        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["sessions", "rename", "s1", "New Name"])

        assert result.exit_code == 0
        mock_memory.update_session_name.assert_called_once_with("s1", "New Name")
        assert "New Name" in result.stdout


# ============================================================
# Knowledge Command Tests
# ============================================================


class TestKnowledgeCommand:
    def test_knowledge_list(self, mock_backend):
        """knowledge list should show documents."""
        mock_settings, _, _, _, mock_kb, _ = mock_backend
        mock_kb.list_documents.return_value = [
            MagicMock(id="doc1", filename="test.txt", chunk_count=5, char_count=1000),
        ]

        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["knowledge", "list"])

        assert result.exit_code == 0
        assert "test.txt" in result.stdout

    def test_knowledge_list_empty(self, mock_backend):
        """knowledge list with no docs should show message."""
        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["knowledge", "list"])

        assert result.exit_code == 0
        assert "No documents" in result.stdout

    def test_knowledge_upload(self, mock_backend, tmp_path):
        """knowledge upload should process a file."""
        # Create a temp file
        test_file = tmp_path / "hello.txt"
        test_file.write_text("Hello, this is a test document!")

        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["knowledge", "upload", str(test_file)])

        assert result.exit_code == 0
        assert "Uploaded" in result.stdout or "upload" in result.stdout.lower()

    def test_knowledge_upload_unsupported_type(self, mock_backend, tmp_path):
        """knowledge upload with unsupported type should error."""
        test_file = tmp_path / "image.png"
        test_file.write_text("fake png content")

        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["knowledge", "upload", str(test_file)])

        assert result.exit_code == 1
        assert "unsupported" in result.stdout.lower()

    def test_knowledge_upload_nonexistent_file(self, mock_backend):
        """knowledge upload with missing file should error."""
        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["knowledge", "upload", "nonexistent.pdf"])

        assert result.exit_code != 0  # Typer validates file existence


# ============================================================
# Plugins Command Tests
# ============================================================


class TestPluginsCommand:
    def test_plugins_list(self, mock_backend):
        """plugins list should show available plugins."""
        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["plugins", "list"])

        assert result.exit_code == 0
        assert "calculator" in result.stdout
        assert "weather" in result.stdout

    def test_plugins_run(self, mock_backend):
        """plugins run should execute and display result."""
        mock_settings, _, _, mock_plugin_loader, _, _ = mock_backend
        mock_plugin_loader.execute.return_value = PluginResult(
            success=True, output="2 + 3 = 5", data=5,
        )

        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["plugins", "run", "calculator", "2 + 3"])

        assert result.exit_code == 0
        assert "2 + 3 = 5" in result.stdout

    def test_plugins_run_error(self, mock_backend):
        """plugins run that fails should show error."""
        mock_settings, _, _, mock_plugin_loader, _, _ = mock_backend
        mock_plugin_loader.execute.return_value = PluginResult(
            success=False, error="Invalid input",
        )

        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["plugins", "run", "calculator", "invalid"])

        assert result.exit_code == 0  # Still 0 because we handle the error gracefully
        assert "Invalid input" in result.stdout

    def test_plugins_run_not_found(self, mock_backend):
        """plugins run with non-existent name should error."""
        mock_settings, _, _, mock_plugin_loader, _, _ = mock_backend
        mock_plugin_loader.get.return_value = None
        mock_plugin_loader.list_plugins.return_value = [
            {"name": "calculator", "description": "desc"},
        ]

        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["plugins", "run", "nonexistent", "input"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()


# ============================================================
# Config Command Tests
# ============================================================


class TestConfigCommand:
    def test_config_show(self, mock_backend):
        """config show should display configuration."""
        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["config"])

        assert result.exit_code == 0
        assert "model_provider" in result.stdout or "mock" in result.stdout

    def test_config_show_with_secrets(self, mock_backend):
        """config with --show-secrets should show masked values."""
        with patch("src.cli.main._init_backend", return_value=mock_backend):
            result = runner.invoke(app, ["config", "--show-secrets"])

        assert result.exit_code == 0
