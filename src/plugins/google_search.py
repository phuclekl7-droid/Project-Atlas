"""
Google Custom Search API Plugin (Feature 22)

Provides web search using the Google Custom Search JSON API.
Acts as a backup/alternative to the DuckDuckGo search plugin.

Requires:
  - GOOGLE_API_KEY (or google_api_key in settings)
  - GOOGLE_CSE_ID (Custom Search Engine ID)

Usage:
    plugin = GoogleSearchPlugin(api_key="...", cse_id="...")
    result = plugin.execute("What is Python?")
    # Returns up to 5 search results with title, snippet, url
"""

import json
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


GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"


def _extract_query(user_input: str) -> Optional[str]:
    """Extract search query from user input.

    Strips command prefixes like "search", "/google", etc.
    """
    text = user_input.strip()
    prefixes = [
        r"^search\s+", r"^google\s+", r"^/google\s+", r"^/search\s+",
        r"^tìm\s+", r"^tìm kiếm\s+", r"^tra cứu\s+",
    ]
    for prefix in prefixes:
        text = re.sub(prefix, "", text, count=1, flags=re.IGNORECASE)
    text = text.strip().strip(".,!?")
    return text if len(text) >= 2 else None


class GoogleSearchPlugin(BasePlugin):
    """Plugin for web search via Google Custom Search API."""

    def __init__(self, api_key: Optional[str] = None, cse_id: Optional[str] = None):
        """Initialize with API credentials.

        Args:
            api_key: Google API key with Custom Search API enabled
            cse_id: Custom Search Engine ID (cx parameter)
        """
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self._cse_id = cse_id or os.environ.get("GOOGLE_CSE_ID", "")

    @property
    def name(self) -> str:
        return "google_search"

    @property
    def description(self) -> str:
        if self._api_key and self._cse_id:
            return "Tìm kiếm web qua Google Custom Search (backup cho DuckDuckGo)"
        return "Tìm kiếm web qua Google (cần GOOGLE_API_KEY + GOOGLE_CSE_ID)"

    @property
    def available(self) -> bool:
        return bool(self._api_key and self._cse_id and _HAS_REQUESTS)

    def execute(self, user_input: str) -> PluginResult:
        """Execute a Google search.

        Args:
            user_input: Search query or command

        Returns:
            PluginResult with up to 5 search results
        """
        if not user_input or not user_input.strip():
            return PluginResult(success=False, output="", plugin_name=self.name)

        search_keywords = [
            "search", "google", "tìm", "tìm kiếm", "tra cứu",
            "/google", "/search",
            "what is", "who is", "how to",
        ]
        is_search_request = any(kw in user_input.lower() for kw in search_keywords)
        if not is_search_request:
            return PluginResult(success=False, output="", plugin_name=self.name)

        query = _extract_query(user_input)
        if not query:
            return PluginResult(
                success=False,
                output="Vui lòng nhập từ khóa tìm kiếm. Ví dụ: `google Python là gì`",
                plugin_name=self.name,
            )

        if not _HAS_REQUESTS:
            return PluginResult(
                success=False,
                output="⚠️ Thiếu thư viện `requests`. Chạy: `pip install requests`",
                plugin_name=self.name,
            )

        if not self._api_key or not self._cse_id:
            return PluginResult(
                success=False,
                output=(
                    "⚠️ **Chưa cấu hình Google Search API**\n\n"
                    "Cần 2 biến môi trường:\n"
                    "- `GOOGLE_API_KEY`\n"
                    "- `GOOGLE_CSE_ID`\n\n"
                    "Cách tạo:\n"
                    "1. https://console.cloud.google.com/apis/credentials\n"
                    "2. https://cse.google.com/cse/all"
                ),
                plugin_name=self.name,
            )

        try:
            response = requests.get(
                GOOGLE_SEARCH_URL,
                params={
                    "key": self._api_key,
                    "cx": self._cse_id,
                    "q": query,
                    "num": 5,
                    "lr": "lang_vi",
                },
                timeout=10,
            )

            if response.status_code == 403:
                return PluginResult(
                    success=False,
                    output="❌ API key không có quyền hoặc đã hết hạn",
                    plugin_name=self.name,
                )
            elif response.status_code == 429:
                return PluginResult(
                    success=False,
                    output="❌ Vượt quá giới hạn API (thử lại sau)",
                    plugin_name=self.name,
                )
            elif response.status_code != 200:
                return PluginResult(
                    success=False,
                    output=f"❌ Lỗi API: {response.status_code}",
                    plugin_name=self.name,
                )

            data = response.json()
            items = data.get("items", [])

            if not items:
                return PluginResult(
                    success=False,
                    output=f"🔍 Không tìm thấy kết quả cho: `{query}`",
                    plugin_name=self.name,
                )

            lines = [f"### 🔍 Kết quả Google cho: {query}\n"]
            results_data = []

            for i, item in enumerate(items[:5], 1):
                title = item.get("title", "Không có tiêu đề")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                lines.append(f"{i}. **[{title}]({link})**")
                if snippet:
                    lines.append(f"   > {snippet[:200]}")
                lines.append("")
                results_data.append({
                    "title": title,
                    "snippet": snippet[:300],
                    "url": link,
                })

            search_time = data.get("searchInformation", {}).get("formattedTotalResults", "?")
            lines.append(f"*Tìm thấy {search_time} kết quả*")

            return PluginResult(
                success=True,
                output="\n".join(lines),
                plugin_name=self.name,
                data=results_data,
            )

        except requests.exceptions.Timeout:
            return PluginResult(
                success=False,
                output="⏱️ Google Search timeout (10s)",
                plugin_name=self.name,
            )
        except requests.exceptions.ConnectionError:
            return PluginResult(
                success=False,
                output="🔌 Mất kết nối mạng",
                plugin_name=self.name,
            )
        except Exception as e:
            return PluginResult(
                success=False,
                output=f"❌ Lỗi: {e}",
                plugin_name=self.name,
            )
