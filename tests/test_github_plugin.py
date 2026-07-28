"""Tests for GitHub Integration Plugin (Feature 26)."""

import pytest
from src.plugins.github_integration import GitHubPlugin, _parse_github_args


class TestParseArgs:
    """Test argument parsing."""

    def test_repo_command(self):
        result = _parse_github_args("/github repo owner/repo")
        assert result is not None
        assert result["action"] == "repo"
        assert result["repo"] == "owner/repo"

    def test_issues_command(self):
        result = _parse_github_args("/github issues owner/repo")
        assert result is not None
        assert result["action"] == "issues"

    def test_non_github_text(self):
        result = _parse_github_args("Hello, how are you?")
        assert result is None

    def test_no_repo_match(self):
        result = _parse_github_args("github info")
        assert result is None

    def test_readme_command(self):
        result = _parse_github_args("/github readme owner/repo")
        assert result is not None
        assert result["action"] == "readme"


class TestGitHubPlugin:
    """Test GitHub plugin behavior."""

    def test_plugin_name(self):
        plugin = GitHubPlugin()
        assert plugin.name == "github"

    def test_plugin_description(self):
        plugin = GitHubPlugin()
        assert "github" in plugin.description.lower() or "tích hợp" in plugin.description.lower()

    def test_empty_input(self):
        plugin = GitHubPlugin()
        result = plugin.execute("")
        assert result.success is False
        assert result.output == ""

    def test_no_github_keyword(self):
        plugin = GitHubPlugin()
        result = plugin.execute("What's the weather like?")
        assert result.success is False
        assert result.output == ""

    def test_missing_repo(self):
        plugin = GitHubPlugin()
        result = plugin.execute("github")
        assert result.success is False

    def test_nonexistent_repo(self, mocker):
        """Test handling of 404 response."""
        mock_response = mocker.MagicMock()
        mock_response.status_code = 404
        mock_requests = mocker.patch("src.plugins.github_integration.requests")
        mock_requests.get.return_value = mock_response

        plugin = GitHubPlugin(token="test_token")
        result = plugin.execute("/github repo nonexistent/repo")
        assert result.success is False
        assert "không tồn tại" in result.output.lower() or "not exist" in result.output.lower()
