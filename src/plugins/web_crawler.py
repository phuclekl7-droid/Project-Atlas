"""
Web Crawler Agent (Feature #65).
Crawls web pages starting from a given URL, extracting content and following links.

Features:
- Start from any URL
- Crawl depth control (1-3 levels)
- Extract page titles, text, and links
- Domain-restricted crawling (stays on same domain by default)
- Max pages limit
- Results formatted as structured markdown

Usage:
    WebCrawlerPlugin.execute("https://example.com depth:2 max:5")
    WebCrawlerPlugin.execute("https://docs.python.org/3/ depth:1 max:3")
"""

import re
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("web_crawler")

# Optional: BeautifulSoup for HTML parsing
try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False


def _is_same_domain(url: str, base_domain: str) -> bool:
    """Check if URL belongs to the same domain."""
    try:
        parsed = urlparse(url)
        return parsed.netloc == base_domain or parsed.netloc == ""
    except Exception:
        return False


def _clean_url(url: str) -> str:
    """Normalize a URL."""
    # Remove fragments, trailing slashes
    url = url.split("#")[0]
    return url.rstrip("/")


def _extract_links(html: str, base_url: str) -> list[str]:
    """Extract all hyperlinks from HTML content."""
    links = []
    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            absolute = urljoin(base_url, href)
            clean = _clean_url(absolute)
            if clean and clean.startswith("http"):
                links.append(clean)
    else:
        # Regex fallback
        for match in re.finditer(r'href=["\'](https?://[^"\']+)["\']', html):
            clean = _clean_url(match.group(1))
            if clean:
                links.append(clean)
    return links


def _extract_title(html: str) -> str:
    """Extract page title from HTML."""
    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        if title_tag and title_tag.get_text(strip=True):
            return title_tag.get_text(strip=True)
    # Regex fallback
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()[:100]
    return "(no title)"


def _extract_text_content(html: str, max_chars: int = 2000) -> str:
    """Extract readable text content from HTML."""
    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r'\s+', ' ', text)
        return text[:max_chars]
    # Regex fallback: remove tags, keep text
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_chars]


def _fetch_page(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch a URL and return its HTML content."""
    try:
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text
    except ImportError:
        logger.error("requests not installed")
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def _crawl(
    start_url: str,
    max_depth: int = 2,
    max_pages: int = 5,
    same_domain: bool = True,
    delay: float = 0.5,
) -> list[dict]:
    """
    Crawl web pages starting from a URL.

    Returns:
        List of dicts with keys: url, title, depth, links_count, text_snippet
    """
    visited: set[str] = set()
    results: list[dict] = []
    base_domain = urlparse(start_url).netloc

    queue = [(start_url, 0)]

    while queue and len(results) < max_pages:
        url, depth = queue.pop(0)

        if url in visited:
            continue
        visited.add(url)

        if same_domain and not _is_same_domain(url, base_domain):
            continue

        html = _fetch_page(url)
        if html is None:
            continue

        title = _extract_title(html)
        text = _extract_text_content(html)
        links = _extract_links(html, url)

        results.append({
            "url": url,
            "title": title,
            "depth": depth,
            "links_count": len(links),
            "text_snippet": text[:500],
        })

        # Enqueue children if within depth limit
        if depth < max_depth:
            for link in links[:10]:  # Limit children per page
                if link not in visited and len(queue) + len(results) < max_pages:
                    queue.append((link, depth + 1))

        time.sleep(delay)  # Polite delay

    return results


class WebCrawlerPlugin(BasePlugin):
    """
    Crawls web pages starting from a URL.

    Parameters (parsed from input text):
    - URL: Starting URL (required)
    - depth:N: Max crawl depth (default: 2, max: 3)
    - max:N: Max pages to crawl (default: 5, max: 10)
    - external: Allow external domains (default: same-domain only)

    Examples:
        "https://example.com depth:2 max:5"
        "https://docs.python.org/3/ depth:1 max:3"
    """

    name = "web_crawler"
    description = "Thu thập thông tin từ nhiều trang web"

    def execute(self, input_str: str) -> PluginResult:
        """Crawl web pages starting from the given URL."""
        text = input_str.strip()
        if not text:
            return PluginResult(
                success=False,
                error="Vui lòng nhập URL bắt đầu.\n\n"
                      "Ví dụ: `https://example.com depth:2 max:5`"
            )

        # Extract parameters
        max_depth = 2
        max_pages = 5
        same_domain = True
        start_url = ""

        # Parse arguments
        depth_match = re.search(r'depth[=:]\s*(\d+)', text, re.IGNORECASE)
        if depth_match:
            max_depth = min(int(depth_match.group(1)), 3)
            text = text.replace(depth_match.group(0), "")

        max_match = re.search(r'max[=:]\s*(\d+)', text, re.IGNORECASE)
        if max_match:
            max_pages = min(int(max_match.group(1)), 10)
            text = text.replace(max_match.group(0), "")

        if "external" in text.lower():
            same_domain = False
            text = text.lower().replace("external", "")

        # Extract URL (first http/https link)
        url_match = re.search(r'(https?://[^\s]+)', text)
        if url_match:
            start_url = url_match.group(1).rstrip("/.,;")
        else:
            return PluginResult(
                success=False,
                error="Không tìm thấy URL hợp lệ. URL phải bắt đầu bằng http:// hoặc https://"
            )

        # Validate URL
        if not _HAS_BS4:
            logger.warning("BeautifulSoup not installed — using regex fallback for HTML parsing")

        try:
            start_time = time.time()
            pages = _crawl(start_url, max_depth=max_depth, max_pages=max_pages, same_domain=same_domain)
            elapsed = (time.time() - start_time) * 1000

            if not pages:
                return PluginResult(
                    success=False,
                    error=f"Không thể truy cập {start_url}. Trang web có thể không khả dụng."
                )

            lines = [
                f"## 🕷️ Web Crawl Results",
                f"",
                f"- **Start URL:** {start_url}",
                f"- **Pages crawled:** {len(pages)}",
                f"- **Max depth:** {max_depth}",
                f"- **Time:** {elapsed:.0f}ms",
                f"- **BeautifulSoup:** {'✅' if _HAS_BS4 else '⚠️ (regex fallback)'}",
                f"",
            ]

            for i, page in enumerate(pages, 1):
                lines.extend([
                    f"### {i}. [{page['title']}]({page['url']})",
                    f"- **Depth:** {page['depth']} | **Links found:** {page['links_count']}",
                    f"- **Preview:**",
                    f"  > {page['text_snippet'][:200]}...",
                    f"",
                ])

            output = "\n".join(lines)
            return PluginResult(success=True, output=output, data={"pages": pages})

        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            return PluginResult(success=False, error=f"Lỗi khi crawl: {e}")
