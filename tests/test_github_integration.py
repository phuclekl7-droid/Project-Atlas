"""
Unit tests for GitHub Integration Plugin.

Tests:
- GitHub argument parsing (_parse_github_args)
- Plugin metadata
- API endpoint calling (mocked requests)
- Repo info formatting
- Issues listing formatting
- PRs listing formatting
- README fetching
- Repo search
- Error handling (404, rate limit, no input, missing requests)
"""

import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.plugin import BasePlugin, PluginResult
from src.plugins.github_integration import (
    GitHubPlugin,
    _parse_github_args,
    GITHUB_API,
)


# ============================================================
# Argument Parsing Tests
# ============================================================


class TestParseGithubArgs:
    def test_repo_command(self):
        result = _parse_github_args("/github repo owner/repo")
        assert result is not None
        assert result["action"] == "repo"
        assert result["repo"] == "owner/repo"

    def test_issues_command(self):
        result = _parse_github_args("show issues for owner/repo")
        assert result is not None
        assert result["action"] == "issues"
        assert result["repo"] == "owner/repo"

    def test_prs_command(self):
        result = _parse_github_args("/github prs owner/repo")
        assert result is not None
        assert result["action"] == "pulls"

    def test_readme_command(self):
        result = _parse_github_args("readme for owner/repo")
        assert result is not None
        assert result["action"] == "readme"

    def test_search_command(self):
        result = _parse_github_args("search machine learning")
        assert result is not None
        assert result["action"] == "search"
        assert "machine learning" in result["repo"]

    def test_no_github_keyword(self):
        """No GitHub-related keywords should return None."""
        result = _parse_github_args("Hello, how are you?")
        assert result is None

    def test_no_repo_pattern(self):
        """GitHub keyword but no owner/repo pattern should return None."""
        result = _parse_github_args("show issues")
        assert result is None

    def test_empty_string(self):
        result = _parse_github_args("")
        assert result is None


# ============================================================
# Plugin Metadata Tests
# ============================================================


class TestGitHubPluginMetadata:
    def test_plugin_name(self):
        plugin = GitHubPlugin()
        assert plugin.name == "github"

    def test_plugin_description(self):
        plugin = GitHubPlugin()
        assert plugin.description is not None
        assert len(plugin.description) > 0

    def test_is_baseplugin_subclass(self):
        assert issubclass(GitHubPlugin, BasePlugin)

    def test_description_with_token(self):
        """With token, description should mention integration."""
        plugin = GitHubPlugin(token="test_token_123")
        desc = plugin.description
        assert "GitHub" in desc or "github" in desc

    def test_description_without_token(self):
        """Without token, description should mention GITHUB_TOKEN."""
        plugin = GitHubPlugin(token="")
        desc = plugin.description.lower()
        assert "token" in desc or "github" in desc


# ============================================================
# Plugin Execution Tests (mocked)
# ============================================================


class TestGitHubPluginExecute:
    def test_empty_input(self):
        plugin = GitHubPlugin()
        result = plugin.execute("")
        assert result.success is False
        assert result.output == ""

    def test_non_github_input(self):
        """Plain text without GitHub keywords should return empty."""
        plugin = GitHubPlugin()
        result = plugin.execute("Hello, how are you?")
        assert result.success is False
        assert result.output == ""

    def test_missing_requests(self, monkeypatch):
        """Without requests library, should return error."""
        monkeypatch.setattr("src.plugins.github_integration._HAS_REQUESTS", False)
        plugin = GitHubPlugin(token="test_token")
        result = plugin.execute("repo owner/repo")
        assert result.success is False
        assert "requests" in result.output


# ============================================================
# Repo Info Tests (mocked)
# ============================================================


class TestGitHubRepoInfo:
    @pytest.fixture
    def mock_repo_response(self):
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {
            "full_name": "owner/test-repo",
            "description": "A test repository",
            "stargazers_count": 100,
            "forks_count": 20,
            "open_issues_count": 5,
            "html_url": "https://github.com/owner/test-repo",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-06-01T00:00:00Z",
            "license": {"spdx_id": "MIT"},
        }
        return mock

    def test_successful_repo(self, mock_repo_response):
        plugin = GitHubPlugin(token="test_token")
        with patch("src.plugins.github_integration.requests.get", return_value=mock_repo_response):
            result = plugin.execute("repo owner/test-repo")

        assert result.success is True
        assert "owner/test-repo" in result.output
        assert "100" in result.output  # Stars
        assert "stars" in result.output.lower()

    def test_repo_404(self):
        """404 should return error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        plugin = GitHubPlugin(token="test_token")
        with patch("src.plugins.github_integration.requests.get", return_value=mock_resp):
            result = plugin.execute("repo nonexistent/repo")

        assert result.success is False
        assert "không tồn tại" in result.output.lower() or "404" in result.output

    def test_repo_rate_limited(self):
        """403 rate limit should return error with suggestion."""
        mock_resp = MagicMock()
        mock_resp.status_code = 403

        plugin = GitHubPlugin(token="test_token")
        with patch("src.plugins.github_integration.requests.get", return_value=mock_resp):
            result = plugin.execute("repo owner/repo")

        assert result.success is False
        assert "rate limit" in result.output.lower() or "GITHUB_TOKEN" in result.output

    def test_repo_data_contains_metadata(self, mock_repo_response):
        """Result data should have name and stars."""
        plugin = GitHubPlugin(token="test_token")
        with patch("src.plugins.github_integration.requests.get", return_value=mock_repo_response):
            result = plugin.execute("repo owner/test-repo")

        assert result.data is not None
        assert "name" in result.data
        assert "stars" in result.data
        assert result.data["stars"] == 100


# ============================================================
# Issues Tests (mocked)
# ============================================================


class TestGitHubIssues:
    def test_successful_issues(self):
        """List issues should return formatted output."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "number": 1,
                "title": "Bug: something broke",
                "html_url": "https://github.com/owner/repo/issues/1",
                "user": {"login": "user1"},
                "created_at": "2024-01-15T00:00:00Z",
                "labels": [{"name": "bug"}],
            },
            {
                "number": 2,
                "title": "Feature request",
                "html_url": "https://github.com/owner/repo/issues/2",
                "user": {"login": "user2"},
                "created_at": "2024-01-16T00:00:00Z",
                "labels": [{"name": "enhancement"}],
            },
        ]

        plugin = GitHubPlugin(token="test_token")
        with patch("src.plugins.github_integration.requests.get", return_value=mock_resp):
            result = plugin.execute("issues owner/repo")

        assert result.success is True
        assert "#1" in result.output
        assert "#2" in result.output
        assert "Bug" in result.output

    def test_no_issues(self):
        """No issues should return a friendly message."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        plugin = GitHubPlugin(token="test_token")
        with patch("src.plugins.github_integration.requests.get", return_value=mock_resp):
            result = plugin.execute("issues owner/repo")

        assert result.success is True


# ============================================================
# Pull Requests Tests (mocked)
# ============================================================


class TestGitHubPullRequests:
    def test_successful_prs(self):
        """List PRs should return formatted output."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "number": 10,
                "title": "Fix critical bug",
                "html_url": "https://github.com/owner/repo/pull/10",
                "user": {"login": "dev1"},
                "created_at": "2024-01-20T00:00:00Z",
            }
        ]

        plugin = GitHubPlugin(token="test_token")
        with patch("src.plugins.github_integration.requests.get", return_value=mock_resp):
            result = plugin.execute("prs owner/repo")

        assert result.success is True
        assert "!10" in result.output or "#10" in result.output
        assert "Fix" in result.output

    def test_no_prs(self):
        """No PRs should return a friendly message."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []

        plugin = GitHubPlugin(token="test_token")
        with patch("src.plugins.github_integration.requests.get", return_value=mock_resp):
            result = plugin.execute("prs owner/repo")

        assert result.success is True
        assert "không có" in result.output.lower() or "✅" in result.output or "No" in result.output


# ============================================================
# README Tests (mocked)
# ============================================================


class TestGitHubReadme:
    def test_successful_readme(self):
        """README fetch should return content."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "# Test Repository\n\nThis is a test README."

        plugin = GitHubPlugin(token="test_token")
        with patch("src.plugins.github_integration.requests.get", return_value=mock_resp):
            result = plugin.execute("readme owner/repo")

        assert result.success is True
        assert "README" in result.output or "readme" in result.output.lower()

    def test_readme_not_found(self):
        """404 should return error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        plugin = GitHubPlugin(token="test_token")
        with patch("src.plugins.github_integration.requests.get", return_value=mock_resp):
            result = plugin.execute("readme owner/repo")

        assert result.success is False
        assert "không tồn tại" in result.output.lower() or "404" in result.output


# ============================================================
# Search Tests (mocked)
# ============================================================


class TestGitHubSearch:
    def test_successful_search(self):
        """Search should return formatted results."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [
                {
                    "full_name": "owner/repo1",
                    "html_url": "https://github.com/owner/repo1",
                    "stargazers_count": 500,
                    "description": "A useful tool",
                },
            ]
        }

        plugin = GitHubPlugin(token="test_token")
        with patch("src.plugins.github_integration.requests.get", return_value=mock_resp):
            result = plugin.execute("search useful tool")

        assert result.success is True
        assert "repo1" in result.output or "useful" in result.output

    def test_search_no_results(self):
        """Search with no results should return error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"items": []}

        plugin = GitHubPlugin(token="test_token")
        with patch("src.plugins.github_integration.requests.get", return_value=mock_resp):
            result = plugin.execute("search nonexistent_tool_xyz_12345")

        assert result.success is False


# ============================================================
# Error Handling Tests
# ============================================================


class TestGitHubErrors:
    def test_network_error(self):
        """Network error should be caught gracefully."""
        plugin = GitHubPlugin(token="test_token")
        with patch(
            "src.plugins.github_integration.requests.get",
            side_effect=requests.ConnectionError("connection refused"),
        ):
            result = plugin.execute("repo owner/repo")

        assert result.success is False
        assert "Lỗi" in result.output or "Error" in result.output
