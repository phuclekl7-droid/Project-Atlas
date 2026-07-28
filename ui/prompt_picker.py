"""
Prompt Picker UI (Feature: Quick Prompt Templates 1-Click)

A Streamlit expander/selectbox component placed above the chat input
that lets users 1-click to auto-fill a prompt template.

Usage (in render_chat_interface or before chat_input):
    from ui.prompt_picker import render_prompt_picker
    render_prompt_picker()

Dependencies:
    - src/features/prompt_library.py (PromptLibrary, PromptTemplate)
"""

import streamlit as st

from src.features.prompt_library import PromptLibrary

# Singleton library instance
_library: PromptLibrary = PromptLibrary()


def render_prompt_picker() -> None:
    """
    Render a compact prompt template picker above the chat input.

    Shows an expander with categorized selectbox. When user selects
    a template, its prompt text is injected into session state for
    the chat_input to pick up.
    """
    # Initialise trigger key if not present
    if "prompt_picker_trigger" not in st.session_state:
        st.session_state.prompt_picker_trigger = ""

    with st.expander("📋 Chọn mẫu câu lệnh nhanh", expanded=False):
        # Category filter
        categories = ["all"] + _library.categories
        cat_labels = {
            "all": "📋 Tất cả",
            "coding": "💻 Lập trình",
            "writing": "✍️ Viết lách",
            "learning": "📚 Học tập",
            "creative": "💡 Sáng tạo",
            "general": "🔧 Chung",
        }
        selected_cat = st.selectbox(
            "Danh mục",
            options=categories,
            format_func=lambda x: cat_labels.get(x, x.capitalize()),
            key="prompt_picker_category",
            label_visibility="collapsed",
        )

        # Get templates for selected category
        if selected_cat == "all":
            templates = _library.get_all()
        else:
            templates = _library.get_all(category=selected_cat)

        if not templates:
            st.caption("Không có mẫu nào trong danh mục này.")
            return

        # Build display options
        options = {t.id: f"{t.icon} {t.title}" for t in templates}
        selected_id = st.selectbox(
            "Chọn mẫu",
            options=list(options.keys()),
            format_func=lambda x: options.get(x, x),
            key="prompt_picker_select",
            label_visibility="collapsed",
        )

        # Show description
        tpl = _library.get_by_id(selected_id)
        if tpl and tpl.description:
            st.caption(tpl.description)

        # Fill button
        if st.button(
            f"📋 Điền mẫu \"{tpl.title if tpl else ''}\"",
            key="prompt_picker_fill",
            use_container_width=True,
            type="secondary",
        ):
            if tpl:
                st.session_state.prompt_picker_trigger = tpl.prompt
                st.rerun()
