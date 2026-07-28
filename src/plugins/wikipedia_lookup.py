"""
Wikipedia Lookup Plugin — tra cứu nhanh định nghĩa từ Wikipedia (Feature 28).

Sử dụng thư viện `wikipedia` (Python wrapper cho Wikipedia API).
Không cần API key — hoàn toàn miễn phí.

Usage:
    "wiki Python"
    "wikipedia Machine Learning"
    "tra cứu Hà Nội"
    "Hà Nội là gì?"
    "what is Artificial Intelligence"
"""

import re
from typing import Optional

from src.plugin import BasePlugin, PluginResult

# Optional: try to import wikipedia-api
try:
    import wikipedia
    WIKIPEDIA_AVAILABLE = True
except ImportError:
    WIKIPEDIA_AVAILABLE = False


def _is_wikipedia_query(text: str) -> bool:
    """Check if the text looks like a Wikipedia lookup request."""
    lowered = text.strip().lower()
    patterns = [
        r"^wiki\s+",
        r"^wikipedia\s+",
        r"^tra cứu\s+",
        r"là gì\??$",
        r"what is\s+",
        r"who is\s+",
        r"meaning of\s+",
        r"định nghĩa\s+",
        r"^what('s| is)\s+",
    ]
    for pattern in patterns:
        if re.search(pattern, lowered):
            return True
    return False


def _extract_term(text: str) -> Optional[str]:
    """Extract the search term from the query text."""
    # Remove leading keywords
    lowered = text.strip().lower()
    
    patterns = [
        (r"^(?:wiki|wikipedia)\s+", ""),
        (r"^tra cứu\s+", ""),
        (r"^(?:what is|what's|who is)\s+", ""),
        (r"\s+(?:là gì|meaning of|định nghĩa)\??$", ""),
        (r"\?$", ""),
    ]
    
    result = lowered
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, count=1)
    
    result = result.strip().rstrip("?.,!;:")
    
    # If extraction removed nothing useful, use the original text
    if not result or len(result) < 2:
        return text.strip().rstrip("?.,!;:")
    
    return result


class WikipediaLookupPlugin(BasePlugin):
    """
    Tra cứu nhanh thông tin từ Wikipedia.
    
    Hỗ trợ tiếng Việt và tiếng Anh. Trả về tóm tắt ngắn gọn
    của bài viết Wikipedia đầu tiên tìm thấy.
    
    Examples:
        "wiki Python"
        "wikipedia Machine Learning"
        "tra cứu Hà Nội"
        "Hà Nội là gì?"
        "what is Artificial Intelligence"
    """
    
    name = "wikipedia"
    description = "Tra cứu nhanh định nghĩa từ Wikipedia (miễn phí, không cần API key)"
    
    def execute(self, input_str: str) -> PluginResult:
        """Search Wikipedia and return article summary."""
        text = input_str.strip()
        
        if not text:
            return PluginResult(
                success=False,
                error="Vui lòng nhập từ khóa cần tra cứu. Ví dụ: wiki Python",
            )
        
        # Only trigger for Wikipedia-like queries
        if not _is_wikipedia_query(text):
            return PluginResult(
                success=False,
                error=f"'{text}' không phải yêu cầu tra Wikipedia. Dùng: wiki <từ khóa>",
            )
        
        if not WIKIPEDIA_AVAILABLE:
            return PluginResult(
                success=False,
                error=(
                    "⚠️ Thư viện `wikipedia` chưa được cài đặt.\n\n"
                    "Cài đặt bằng lệnh:\n"
                    "```\n"
                    "pip install wikipedia\n"
                    "```\n\n"
                    "Sau đó khởi động lại ứng dụng."
                ),
            )
        
        # Extract search term
        term = _extract_term(text)
        if not term:
            return PluginResult(
                success=False,
                error="Không thể trích xuất từ khóa tìm kiếm.",
            )
        
        try:
            # Try Vietnamese Wikipedia first
            wikipedia.set_lang("vi")
            try:
                summary = wikipedia.summary(term, sentences=5)
                page = wikipedia.page(term)
                url = page.url
                title = page.title
            except wikipedia.exceptions.DisambiguationError as e:
                # If ambiguous, try the first option
                options = e.options[:5]
                first_option = options[0]
                try:
                    summary = wikipedia.summary(first_option, sentences=5)
                    page = wikipedia.page(first_option)
                    url = page.url
                    title = page.title
                except Exception:
                    return PluginResult(
                        success=True,
                        output=(
                            f"🔍 Từ khóa '{term}' có nhiều kết quả:\n\n"
                            + "\n".join(f"- {opt}" for opt in options)
                            + "\n\nHãy thử với từ khóa cụ thể hơn."
                        ),
                        data={"term": term, "options": options},
                    )
            except wikipedia.exceptions.PageError:
                # Try English Wikipedia as fallback
                wikipedia.set_lang("en")
                summary = wikipedia.summary(term, sentences=5)
                page = wikipedia.page(term)
                url = page.url
                title = page.title
                lang_note = "\n\n🌐 *Kết quả từ Wikipedia tiếng Anh*"
                return PluginResult(
                    success=True,
                    output=(
                        f"## 📖 {title}\n\n"
                        f"{summary}{lang_note}\n\n"
                        f"🔗 [Đọc thêm]({url})"
                    ),
                    data={
                        "title": title,
                        "summary": summary,
                        "url": url,
                        "language": "en",
                    },
                )
            
            return PluginResult(
                success=True,
                output=(
                    f"## 📖 {title}\n\n"
                    f"{summary}\n\n"
                    f"🔗 [Đọc thêm trên Wikipedia]({url})"
                ),
                data={
                    "title": title,
                    "summary": summary,
                    "url": url,
                    "language": "vi",
                },
            )
            
        except wikipedia.exceptions.WikipediaException as e:
            return PluginResult(
                success=False,
                error=f"Lỗi Wikipedia: {str(e)[:200]}",
            )
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Không thể tra cứu '{term}': {str(e)[:200]}",
            )
