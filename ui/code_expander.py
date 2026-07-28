"""
Code Block Expander (Feature 171: Thu gọn/Mở rộng Code Dài)

Auto-collapses code blocks longer than 20 lines and adds a
"▼ Hiển thị thêm code" toggle button.

Uses JavaScript injection + CSS to hide/show the truncated code.

Usage in render_chat_interface:
    from ui.code_expander import wrap_code_block
    html = wrap_code_block(code_text, language)
"""

import html
import re

_MAX_VISIBLE_LINES = 20


def _count_code_lines(code: str) -> int:
    """Count the number of meaningful lines in a code block."""
    if not code:
        return 0
    lines = code.split("\n")
    # Filter out purely empty lines at the end
    while lines and lines[-1].strip() == "":
        lines.pop()
    return len(lines)


def wrap_code_block(code: str, language: str = "") -> str:
    """
    Wrap a code block with optional expander for long blocks.

    If the code has <= MAX_VISIBLE_LINES lines, returns standard
    ```...``` markdown. If longer, returns HTML with a expand/collapse
    toggle injected via JavaScript.

    Args:
        code: The source code text
        language: Optional language label (e.g., "python", "javascript")

    Returns:
        Markdown code block string (short) or HTML string (long)
    """
    line_count = _count_code_lines(code)

    if line_count <= _MAX_VISIBLE_LINES:
        # Short block — render as-is
        lang_tag = language or ""
        return f"```{lang_tag}\n{code}\n```"

    # Long block — truncate and add expander
    lines = code.split("\n")
    visible = lines[:_MAX_VISIBLE_LINES]
    hidden = lines[_MAX_VISIBLE_LINES:]
    hidden_count = line_count - _MAX_VISIBLE_LINES

    # Use a unique ID for the expander
    import random
    expander_id = f"code_expand_{random.randint(10000, 99999)}"

    escaped_visible = html.escape("\n".join(visible))
    escaped_hidden = html.escape("\n".join(hidden))

    lang_tag = language or ""

    html_output = f"""\
<div class=\"code-expander-wrapper\" id=\"{expander_id}\">
<pre style=\"position:relative;\"><code class=\"language-{lang_tag}\">{escaped_visible}</code></pre>
<div class=\"code-expander-hidden\" id=\"{expander_id}_hidden\" style=\"display:none;\">
<pre><code class=\"language-{lang_tag}\">{escaped_hidden}</code></pre>
</div>
<div class=\"code-expander-toggle\" style=\"text-align:center;padding:0.3rem;\">
<button onclick=\"(function() {{
    var hidden = document.getElementById('{expander_id}_hidden');
    var btn = document.getElementById('{expander_id}_btn');
    if (hidden.style.display === 'none') {{
        hidden.style.display = 'block';
        btn.innerHTML = '▲ Thu gọn';
    }} else {{
        hidden.style.display = 'none';
        btn.innerHTML = '▼ Hiển thị thêm {hidden_count} dòng';
    }}
}})(); return false;\" 
id=\"{expander_id}_btn\"
style=\"background:rgba(102,126,234,0.1);border:1px solid rgba(102,126,234,0.2);
       color:#667eea;padding:0.3rem 1rem;border-radius:6px;cursor:pointer;
       font-size:0.8rem;transition:all 0.15s;\"
onmouseover=\"this.style.background='rgba(102,126,234,0.2)'\"
onmouseout=\"this.style.background='rgba(102,126,234,0.1)'\"
>▼ Hiển thị thêm {hidden_count} dòng</button>
</div>
</div>"""

    return html_output


# ── CSS to inject into the page (via ui/styles.py or st.markdown) ──

CODE_EXPANDER_CSS = """
<style>
.code-expander-wrapper {
    margin: 0.5rem 0;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid rgba(128, 128, 128, 0.15);
}
.code-expander-wrapper pre {
    margin: 0 !important;
    border-radius: 0 !important;
    max-height: none !important;
}
.code-expander-wrapper .code-expander-hidden pre {
    border-top: 1px dashed rgba(128, 128, 128, 0.2);
}
.code-expander-toggle {
    background: rgba(0, 0, 0, 0.15);
    border-top: 1px solid rgba(128, 128, 128, 0.1);
}
</style>
"""
