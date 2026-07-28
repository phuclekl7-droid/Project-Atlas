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

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("web_search")

# ── Constants ──

_DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_MAX_RESULTS = 5
_REQUEST_TIMEOUT = 15  # seconds


# ── Optional BeautifulSoup import (fallback when regex fails) ──
try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False


def _search_duckduckgo(query: str, max_results: int = _MAX_RESULTS) -> list[dict]:
    """
    Search DuckDuckGo and return raw results.

    Uses the HTML endpoint (no API key needed).
    First tries regex parsing (fast). Falls back to BeautifulSoup (more robust)
    if regex returns no results but HTML was received, or if bs4 is available.

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

    html_text = response.text

    # Try regex parsing first
    results = _parse_with_regex(html_text, max_results)

    # If regex found nothing but we know bs4 is available, try that
    if not results and _HAS_BS4:
        logger.debug("Regex fallback: no results, retrying with BeautifulSoup...")
        results = _parse_with_bs4(html_text, max_results)

    # If still no results, warn about possible HTML changes
    if not results:
        logger.warning(
            "DuckDuckGo returned HTML but both regex and BeautifulSoup "
            "parsing found no matches — the HTML structure may have changed."
        )
        results.append({
            "title": "⚠️ Không thể parse kết quả",
            "snippet": "DuckDuckGo đã trả về kết quả nhưng cấu trúc HTML có thể đã thay đổi. Hãy thử lại sau.",
            "url": f"https://duckduckgo.com/?q={urllib.parse.quote(query)}",
        })

    return results


def _parse_with_regex(html: str, max_results: int) -> list[dict]:
    """Parse DuckDuckGo HTML results using regex (fast path)."""
    results = []

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
    url_pattern = re.compile(
        r'<a[^>]*class="result__url"[^>]*href="([^"]*)"',
    )

    title_matches = result_pattern.findall(html)
    snippet_matches = snippet_pattern.findall(html)
    url_matches = url_pattern.findall(html)

    for i in range(min(max_results, len(title_matches))):
        title_raw = title_matches[i][1] if i < len(title_matches) else ""
        snippet_raw = snippet_matches[i] if i < len(snippet_matches) else ""
        url_raw = url_matches[i] if i < len(url_matches) else ""

        title = re.sub(r"<[^>]+>", "", title_raw).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet_raw).strip()

        title = _decode_html_entities(title)
        snippet = _decode_html_entities(snippet)
        url = _clean_duckduckgo_url(url_raw)

        if title and url:
            results.append({"title": title, "snippet": snippet, "url": url})

    return results


def _parse_with_bs4(html: str, max_results: int) -> list[dict]:
    """Parse DuckDuckGo HTML results using BeautifulSoup (fallback, more robust)."""
    results = []

    try:
        soup = BeautifulSoup(html, "html.parser")
        # DuckDuckGo result blocks are usually <div class="result"> or <div class="results_links">
        result_blocks = soup.find_all("div", class_=lambda c: c and ("result" in c or "results_links" in c))

        if not result_blocks:
            # Try finding all <a> tags with article-like headings
            for heading in soup.find_all(["h2", "h3", "a"], limit=max_results * 2):
                parent = heading.find_parent(["div", "article", "li"])
                if parent is None:
                    parent = heading  # Use heading itself

                title = heading.get_text(strip=True)
                # Get the nearest link
                link = parent.find("a") if parent != heading else heading
                href = link.get("href", "") if link and hasattr(link, "get") else ""
                snippet_tag = parent.find(["div", "span", "p"], class_=lambda c: c and "snippet" in c.lower()) if parent else None
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                if title and href:
                    url = _clean_duckduckgo_url(href)
                    if url not in [r["url"] for r in results]:
                        results.append({"title": title, "snippet": snippet, "url": url})
                        if len(results) >= max_results:
                            break
            return results

        # Found result blocks via class match
        for block in result_blocks[:max_results]:
            link = block.find("a", href=True)
            if not link:
                continue
            title = link.get_text(strip=True)
            url = _clean_duckduckgo_url(link["href"])

            snippet = ""
            snippet_tag = block.find(["div", "span"], class_=lambda c: c and ("snippet" in c or "description" in c))
            if snippet_tag:
                snippet = snippet_tag.get_text(strip=True)

            if title and url:
                results.append({"title": title, "snippet": snippet, "url": url})

    except Exception as e:
        logger.warning(f"BeautifulSoup parsing failed: {e}")

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
