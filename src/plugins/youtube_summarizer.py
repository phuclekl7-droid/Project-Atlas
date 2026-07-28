"""
YouTube Video Summarizer Plugin — tóm tắt nội dung video YouTube (Feature 60).

Sử dụng youtube-transcript-api để lấy phụ đề, sau đó gửi cho LLM để tóm tắt.
Không cần API key cho transcript, nhưng cần LLM để tóm tắt.

Usage:
    "https://www.youtube.com/watch?v=... tóm tắt"
    "youtube dQw4w9WgXcQ summarize"
    "tóm tắt video https://youtu.be/..."
"""

import re
from typing import Optional

from src.plugin import BasePlugin, PluginResult

# Try to import youtube-transcript-api
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.formatters import TextFormatter
    YT_TRANSCRIPT_AVAILABLE = True
except ImportError:
    YT_TRANSCRIPT_AVAILABLE = False


def _extract_video_id(text: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats or direct ID."""
    # Pattern 1: https://www.youtube.com/watch?v=VIDEO_ID
    match = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})", text)
    if match:
        return match.group(1)
    
    # Pattern 2: Direct video ID (11 chars)
    match = re.search(r"\b([a-zA-Z0-9_-]{11})\b", text)
    if match:
        return match.group(1)
    
    return None


def _is_youtube_query(text: str) -> bool:
    """Check if the text looks like a YouTube summarization request."""
    lowered = text.lower().strip()
    patterns = [
        r"youtube\.com/watch",
        r"youtu\.be/",
        r"\byoutube\s+",
        r"tóm tắt\s+(?:video\s+)?(?:youtube|yt)",
        r"summarize\s+(?:youtube|video)",
    ]
    for pattern in patterns:
        if re.search(pattern, lowered):
            return True
    
    # Check for direct video ID
    if _extract_video_id(text) and any(w in lowered for w in ["tóm tắt", "summarize", "tổng hợp", "nội dung"]):
        return True
    
    return False


def _fetch_transcript(video_id: str) -> Optional[str]:
    """Fetch video transcript using youtube-transcript-api."""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        formatter = TextFormatter()
        text = formatter.format_transcript(transcript)
        # Limit to first 10000 chars to avoid token overflow
        if len(text) > 10000:
            text = text[:10000] + "\n\n[Transcript truncated at 10000 characters...]"
        return text
    except Exception as e:
        return None


def _fetch_transcript_with_languages(video_id: str) -> Optional[dict]:
    """Try to fetch transcript in multiple languages. Returns dict with transcript and language."""
    languages_to_try = ["vi", "en", "ja", "ko", "zh-Hans", "zh-Hant"]
    
    for lang in languages_to_try:
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
            formatter = TextFormatter()
            text = formatter.format_transcript(transcript)
            if len(text) > 10000:
                text = text[:10000] + "\n\n[Transcript truncated at 10000 characters...]"
            return {"text": text, "language": lang}
        except Exception:
            continue
    
    # Try without language (auto-detect)
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Try to find a manually created transcript first
        try:
            transcript = transcript_list.find_manually_created_transcript(["vi", "en"])
        except Exception:
            # Fall back to any generated transcript
            transcript = transcript_list.find_generated_transcript(["vi", "en"])
        text = TextFormatter().format_transcript(transcript.fetch())
        if len(text) > 10000:
            text = text[:10000] + "\n\n[Transcript truncated at 10000 characters...]"
        return {"text": text, "language": transcript.language_code}
    except Exception:
        return None


def _format_transcript_output(video_id: str, transcript_data: dict) -> str:
    """Format the transcript + summarization prompt for the LLM."""
    lang = transcript_data.get("language", "unknown")
    text = transcript_data["text"]
    
    lines = [
        f"## 📺 Video Transcript Analysis",
        f"",
        f"**Video ID**: `{video_id}`",
        f"**Transcript Language**: {lang}",
        f"**Length**: {len(text)} characters",
        f"",
        f"---",
        f"",
        f"### 📝 Transcript Content",
        f"",
        f"```",
        f"{text[:3000]}",  # Show first 3000 chars as preview
        f"```",
        f"",
        f"---",
        f"",
        f"### 🤖 AI Summary",
        f"",
        f"*Hãy hỏi AI để tóm tắt video này. Ví dụ: \"Tóm tắt nội dung chính của video này\"*",
    ]
    
    return "\n".join(lines)


class YouTubeSummarizerPlugin(BasePlugin):
    """
    Tóm tắt nội dung video YouTube bằng phụ đề và AI.
    
    Tự động lấy phụ đề video (ưu tiên tiếng Việt, fallback tiếng Anh),
    hiển thị transcript và cho phép AI tóm tắt nội dung.
    
    Examples:
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ tóm tắt"
        "youtube dQw4w9WgXcQ summarize"
        "tóm tắt video https://youtu.be/..."
    """
    
    name = "youtube_summarizer"
    description = "Lấy phụ đề và tóm tắt nội dung video YouTube"
    
    def execute(self, input_str: str) -> PluginResult:
        """Extract YouTube video ID, fetch transcript, return formatted output."""
        text = input_str.strip()
        
        if not text:
            return PluginResult(
                success=False,
                error="Vui lòng nhập link YouTube. Ví dụ: https://www.youtube.com/watch?v=...",
            )
        
        if not _is_youtube_query(text):
            return PluginResult(
                success=False,
                error="Đây không phải yêu cầu tóm tắt YouTube. Dùng: <link YouTube> + tóm tắt",
            )
        
        # Extract video ID
        video_id = _extract_video_id(text)
        if not video_id:
            return PluginResult(
                success=False,
                error=(
                    "Không tìm thấy Video ID YouTube hợp lệ.\n\n"
                    "Cách dùng:\n"
                    "  • Dán link YouTube: https://www.youtube.com/watch?v=VIDEO_ID\n"
                    "  • Hoặc: https://youtu.be/VIDEO_ID\n"
                    "  • Kèm từ khóa: tóm tắt, summarize, nội dung"
                ),
            )
        
        if not YT_TRANSCRIPT_AVAILABLE:
            return PluginResult(
                success=False,
                error=(
                    "⚠️ Thư viện `youtube-transcript-api` chưa được cài đặt.\n\n"
                    "Cài đặt bằng lệnh:\n"
                    "```\n"
                    "pip install youtube-transcript-api\n"
                    "```\n\n"
                    "Sau đó khởi động lại ứng dụng."
                ),
            )
        
        # Fetch transcript
        try:
            transcript_data = _fetch_transcript_with_languages(video_id)
            if not transcript_data:
                # Try simple fetch
                simple = _fetch_transcript(video_id)
                if simple:
                    transcript_data = {"text": simple, "language": "unknown"}
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Lỗi khi lấy phụ đề: {str(e)[:200]}",
            )
        
        if not transcript_data:
            return PluginResult(
                success=False,
                error=(
                    f"Không thể lấy phụ đề cho video `{video_id}`.\n\n"
                    f"Có thể video không có phụ đề (CC), hoặc bị giới hạn quyền truy cập.\n"
                    f"Thử với video khác."
                ),
            )
        
        # Format output
        output = _format_transcript_output(video_id, transcript_data)
        
        return PluginResult(
            success=True,
            output=output,
            data={
                "video_id": video_id,
                "language": transcript_data.get("language", "unknown"),
                "transcript_length": len(transcript_data["text"]),
                "transcript_preview": transcript_data["text"][:500],
            },
        )
