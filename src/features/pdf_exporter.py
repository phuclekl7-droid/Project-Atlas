"""
PDF Exporter (Feature 173: Export Chat to PDF)

Exports chat sessions as a well-formatted PDF using browser's
@media print CSS rather than server-side libraries (which require
heavy dependencies like pdfkit/weasyprint).

The function generates a self-contained HTML document with embedded
CSS that, when opened in a browser and printed (Ctrl+P → Save as PDF),
produces a clean PDF with chat bubbles.

Usage:
    from src.features.pdf_exporter import export_chat_as_pdf_html
    html = export_chat_as_pdf_html(session_name, messages)
    st.download_button("📄 Tải PDF", data=html, ...)
"""

import base64
import html as html_mod
from datetime import datetime
from typing import Optional


def _escape(text: str) -> str:
    """HTML-escape text for safe embedding."""
    return html_mod.escape(text or "")


def _format_message(role: str, content: str, provider: str = "", index: int = 0) -> str:
    """Format a single message as a chat bubble HTML."""
    is_user = role == "user"
    bubble_class = "bubble-user" if is_user else "bubble-assistant"
    avatar = "👤" if is_user else "🤖"
    align = "right" if is_user else "left"
    bg = "#667eea" if is_user else "#2d2d3f"
    color = "#fff" if is_user else "#e0e0e0"

    return f"""\
<div class="msg-row" style="text-align:{align};">
    <div class="bubble {bubble_class}" style="background:{bg};color:{color};">
        <div class="bubble-header">
            <span class="avatar">{avatar}</span>
            <span class="role">{'Bạn' if is_user else 'AI'}</span>
            {f'<span class="provider">({_escape(provider)})</span>' if provider else ''}
        </div>
        <div class="bubble-content">
            {_escape(content)}
        </div>
    </div>
</div>"""


def _generate_chat_html(
    session_name: str,
    messages: list[dict],
    include_metadata: bool = True,
) -> str:
    """
    Generate a self-contained HTML document for PDF export.

    Uses @media print CSS for clean page breaks and formatting.
    Designed to be saved as PDF via browser's Save as PDF (Ctrl+P).

    Args:
        session_name: Name of the chat session
        messages: List of message dicts with role, content, provider keys
        include_metadata: Whether to include session info header

    Returns:
        Complete HTML document as string
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg_count = len(messages)

    # Build message HTML
    msg_html_parts = []
    for i, msg in enumerate(messages):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        provider = msg.get("provider", "")
        msg_html_parts.append(_format_message(role, content, provider, i))

    messages_html = "\n".join(msg_html_parts)

    metadata_html = ""
    if include_metadata:
        metadata_html = f"""\
<div class="meta">
    <strong>{_escape(session_name)}</strong><br>
    <span class="meta-detail">{msg_count} tin nhắn · Xuất lúc {now}</span>
</div>"""

    return f"""\
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>Chat Export - {_escape(session_name)}</title>
<style>
    @page {{ margin: 1.5cm; }}
    * {{ box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans', sans-serif;
        font-size: 11pt;
        line-height: 1.5;
        color: #1a1a2e;
        background: #fff;
        max-width: 800px;
        margin: 0 auto;
        padding: 1rem;
    }}
    .header {{
        text-align: center;
        padding: 1.5rem 0 1rem;
        border-bottom: 2px solid #667eea;
        margin-bottom: 1.5rem;
    }}
    .header h1 {{ font-size: 1.4rem; color: #1a1a2e; margin: 0; }}
    .header p {{ font-size: 0.8rem; color: #888; margin: 0.3rem 0 0; }}
    .meta {{
        background: #f5f5f5;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 1.5rem;
        font-size: 0.85rem;
    }}
    .meta-detail {{ color: #888; font-size: 0.8rem; }}
    .msg-row {{ margin-bottom: 1rem; page-break-inside: avoid; }}
    .bubble {{
        display: inline-block;
        max-width: 75%;
        padding: 0.6rem 1rem;
        border-radius: 16px;
        text-align: left;
        page-break-inside: avoid;
    }}
    .bubble-user {{ border-bottom-right-radius: 4px; }}
    .bubble-assistant {{ border-bottom-left-radius: 4px; }}
    .bubble-header {{
        font-size: 0.75rem;
        margin-bottom: 0.3rem;
        opacity: 0.8;
        display: flex;
        align-items: center;
        gap: 0.3rem;
    }}
    .bubble-content {{
        font-size: 0.95rem;
        white-space: pre-wrap;
        word-wrap: break-word;
    }}
    .provider {{ font-size: 0.65rem; opacity: 0.6; }}
    .footer {{
        text-align: center;
        font-size: 0.7rem;
        color: #aaa;
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid #eee;
    }}
    @media print {{
        body {{ padding: 0; }}
        .msg-row {{ break-inside: avoid; }}
    }}
</style>
</head>
<body>
    <div class="header">
        <h1>💬 {_escape(session_name)}</h1>
        <p>Project Atlas · {now}</p>
    </div>
    {metadata_html}
    {messages_html}
    <div class="footer">
        Generated by Project Atlas · {msg_count} messages · {now}
    </div>
</body>
</html>"""


def export_chat_as_pdf_html(
    session_name: str,
    messages: list[dict],
    include_metadata: bool = True,
) -> str:
    """
    Export chat to a print-ready HTML document.

    The HTML is designed to be:
    - Saved as PDF via browser (Ctrl+P → Save as PDF)
    - Downloaded as .html and opened in any browser
    - Self-contained (no external dependencies)

    Args:
        session_name: Display name for the session
        messages: List of dicts with role/content/provider
        include_metadata: Include session info in export

    Returns:
        Complete HTML document string
    """
    return _generate_chat_html(session_name, messages, include_metadata)


def count_export_messages(messages: list[dict]) -> int:
    """
    Count messages and return stats.

    Args:
        messages: List of message dicts

    Returns:
        Total message count
    """
    return len(messages)


def get_export_stats(messages: list[dict]) -> dict:
    """
    Get statistics about the export data.

    Args:
        messages: List of message dicts

    Returns:
        Dict with total, user_count, assistant_count, total_chars
    """
    total = len(messages)
    user_count = sum(1 for m in messages if m.get("role") == "user")
    assistant_count = sum(1 for m in messages if m.get("role") == "assistant")
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return {
        "total": total,
        "user_messages": user_count,
        "assistant_messages": assistant_count,
        "total_chars": total_chars,
    }
