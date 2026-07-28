"""
Code Theme Picker (Feature 170: Code Highlight Theme)

Allows users to switch between popular code syntax highlighting themes
(Monokai, GitHub Dark, OneDark, Solarized) via a sidebar selector.

Injects CSS overrides for `pre` and `code` blocks to match the selected theme.

Usage in sidebar:
    from ui.code_theme_picker import render_code_theme_picker
    render_code_theme_picker()
"""

import streamlit as st


# ── Theme Definitions ──

_THEMES = {
    "monokai": {
        "name": "Monokai",
        "icon": "🟣",
        "description": "Monokai — classic dark code theme",
        "css": """
        .message-bubble.assistant pre {
            background: #272822 !important;
            border: 1px solid #3e3d32 !important;
        }
        .message-bubble.assistant code {
            background: #3e3d32 !important;
            color: #f8f8f2 !important;
        }
        .message-bubble.assistant pre code {
            color: #f8f8f2 !important;
            background: transparent !important;
        }
        .stCodeBlock {
            background: #272822 !important;
        }
        """,
    },
    "github_dark": {
        "name": "GitHub Dark",
        "icon": "🌙",
        "description": "GitHub Dark — familiar GitHub code blocks",
        "css": """
        .message-bubble.assistant pre {
            background: #0d1117 !important;
            border: 1px solid #30363d !important;
        }
        .message-bubble.assistant code {
            background: #161b22 !important;
            color: #c9d1d9 !important;
        }
        .message-bubble.assistant pre code {
            color: #c9d1d9 !important;
            background: transparent !important;
        }
        .stCodeBlock {
            background: #0d1117 !important;
        }
        """,
    },
    "onedark": {
        "name": "OneDark",
        "icon": "🔵",
        "description": "One Dark Pro — Atom-inspired dark theme",
        "css": """
        .message-bubble.assistant pre {
            background: #1e2127 !important;
            border: 1px solid #3b4048 !important;
        }
        .message-bubble.assistant code {
            background: #3b4048 !important;
            color: #abb2bf !important;
        }
        .message-bubble.assistant pre code {
            color: #abb2bf !important;
            background: transparent !important;
        }
        .stCodeBlock {
            background: #1e2127 !important;
        }
        """,
    },
    "solarized": {
        "name": "Solarized",
        "icon": "🟠",
        "description": "Solarized Dark — warm, low-contrast theme",
        "css": """
        .message-bubble.assistant pre {
            background: #002b36 !important;
            border: 1px solid #073642 !important;
        }
        .message-bubble.assistant code {
            background: #073642 !important;
            color: #839496 !important;
        }
        .message-bubble.assistant pre code {
            color: #839496 !important;
            background: transparent !important;
        }
        .stCodeBlock {
            background: #002b36 !important;
        }
        """,
    },
    "default": {
        "name": "Default",
        "icon": "🔲",
        "description": "Mặc định (theo theme chính)",
        "css": "",
    },
}

_DEFAULT_THEME = "default"

_THEME_PREF_KEY = "code_theme"


def get_available_themes() -> list[str]:
    """Get list of available theme IDs."""
    return list(_THEMES.keys())


def get_theme_info(theme_id: str) -> dict:
    """Get theme metadata dict by ID."""
    return _THEMES.get(theme_id, _THEMES[_DEFAULT_THEME])


def get_theme_css(theme_id: str) -> str:
    """Get the CSS string for a theme (empty for default)."""
    info = _THEMES.get(theme_id)
    if info is None:
        return ""
    return info["css"]


def render_code_theme_picker() -> None:
    """
    Render the code theme selector in the sidebar.

    Stores the selected theme in:
        - st.session_state.code_theme (for current session)
        - memory.save_preference("code_theme", theme_id) for persistence

    Injects theme CSS via st.markdown when a non-default theme is selected.
    """
    # Ensure default
    if "code_theme" not in st.session_state:
        # Try to load from memory preferences
        memory = st.session_state.get("memory")
        if memory:
            saved = memory.get_preference(_THEME_PREF_KEY, _DEFAULT_THEME)
            st.session_state.code_theme = saved
        else:
            st.session_state.code_theme = _DEFAULT_THEME

    current_theme = st.session_state.code_theme

    # Build options
    theme_ids = get_available_themes()
    theme_options = {
        tid: f"{_THEMES[tid]['icon']} {_THEMES[tid]['name']}"
        for tid in theme_ids
    }

    selected = st.selectbox(
        "Code Theme",
        options=theme_ids,
        index=theme_ids.index(current_theme) if current_theme in theme_ids else 0,
        format_func=lambda x: theme_options.get(x, x),
        key="code_theme_selector",
        label_visibility="collapsed",
    )

    if selected != current_theme:
        st.session_state.code_theme = selected
        # Save preference
        memory = st.session_state.get("memory")
        if memory:
            memory.save_preference(_THEME_PREF_KEY, selected)
        st.rerun()

    # Inject theme CSS
    css = get_theme_css(selected)
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    # Show small description
    info = get_theme_info(selected)
    if info and selected != _DEFAULT_THEME:
        st.caption(info["description"])
