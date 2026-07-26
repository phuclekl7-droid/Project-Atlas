"""
Web Search Plugin — searches the web using DuckDuckGo (no API key required).

Uses requests (already a dependency) to call DuckDuckGo's HTML search endpoint.
Returns formatted search results with titles, snippets, and URLs.

Usage:
    WebSearchPlugin.execute("Python programming tutorial")
    WebSearchPlugin.execute("latest AI news 2024")
"""

import html
import re
import urllib.parse
from typing import Optional

import requests

from src.plugin import BasePlugin, PluginResult

# ── Constants ──

_DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_MAX_RESULTS = 5
_REQUEST_TIMEOUT = 15  # seconds


def _search_duckduckgo(query: str, max_results: int = _MAX_RESULTS) -> list[dict]:
    """
    Search DuckDuckGo and return raw results.

    Uses the HTML endpoint (no API key needed).
    Parses results using regex on the HTML response.

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        List of dicts with keys: title, snippet, url
    """
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    }

    payload = {
        "q": query,
    }

    try:
        response = requests.post(
            _DUCKDUCKGO_URL,
            data=payload,
            headers=headers,
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise ConnectionError(f"Failed to search DuckDuckGo: {e}")

    # Parse HTML results with regex
    html = response.text
    results = []

    # DuckDuckGo HTML results are in <a class="result__a"> tags
    # Each result block: result__title → result__snippet → result__url
    # We use regex to extract them in order

    # Pattern to find result blocks
    result_pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>'
        r'\s*(.*?)\s*</a>',
        re.DOTALL,
    )

    snippet_pattern = re.compile(
        r'<a[^>]*class="result__snippet"[^>]*>'
        r'\s*(.*?)\s*</a>',
        re.DOTALL,
    )

    # Find all titles first
    title_matches = result_pattern.findall(html)
    snippet_matches = snippet_pattern.findall(html)

    # Find URLs from redirect links
    # DuckDuckGo wraps URLs in <a class="result__url" ...>
    url_pattern = re.compile(
        r'<a[^>]*class="result__url"[^>]*href="([^"]*)"',
    )
    url_matches = url_pattern.findall(html)

    for i in range(min(max_results, len(title_matches))):
        title_raw = title_matches[i][1] if i < len(title_matches) else ""
        snippet_raw = snippet_matches[i] if i < len(snippet_matches) else ""
        url_raw = url_matches[i] if i < len(url_matches) else ""

        # Clean HTML tags from title and snippet
        title = re.sub(r"<[^>]+>", "", title_raw).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet_raw).strip()

            # Decode HTML entities
        title = _decode_html_entities(title)
        snippet = _decode_html_entities(snippet)

        # Clean URL (remove DuckDuckGo redirect wrapper)
        url = _clean_duckduckgo_url(url_raw)

        if title and url:
            results.append({
                "title": title,
                "snippet": snippet,
                "url": url,
            })

    # If HTTP succeeded but no results parsed, warn about possible HTML changes
    if not results and title_matches:
        logger.warning(
            "DuckDuckGo returned results but regex parsing found no matches — "
            "the HTML structure may have changed."
        )
        results.append({
            "title": "⚠️ Không thể parse kết quả",
            "snippet": "DuckDuckGo đã trả về kết quả nhưng cấu trúc HTML có thể đã thay đổi. Hãy thử lại sau.",
            "url": f"https://duckduckgo.com/?q={urllib.parse.quote(query)}",
        })

    return results


def _clean_duckduckgo_url(url: str) -> str:
    """Extract the actual URL from DuckDuckGo's redirect wrapper."""
    # DuckDuckGo URLs look like: //duckduckgo.com/l/?uddg=https%3A%2F%2F...
    # Or direct URLs
    if "uddg=" in url:
        # Extract the uddg parameter
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        if "uddg" in params:
            return params["uddg"][0]
    # Remove leading // if present
    if url.startswith("//"):
        url = "https:" + url
    return url


def _decode_html_entities(text: str) -> str:
    """Decode common HTML entities."""
    return html.unescape(text)


class WebSearchPlugin(BasePlugin):
    """
    Searches the web using DuckDuckGo (no API key needed).

    Returns formatted search results with titles, snippets, and URLs.
    Useful for getting up-to-date information, news, or facts.

    Examples:
        "Python programming tutorial"
        "latest AI news"
        "thời tiết hôm nay"
    """

    name = "web_search"
    description = "Tìm kiếm web với DuckDuckGo (không cần API key)"

    def execute(self, input_str: str) -> PluginResult:
        """
        Search the web and return formatted results.

        Args:
            input_str: Search query (e.g., "Python programming tutorial")

        Returns:
            PluginResult with formatted search results
        """
        query = input_str.strip()

        if not query:
            return PluginResult(
                success=False,
                error="Vui lòng nhập từ khóa tìm kiếm. Ví dụ: Python programming tutorial",
            )

        try:
            results = _search_duckduckgo(query, max_results=_MAX_RESULTS)
        except ConnectionError as e:
            return PluginResult(
                success=False,
                error=f"Không thể kết nối DuckDuckGo: {e}",
            )
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Lỗi tìm kiếm: {e}",
            )

        if not results:
            return PluginResult(
                success=False,
                error=f"Không tìm thấy kết quả cho '{query}'",
            )

        # Format results
        lines = [
            f"## 🔍 Kết quả tìm kiếm cho: {query}\n",
        ]

        for i, r in enumerate(results, 1):
            title = r["title"]
            snippet = r["snippet"][:200] if r["snippet"] else ""
            url = r["url"]

            lines.append(f"### {i}. [{title}]({url})")
            if snippet:
                lines.append(f"> {snippet}")
            lines.append("")  # blank line

        lines.append("---")
        lines.append(f"🔗 Tìm kiếm qua DuckDuckGo • {len(results)} kết quả")

        output = "\n".join(lines)

        return PluginResult(
            success=True,
            output=output,
            data=results,
        )
