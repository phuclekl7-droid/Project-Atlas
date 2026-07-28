"""
URL Summarizer Plugin

Crawls web pages and summarizes their content using the LLM.
No external API key required — uses requests + BeautifulSoup for crawling.

Usage:
    Plugin: "https://example.com/article"
    Returns: Summary of the article in Vietnamese
"""

import re
import traceback
from typing import Optional
from urllib.parse import urlparse

import requests

from src.plugin import BasePlugin


class URLSummarizerPlugin(BasePlugin):
    """
    Crawls a URL and returns a summary of the page content.
    Supports text content extraction from HTML articles, blogs, and documentation.
    """

    @property
    def name(self) -> str:
        return "url_summarizer"

    @property
    def description(self) -> str:
        return (
            "Nhập link bài báo / trang web, AI sẽ đọc nội dung và tóm tắt. "
            "Ví dụ: https://vnexpress.net/... hoặc https://dev.to/..."
        )

    def execute(self, input_text: str) -> dict:
        """
        Crawl a URL and prepare content for summarization.

        Args:
            input_text: A URL to summarize (e.g., "https://example.com/article")

        Returns:
            dict with keys: success, output, data (list of extracted texts), url
        """
        url = input_text.strip()

        # Extract URL from text if there's extra text around it
        url_match = re.search(r'https?://[^\s<>">\']+', url)
        if url_match:
            url = url_match.group(0)

        if not url.startswith(("http://", "https://")):
            return {
                "success": False,
                "output": "Vui lòng cung cấp một URL hợp lệ (bắt đầu với http:// hoặc https://).",
                "data": [],
                "url": url,
            }

        # Validate URL format
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return {
                    "success": False,
                    "output": f"URL không hợp lệ: {url}",
                    "data": [],
                    "url": url,
                }
        except Exception:
            return {
                "success": False,
                "output": f"URL không hợp lệ: {url}",
                "data": [],
                "url": url,
            }

        # Fetch the page
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            }

            response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            response.raise_for_status()

            # Detect encoding
            content_type = response.headers.get("content-type", "")
            if "charset" in content_type:
                encoding = content_type.split("charset=")[-1].split(";")[0].strip()
            else:
                encoding = response.apparent_encoding or "utf-8"

            html = response.content.decode(encoding, errors="replace")

        except requests.Timeout:
            return {
                "success": False,
                "output": f"⏱️ Không thể truy cập {url} — request timed out sau 15 giây.",
                "data": [],
                "url": url,
            }
        except requests.RequestException as e:
            return {
                "success": False,
                "output": f"❌ Lỗi khi truy cập {url}: {e}",
                "data": [],
                "url": url,
            }

        # Extract text content using BeautifulSoup if available
        text = self._extract_text(html)

        if not text or len(text.strip()) < 50:
            # Fallback: basic HTML tag stripping
            text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            text = text[:5000]

        if not text or len(text.strip()) < 20:
            return {
                "success": False,
                "output": f"Không thể trích xuất nội dung từ {url}. Trang có thể yêu cầu JavaScript.",
                "data": [],
                "url": url,
            }

        # Truncate to reasonable length for LLM context
        max_chars = 4000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[...truncated...]"

        # Return the extracted text for the LLM to summarize
        site_name = parsed.netloc.replace("www.", "")
        summary_prompt = (
            f"📰 **Nguồn:** {site_name}\n"
            f"🔗 **URL:** {url}\n\n"
            f"**Nội dung:**\n{text}\n\n"
            f"Hãy tóm tắt nội dung trên bằng tiếng Việt, "
            f"nêu rõ chủ đề chính, các điểm quan trọng, và kết luận (nếu có)."
        )

        return {
            "success": True,
            "output": summary_prompt,
            "data": [{"text": text, "url": url, "site": site_name}],
            "url": url,
        }

    def _extract_text(self, html: str) -> str:
        """Extract readable text from HTML using BeautifulSoup (fallback to regex)."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Remove unwanted elements
            for tag in soup(["script", "style", "nav", "footer", "header",
                             "aside", "noscript", "iframe", "form", "button"]):
                tag.decompose()

            # Try to find main content area first
            for selector in ["article", "main", "[role=main]", ".post-content",
                             ".article-content", ".entry-content", ".content",
                             "#content", "#article", ".post"]:
                content = soup.select_one(selector)
                if content:
                    text = content.get_text(separator="\n", strip=True)
                    if len(text) > 200:
                        return text

            # Fallback: get all text
            text = soup.get_text(separator="\n", strip=True)
            return text

        except ImportError:
            # BeautifulSoup not available — use regex
            try:
                # Remove scripts and styles
                text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
                text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
                # Get text content from common article tags
                article_match = re.search(
                    r'<(?:article|main|div[^>]*class="[^"]*(?:content|article|post)[^"]*")[^>]*>'
                    r'(.*?)</(?:article|main|div)>',
                    html, re.DOTALL | re.IGNORECASE
                )
                if article_match:
                    text = article_match.group(1)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
                return text
            except Exception:
                return ""
        except Exception:
            return ""
