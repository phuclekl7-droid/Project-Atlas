"""
Global Keyboard Shortcuts (Feature 174)

Provides JavaScript-enhanced keyboard shortcuts for Streamlit:
  - Ctrl+K / Cmd+K: Focus the session search input
  - Ctrl+N / Cmd+N: Create new session (duplicated from existing shortcut JS)
  - Escape: Close modals / cancel edit
  - ? Show help overlay

Uses st.markdown() injection. Designed to be called once from app.py main().

Usage:
    from ui.keyboard_shortcuts import get_global_shortcuts_js
    st.markdown(get_global_shortcuts_js(), unsafe_allow_html=True)
"""

import random


def get_global_shortcuts_js() -> str:
    """
    Return a <script> tag that registers global keyboard shortcuts.

    Shortcuts:
      Ctrl+K / Cmd+K → Focus session search input
      Ctrl+N / Cmd+N → Click "New Session" button

    Returns:
        HTML script tag string
    """
    uid = random.randint(10000, 99999)
    return f"""\
<script>
(function() {{
    'use strict';
    if (window.__globalShortcuts_{uid}) return;
    window.__globalShortcuts_{uid} = true;

    var lastAction = 0;

    document.addEventListener('keydown', function(e) {{
        var tag = (e.target || document.activeElement).tagName || '';
        var isInput = (tag === 'INPUT' || tag === 'TEXTAREA');

        // Debounce
        var now = Date.now();
        if (now - lastAction < 300) return;

        // ── Ctrl+K / Cmd+K : Focus session search ──
        if (e.key === 'k' && (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {{
            e.preventDefault();
            lastAction = now;
            // Look for the search input (Chat History Search — 'Tìm kiếm...')
            var searchInputs = document.querySelectorAll('input[type="text"]');
            for (var i = 0; i < searchInputs.length; i++) {{
                var inp = searchInputs[i];
                if (inp.placeholder && (inp.placeholder.indexOf('Tìm') !== -1 || inp.placeholder.indexOf('Tim') !== -1)) {{
                    inp.focus();
                    inp.select();
                    break;
                }}
            }}
        }}

        // ── Ctrl+N / Cmd+N : New Session ──
        if (e.key === 'n' && (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {{
            if (isInput) return; // Let input-specific Ctrl+N handlers work
            e.preventDefault();
            lastAction = now;
            var buttons = document.querySelectorAll('button');
            for (var i = 0; i < buttons.length; i++) {{
                var btn = buttons[i];
                if (btn.textContent.indexOf('New Session') !== -1) {{
                    btn.click();
                    break;
                }}
            }}
        }}

        // ── ? : Show help overlay (when not in input) ──
        if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey && !isInput) {{
            e.preventDefault();
            lastAction = now;
            var help = document.getElementById('shortcuts-help-{uid}');
            if (help) {{
                help.style.display = (help.style.display === 'none' || !help.style.display) ? 'block' : 'none';
            }}
        }}
    }});
}})();
</script>
<style>
#shortcuts-help-{uid} {{
    display: none;
    position: fixed;
    bottom: 1rem;
    right: 1rem;
    background: #1a1a2e;
    border: 1px solid rgba(102,126,234,0.3);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    z-index: 99999;
    font-size: 0.8rem;
    min-width: 220px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}}
#shortcuts-help-{uid} h4 {{
    margin: 0 0 0.5rem 0;
    color: #667eea;
    font-size: 0.85rem;
}}
#shortcuts-help-{uid} .shortcut-row {{
    display: flex;
    justify-content: space-between;
    padding: 0.2rem 0;
    color: #ccc;
}}
#shortcuts-help-{uid} kbd {{
    display: inline-block;
    padding: 0.05rem 0.4rem;
    border-radius: 4px;
    background: rgba(128,128,128,0.15);
    border: 1px solid rgba(128,128,128,0.2);
    font-family: monospace;
    font-size: 0.7rem;
    color: #aaa;
}}
</style>
<div id="shortcuts-help-{uid}">
<h4>⌨️ Phím tắt</h4>
<div class="shortcut-row"><span><kbd>Ctrl</kbd>+<kbd>K</kbd></span><span>Tìm kiếm session</span></div>
<div class="shortcut-row"><span><kbd>Ctrl</kbd>+<kbd>N</kbd></span><span>Session mới</span></div>
<div class="shortcut-row"><span><kbd>Esc</kbd></span><span>Hủy edit</span></div>
<div class="shortcut-row"><span><kbd>?</kbd></span><span>Phím tắt này</span></div>
</div>
"""


def _get_shortcut_help_html() -> str:
    """
    Return the HTML for the keyboard shortcut help panel.

    This is embedded in the JS-generated div but can also be
    rendered independently in the sidebar.
    """
    return (
        '<div style="font-size:0.65rem;color:#666;padding:0.2rem 0;">'
        '<div><kbd>Ctrl</kbd>+<kbd>K</kbd> Tìm kiếm</div>'
        '<div><kbd>Ctrl</kbd>+<kbd>N</kbd> Session mới</div>'
        '<div><kbd>?</kbd> Xem phím tắt</div>'
        '</div>'
    )
