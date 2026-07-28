"""
Features Module: Advanced UI features for Project Atlas (v0.8.0)

Contains standalone implementations for:
  - Feature 47: LaTeX Math Rendering (KaTeX CDN)
  - Feature 50: Chat History Search Bar
  - Feature 55: Code Diff Viewer
  - Feature 57: Data Visualization Plotter
  - Feature 59: Export Chat to Markdown/JSON
  - Feature 17: Export & Import Memory DB
  - Feature 79: Local LLM Benchmark Tool

Each function is self-contained and designed to be called from app.py.
"""

import base64
import html
import json
import re
import time
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Optional

import streamlit as st


# ============================================================
# Feature 47: LaTeX Math Rendering (KaTeX CDN)
# ============================================================

def get_katex_html() -> str:
    """Return KaTeX CDN link tags to enable math formula rendering.

    Injects KaTeX CSS + JS into the Streamlit page via st.markdown.
    Call this once in main() after the main CSS injection.
    """
    return """<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" crossorigin="anonymous">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js" crossorigin="anonymous"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
    onload="renderMathInElement(document.body, {
        delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false},
            {left: '\\\\\\\\[', right: '\\\\\\\\]', display: true},
            {left: '\\\\\\(', right: '\\\\\\)', display: false}
        ],
        throwOnError: false,
        trust: true
    });"></script>"""


def render_math_markdown(text: str) -> str:
    """Render markdown with safe LaTeX handling.

    If text contains math delimiters ($$, $, \\[, \\]),
    the KaTeX auto-render script will handle them on the client side.
    This function does server-side preprocessing for fallback styling.

    Args:
        text: Markdown content that may contain LaTeX math expressions

    Returns:
        Text with math blocks wrapped in styled divs for KaTeX
    """
    if not text:
        return text
    text = re.sub(
        r'\$\$(.+?)\$\$',
        r'<div class="math-block">$$\1$$</div>',
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r'(?<!\$)\$(.+?)\$(?!\$)',
        r'<span class="math-inline">$\1$</span>',
        text,
    )
    return text


# ============================================================
# Feature 50: Chat History Search Helper
# ============================================================

def search_sessions_ui(memory) -> None:
    """Render the chat history search interface in the sidebar."""
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown("<h3>Search History</h3>", unsafe_allow_html=True)

    search_query = st.text_input(
        "Tim kiem...",
        key="chat_search_v2",
        placeholder="Nhap tu khoa...",
        label_visibility="collapsed",
    )

    if search_query:
        try:
            results = memory.search_sessions(search_query, limit=15)
            if results:
                for s in results:
                    is_active = s.id == st.session_state.get("session_id", "")
                    btn_type = "secondary" if is_active else "tertiary"
                    if st.button(
                        f"{s.name[:55]} ({s.message_count} tin)",
                        key=f"sr2_{s.id}",
                        use_container_width=True,
                        type=btn_type,
                    ):
                        st.session_state.session_id = s.id
                        if "pending_prompt" in st.session_state:
                            del st.session_state.pending_prompt
                        st.rerun()
            else:
                st.caption("Khong tim thay ket qua")
        except Exception:
            st.caption("Loi tim kiem")
    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# Feature 55: Code Diff Viewer
# ============================================================

def _diff_lines(old_text: str, new_text: str) -> list[dict]:
    """Generate a simple line-by-line diff between old and new code."""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    old_set = set(old_lines)
    new_set = set(new_lines)
    result = []
    for line in old_lines:
        result.append({"type": "removed" if line not in new_set else "same", "line": line})
    added_lines = [l for l in new_lines if l not in old_set]
    for line in added_lines:
        result.append({"type": "added", "line": line})
    return result


def render_code_diff(old_code: str, new_code: str, lang: str = "") -> None:
    """Render a side-by-side code diff comparison in the Streamlit UI."""
    st.markdown("### Code Diff")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('<div class="diff-panel-header diff-old">Before</div>', unsafe_allow_html=True)
        st.code(old_code, language=lang or None, line_numbers=True)
    with col_b:
        st.markdown('<div class="diff-panel-header diff-new">After</div>', unsafe_allow_html=True)
        st.code(new_code, language=lang or None, line_numbers=True)
    old_lines = old_code.splitlines()
    new_lines = new_code.splitlines()
    st.caption(
        f"Lines: {len(old_lines)} -> {len(new_lines)} "
        f"({'<span style=\"color:#4ecdc4\">+' if len(new_lines) > len(old_lines) else '<span style=\"color:#ff6b6b\">'}"
        f"{abs(len(new_lines) - len(old_lines))}</span> change)"
    )


# ============================================================
# Feature 57: Data Visualization Plotter
# ============================================================

def detect_plot_data(text: str) -> Optional[dict]:
    """Detect if the user is asking for a data visualization."""
    if not text:
        return None
    lowered = text.lower()
    plot_keywords = [
        "ve bieu do", "bieu do", "chart", "plot", "graph", "visualize",
        "draw", "bieu dien", "do thi", "histogram", "bar chart",
        "line chart", "pie chart", "scatter", "phan tich du lieu",
    ]
    for kw in plot_keywords:
        if kw in lowered:
            chart_type = "bar"
            if any(w in lowered for w in ["line", "duong", "xu huong"]):
                chart_type = "line"
            elif any(w in lowered for w in ["pie", "tron", "ty le"]):
                chart_type = "pie"
            elif any(w in lowered for w in ["scatter", "phantan", "phan tan"]):
                chart_type = "scatter"
            return {"type": chart_type, "title": text[:80], "data_text": text}
    return None


def render_plot_message(message_content: str) -> None:
    """Render a data visualization in the chat if the content contains plot data."""
    if not message_content:
        return
    json_match = re.search(r'```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```', message_content, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if isinstance(data, list) and len(data) > 1:
                import pandas as pd
                df = pd.DataFrame(data)
                if len(df.columns) >= 2:
                    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                    if numeric_cols:
                        st.markdown(
                            '<div class="viz-container"><div class="viz-title">Data Visualization</div></div>',
                            unsafe_allow_html=True,
                        )
                        with st.container():
                            tab1, tab2 = st.tabs(["Bar Chart", "Line Chart"])
                            with tab1:
                                st.bar_chart(df, x=df.columns[0], y=numeric_cols)
                            with tab2:
                                st.line_chart(df, x=df.columns[0], y=numeric_cols)
                        return
            elif isinstance(data, dict) and len(data) > 1:
                st.markdown(
                    '<div class="viz-container"><div class="viz-title">Data Summary</div></div>',
                    unsafe_allow_html=True,
                )
                st.json(data)
                return
        except (json.JSONDecodeError, ImportError):
            pass


# ============================================================
# Feature 59: Export Chat to Markdown / JSON
# ============================================================

def export_session_as_markdown(session_id: str, messages: list[dict]) -> str:
    """Export a chat session as a Markdown string."""
    memory = st.session_state.get("memory")
    session_name = "Chat Export"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    if memory:
        session = memory.get_session(session_id)
        if session:
            session_name = session.name
            created_at = getattr(session, "created_at", created_at)[:19]
    lines = [
        f"# Chat: {session_name}",
        f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Created:** {created_at}",
        f"**Messages:** {len(messages)}",
        "---", "",
    ]
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        provider = msg.get("provider", "")
        if role == "user":
            lines.append(f"## User  {f'({provider})' if provider else ''}")
        elif role == "assistant":
            lines.append(f"## Assistant  {f'({provider})' if provider else ''}")
        else:
            lines.append(f"## {role.capitalize()}")
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")
    lines.append("\n*Exported from Project Atlas v0.7.0*")
    return "\n".join(lines)


def export_session_as_json(session_id: str, messages: list[dict]) -> str:
    """Export a chat session as a JSON string."""
    memory = st.session_state.get("memory")
    session_name = "Chat Export"
    if memory:
        session = memory.get_session(session_id)
        if session:
            session_name = session.name
    export_data = {
        "session_id": session_id,
        "session_name": session_name,
        "exported_at": datetime.now().isoformat(),
        "message_count": len(messages),
        "messages": [
            {
                "role": m.get("role", ""),
                "content": m.get("content", ""),
                "provider": m.get("provider", None),
                "timestamp": m.get("created_at", ""),
            }
            for m in messages
        ],
    }
    return json.dumps(export_data, indent=2, ensure_ascii=False)


def export_session_as_pdf_html(session_name: str, messages: list[dict]) -> str:
    """
    Generate a self-contained HTML doc suitable for print-to-PDF.

    Opens in browser → Ctrl+P → Save as PDF for a clean chat export.

    Args:
        session_name: Name of the chat session
        messages: List of message dicts with role, content, provider keys

    Returns:
        Complete HTML document as string
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    def _esc(text: str) -> str:
        return html.escape(text or "")

    def _fmt_msg(role: str, content: str, provider: str = "") -> str:
        is_user = role == "user"
        align = "right" if is_user else "left"
        bg = "#667eea" if is_user else "#2d2d3f"
        color = "#fff" if is_user else "#e0e0e0"
        avatar = "👤" if is_user else "🤖"
        label = "Bạn" if is_user else "AI"
        prov = f"<span style='opacity:0.6;font-size:0.75rem;'>({_esc(provider)})</span>" if provider else ""
        body = _esc(content).replace("\n", "<br>")
        return (
            f'<div style="text-align:{align};margin-bottom:0.8rem;page-break-inside:avoid;">'
            f'<div style="display:inline-block;background:{bg};color:{color};border-radius:12px;'
            f'padding:0.6rem 1rem;max-width:80%;text-align:left;">'
            f'<div style="font-size:0.75rem;margin-bottom:0.3rem;opacity:0.7;">{avatar} {label} {prov}</div>'
            f'<div style="white-space:pre-wrap;word-wrap:break-word;">{body}</div>'
            f'</div></div>'
        )

    msgs_html = "\n".join(_fmt_msg(m.get("role", ""), m.get("content", ""), m.get("provider", "")) for m in messages)
    count = len(messages)
    name = _esc(session_name) if session_name else "Chat Export"

    return f"""\
<!DOCTYPE html><html lang="vi"><head>
<meta charset="UTF-8">
<title>Chat Export - {name}</title>
<style>
@page {{ margin: 1.5cm; }}
* {{ box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 11pt; line-height: 1.5; color: #1a1a2e; background: #fff;
    max-width: 800px; margin: 0 auto; padding: 1rem;
}}
.header {{ text-align:center; padding:1.5rem 0 1rem; border-bottom:2px solid #667eea; margin-bottom:1.5rem; }}
.header h1 {{ font-size:1.3rem; margin:0; }}
.header p {{ font-size:0.8rem; color:#888; margin:0.3rem 0 0; }}
.footer {{ text-align:center; font-size:0.7rem; color:#aaa; margin-top:2rem; border-top:1px solid #ddd; padding-top:1rem; }}
@media print {{ body {{ font-size:10pt; }} }}
</style>
</head><body>
<div class="header"><h1>Chat: {name}</h1><p>{count} tin nhắn · Xuất lúc {now}</p></div>
{msgs_html}
<div class="footer">Xuất từ Project Atlas · {now}</div>
</body></html>"""


def render_export_buttons(session_id: str, messages: list[dict]) -> None:
    """Render download buttons for exporting the current session."""
    if not messages:
        return
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown("<h3>Export Chat</h3>", unsafe_allow_html=True)
    md_content = export_session_as_markdown(session_id, messages)
    json_content = export_session_as_json(session_id, messages)
    session_name = ""
    memory = st.session_state.get("memory")
    if memory:
        session = memory.get_session(session_id)
        if session:
            session_name = session.name
    pdf_html = export_session_as_pdf_html(session_name, messages)

    col_md, col_json, col_pdf = st.columns([1, 1, 1])
    with col_md:
        st.download_button(
            label="MD", data=md_content,
            file_name=f"chat_{session_id[:8]}.md",
            mime="text/markdown", key=f"export_md_{session_id}",
            use_container_width=True,
        )
    with col_json:
        st.download_button(
            label="JSON", data=json_content,
            file_name=f"chat_{session_id[:8]}.json",
            mime="application/json", key=f"export_json_{session_id}",
            use_container_width=True,
        )
    with col_pdf:
        st.download_button(
            label="PDF", data=pdf_html,
            file_name=f"chat_{session_id[:8]}.pdf",
            mime="text/html", key=f"export_pdf_{session_id}",
            use_container_width=True,
            help="📄 Mở file trong trình duyệt → Ctrl+P → Save as PDF",
        )
    st.caption(f"{len(messages)} messages")
    st.caption("📄 PDF: Mở file → Ctrl+P → Save as PDF")
    st.markdown('</div>', unsafe_allow_html=True)


def auto_detect_and_render(message_content: str) -> None:
    """Auto-detect and render data visualizations in assistant messages."""
    plot_info = detect_plot_data(message_content)
    if plot_info:
        render_plot_message(message_content)


# ============================================================
# Feature 79: Local LLM Benchmark Tool
# ============================================================

def run_benchmark(model_router, num_tokens: int = 50) -> dict:
    """Run a quick benchmark to measure tokens/second for the current model.

    Sends a short test prompt and measures how long it takes to generate
    approximately `num_tokens` tokens. Returns benchmark results.

    Works best with local models (Ollama) since external APIs have network latency
    that skews the measurement.

    Args:
        model_router: The ModelRouter instance
        num_tokens: Target number of tokens to generate

    Returns:
        Dict with keys: tokens_per_sec, latency_ms, num_tokens, provider, model_name
    """
    import asyncio

    benchmark_prompt = (
        f"Please write a short paragraph of approximately {num_tokens} words "
        f"about the weather in Vietnam. Just write the paragraph, no extra text."
    )

    start = time.time()
    try:

        async def _run():
            return await model_router.generate_async(benchmark_prompt)

        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(_run())
        elapsed = (time.time() - start) * 1000  # ms
        generated_tokens = getattr(response, "tokens", 0) or 0

        if generated_tokens > 0 and elapsed > 0:
            tokens_per_sec = (generated_tokens / elapsed) * 1000
        else:
            tokens_per_sec = 0.0

        return {
            "tokens_per_sec": round(tokens_per_sec, 2),
            "latency_ms": round(elapsed, 0),
            "num_tokens": generated_tokens,
            "provider": getattr(response, "provider", "unknown"),
            "model_name": getattr(response, "model_name", "unknown"),
            "success": True,
        }
    except Exception as e:
        return {
            "tokens_per_sec": 0.0,
            "latency_ms": 0.0,
            "num_tokens": 0,
            "provider": "error",
            "model_name": str(e),
            "success": False,
        }


def render_benchmark_ui(model_router) -> None:
    """Render the LLM Benchmark tool in the sidebar.

    Shows a button to run a benchmark and displays results with
    tokens/second chart.
    """
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown("<h3>LLM Benchmark</h3>", unsafe_allow_html=True)

    if st.button("Run Benchmark", key="benchmark_run", use_container_width=True):
        with st.spinner("Running benchmark..."):
            result = run_benchmark(model_router)

        if result["success"]:
            st.markdown(
                f'<div style="text-align:center;padding:0.5rem;">'
                f'<div style="font-size:2rem;font-weight:700;color:#667eea;">'
                f'{result["tokens_per_sec"]:.1f}</div>'
                f'<div style="font-size:0.7rem;color:#888;">tokens/sec</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                f"Model: {result['model_name']} | "
                f"Tokens: {result['num_tokens']} | "
                f"Latency: {result['latency_ms']:.0f}ms"
            )
        else:
            st.error(f"Benchmark failed: {result['model_name']}")

    st.caption("Sends a test prompt and measures generation speed.")
    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# Feature 17: Export & Import Memory DB
# ============================================================

def export_memory_db() -> Optional[bytes]:
    """Export the SQLite memory database as a downloadable file.

    Reads the SQLite .db file and returns its content as bytes.
    Returns None if the file cannot be read.

    Returns:
        Bytes of the SQLite database file, or None
    """
    memory = st.session_state.get("memory")
    if not memory:
        return None

    db_path = memory.db_path
    if not db_path or not Path(db_path).exists():
        return None

    try:
        # Close current connection to ensure file is written
        memory.close()

        # Read the file
        with open(db_path, "rb") as f:
            data = f.read()

        # Re-open connection (will be lazy-recreated on next use)
        return data
    except Exception as e:
        st.error(f"Failed to export database: {e}")
        return None


def import_memory_db(uploaded_file) -> bool:
    """Import a SQLite database file to replace the current memory.

    Args:
        uploaded_file: A Streamlit UploadedFile object

    Returns:
        True if import was successful
    """
    if uploaded_file is None:
        return False

    memory = st.session_state.get("memory")
    if not memory:
        st.error("Memory not initialized")
        return False

    db_path = memory.db_path
    if not db_path:
        st.error("Memory database path not set")
        return False

    try:
        # Close current connection
        memory.close()

        # Write uploaded file to database path
        with open(db_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Force re-initialization on next access
        st.session_state.pop("memory", None)
        st.session_state.pop("initialized", None)

        return True
    except Exception as e:
        st.error(f"Failed to import database: {e}")
        return False


def render_db_export_import_ui() -> None:
    """Render database export/import buttons in the sidebar."""
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown("<h3>Database</h3>", unsafe_allow_html=True)

    # Export
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        db_data = export_memory_db()
        if db_data:
            st.download_button(
                label="Export DB",
                data=db_data,
                file_name="atlas_memory_backup.db",
                mime="application/octet-stream",
                key="export_db_btn",
                use_container_width=True,
            )

    # Import
    with col_exp2:
        uploaded = st.file_uploader(
            "Import DB",
            type=["db"],
            key="import_db_uploader",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            if import_memory_db(uploaded):
                st.success("Database imported! Please refresh the app.")
                st.rerun()
            else:
                st.error("Import failed.")

    st.caption("Export/import your full chat history and settings.")
    st.markdown('</div>', unsafe_allow_html=True)
