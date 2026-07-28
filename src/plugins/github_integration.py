"""
GitHub Integration Plugin (Feature 26)

Provides GitHub API access via chat commands:
  - /github repo <owner/repo> — Get repo info
  - /github issues <owner/repo> — List recent issues
  - /github prs <owner/repo> — List open PRs
  - /github readme <owner/repo> — Get README content
  - /github search <query> — Search repos

Requires GITHUB_TOKEN environment variable for authenticated requests.

Usage:
    plugin = GitHubPlugin()
    result = plugin.execute("/github repo phuclekl7-droid/Project-Atlas")
    result = plugin.execute("show me issues for phuclekl7-droid/Project-Atlas")
"""

import os
import re
from typing import Optional

from src.plugin import BasePlugin, PluginResult

_HAS_REQUESTS = False
try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    requests = None  # type: ignore

GITHUB_API = "https://api.github.com"


def _parse_github_args(user_input: str) -> Optional[dict]:
    """Parse GitHub command arguments from user input.

    Recognizes patterns like:
      /github repo owner/repo
      /github issues owner/repo
      show issues for owner/repo
      repo info owner/repo

    Returns:
        Dict with action and repo, or None if not a GitHub request
    """
    text = user_input.strip().lower()

    # Check for GitHub-related keywords
    gh_keywords = ["/github", "github", "repo", "repository", "issue", "pull request", "pr"]
    if not any(kw in text for kw in gh_keywords):
        return None

    # Extract owner/repo pattern
    repo_match = re.search(r"([\w.-]+/[\w.-]+)", user_input)
    if not repo_match:
        return None

    repo = repo_match.group(1).strip("/")

    # Determine action
    if any(w in text for w in ["issue", "/issues"]):
        action = "issues"
    elif any(w in text for w in ["pr", "pull request", "/prs"]):
        action = "pulls"
    elif any(w in text for w in ["readme", "read me"]):
        action = "readme"
    elif any(w in text for w in ["search"]):
        action = "search"
        repo = text.split("search", 1)[1].strip()
    else:
        action = "repo"

    return {"action": action, "repo": repo}


class GitHubPlugin(BasePlugin):
    """Plugin for GitHub API integration."""

    def __init__(self, token: Optional[str] = None):
        """Initialize with optional GitHub token.

        Args:
            token: GitHub personal access token (default: GITHUB_TOKEN env var)
        """
        self._token = token or os.environ.get("GITHUB_TOKEN", "")
        self._headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Project-Atlas/1.0",
        }
        if self._token:
            self._headers["Authorization"] = f"token {self._token}"

    @property
    def name(self) -> str:
        return "github"

    @property
    def description(self) -> str:
        if self._token:
            return "Tích hợp GitHub: xem repo, issues, PRs, README"
        return "Tích hợp GitHub (cần GITHUB_TOKEN để tăng rate limit)"

    def execute(self, user_input: str) -> PluginResult:
        """Execute a GitHub command.

        Args:
            user_input: GitHub command string

        Returns:
            PluginResult with GitHub data
        """
        if not user_input or not user_input.strip():
            return PluginResult(success=False, output="", plugin_name=self.name)

        args = _parse_github_args(user_input)
        if args is None:
            return PluginResult(success=False, output="", plugin_name=self.name)

        if not _HAS_REQUESTS:
            return PluginResult(
                success=False,
                output="⚠️ Thiếu thư viện `requests`. Chạy: `pip install requests`",
                plugin_name=self.name,
            )

        action = args["action"]
        repo = args["repo"]

        try:
            if action == "repo":
                return self._get_repo(repo)
            elif action == "issues":
                return self._list_issues(repo)
            elif action == "pulls":
                return self._list_pulls(repo)
            elif action == "readme":
                return self._get_readme(repo)
            elif action == "search":
                return self._search_repos(repo)
            else:
                return PluginResult(
                    success=False,
                    output=f"Lệnh không hỗ trợ: {action}",
                    plugin_name=self.name,
                )
        except Exception as e:
            return PluginResult(
                success=False,
                output=f"❌ Lỗi: {str(e)[:200]}",
                plugin_name=self.name,
            )

    def _get_repo(self, repo: str) -> PluginResult:
        """Get repository information."""
        resp = requests.get(f"{GITHUB_API}/repos/{repo}", headers=self._headers, timeout=10)
        if resp.status_code == 404:
            return PluginResult(success=False, output=f"❌ Repo không tồn tại: {repo}", plugin_name=self.name)
        if resp.status_code == 403:
            return PluginResult(success=False, output="❌ Rate limit exceeded. Thêm GITHUB_TOKEN.", plugin_name=self.name)
        resp.raise_for_status()
        d = resp.json()

        lines = [
            f"📦 **{d.get('full_name', repo)}**",
            f"",
            f"{d.get('description', 'Không có mô tả')}",
            f"",
            f"⭐ Stars: **{d.get('stargazers_count', 0):,}**  "
            f"🍴 Forks: **{d.get('forks_count', 0):,}**  "
            f"🐛 Issues: **{d.get('open_issues_count', 0):,}**",
            f"📜 License: {d.get('license', {}).get('spdx_id', 'N/A') if d.get('license') else 'N/A'}",
            f"🌐 {d.get('html_url', '')}",
            f"📅 Tạo: {d.get('created_at', '')[:10]}  "
            f"📝 Cập nhật: {d.get('updated_at', '')[:10]}",
        ]
        return PluginResult(success=True, output="\n".join(lines), plugin_name=self.name, data={
            "name": d.get("full_name"), "stars": d.get("stargazers_count"),
        })

    def _list_issues(self, repo: str) -> PluginResult:
        """List recent issues."""
        resp = requests.get(
            f"{GITHUB_API}/repos/{repo}/issues",
            headers=self._headers,
            params={"state": "open", "per_page": 5, "sort": "updated"},
            timeout=10,
        )
        resp.raise_for_status()
        issues = [i for i in resp.json() if "pull_request" not in i]

        if not issues:
            return PluginResult(success=True, output=f"✅ Không có issue mở nào trong {repo}", plugin_name=self.name)

        lines = [f"🐛 **Open Issues — {repo}**\n"]
        for i in issues:
            labels = " ".join(f"`{l['name']}`" for l in i.get("labels", []))
            lines.append(f"- **#{i['number']}** [{i['title']}]({i['html_url']}) {labels}")
            lines.append(f"  👤 {i['user']['login']}  📅 {i['created_at'][:10]}")

        return PluginResult(success=True, output="\n".join(lines), plugin_name=self.name, data={
            "count": len(issues), "repo": repo,
        })

    def _list_pulls(self, repo: str) -> PluginResult:
        """List open pull requests."""
        resp = requests.get(
            f"{GITHUB_API}/repos/{repo}/pulls",
            headers=self._headers,
            params={"state": "open", "per_page": 5, "sort": "updated"},
            timeout=10,
        )
        resp.raise_for_status()
        prs = resp.json()

        if not prs:
            return PluginResult(success=True, output=f"✅ Không có PR mở nào trong {repo}", plugin_name=self.name)

        lines = [f"🔀 **Open Pull Requests — {repo}**\n"]
        for pr in prs:
            lines.append(f"- **!{pr['number']}** [{pr['title']}]({pr['html_url']})")
            lines.append(f"  👤 {pr['user']['login']}  📅 {pr['created_at'][:10]}")

        return PluginResult(success=True, output="\n".join(lines), plugin_name=self.name)

    def _get_readme(self, repo: str) -> PluginResult:
        """Get repository README."""
        resp = requests.get(
            f"{GITHUB_API}/repos/{repo}/readme",
            headers={**self._headers, "Accept": "application/vnd.github.v3.raw"},
            timeout=10,
        )
        if resp.status_code == 404:
            return PluginResult(success=False, output=f"❌ README không tồn tại trong {repo}", plugin_name=self.name)
        resp.raise_for_status()

        content = resp.text[:3000]
        if len(resp.text) > 3000:
            content += "\n\n... [truncated]"

        return PluginResult(
            success=True,
            output=f"📖 **README — {repo}**\n\n```\n{content}\n```",
            plugin_name=self.name,
        )

    def _search_repos(self, query: str) -> PluginResult:
        """Search repositories."""
        resp = requests.get(
            f"{GITHUB_API}/search/repositories",
            headers=self._headers,
            params={"q": query, "per_page": 5, "sort": "stars"},
            timeout=10,
        )
        resp.raise_for_status()
        d = resp.json()
        items = d.get("items", [])

        if not items:
            return PluginResult(success=False, output=f"🔍 Không tìm thấy repo cho: {query}", plugin_name=self.name)

        lines = [f"🔍 **Kết quả tìm kiếm: {query}**\n"]
        for r in items:
            lines.append(f"- **[{r['full_name']}]({r['html_url']})** ⭐ {r['stargazers_count']:,}")
            desc = r.get("description", "")
            if desc:
                lines.append(f"  {desc[:100]}")

        return PluginResult(success=True, output="\n".join(lines), plugin_name=self.name)
