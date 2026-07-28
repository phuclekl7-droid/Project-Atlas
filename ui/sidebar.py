"""
Sidebar UI Module: session management, provider switching, preferences, health check.

Extracted from app.py to reduce its size.
"""

import streamlit as st

from src.core import (
    ConfigurationError,
    AssistantError,
)
from src.features import (
    render_export_buttons,
    search_sessions_ui,
    render_code_diff,
    render_db_export_import_ui,
    render_benchmark_ui,
)
from src.features.system_stats import get_system_stats, render_stats_html
from src.features.session_bookmark import SessionBookmark
from utils.prompt import detect_session_tags, render_session_tags


def render_sidebar():
    """Render the sidebar with session management, settings, and tools."""
    with st.sidebar:
        # ── User info ──
        user_name = st.session_state.get("preferences", {}).get("user_name", "")
        if user_name:
            st.markdown(f"### 👋 {user_name}")
        else:
            st.markdown("### 🧠 Personal AI")

        # ── Session management ──
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("<h3>💬 Sessions</h3>", unsafe_allow_html=True)

        col_new, col_del, col_clone = st.columns([2, 1, 1])
        with col_new:
            if st.button("✨ New Session", key="new_session_btn", use_container_width=True):
                from handlers.streaming import create_new_session
                create_new_session()
                st.rerun()
        with col_del:
            if st.button("🗑️ All", key="del_all_btn", use_container_width=True):
                from handlers.streaming import delete_all_sessions
                delete_all_sessions()
        with col_clone:
            current_sid = st.session_state.get("session_id", "")
            if st.button("📋 Clone", key="clone_session_btn", use_container_width=True):
                from handlers.session_cloner import clone_session
                new_id = clone_session(st.session_state.memory, current_sid)
                if new_id:
                    st.session_state.session_id = new_id
                    from handlers.streaming import refresh_messages
                    refresh_messages()
                    st.session_state.success = "📋 Đã clone session!"
                    st.rerun()
                else:
                    st.session_state.error = "❌ Không thể clone session!"
                    st.rerun()

        # Session list with bookmarks
        memory = st.session_state.memory
        sessions = memory.list_sessions(limit=20)
        current_sid = st.session_state.get("session_id", "")

        # Sort sessions: bookmarked first, then by updated_at
        bookmark = SessionBookmark(memory)
        sessions.sort(key=lambda s: bookmark.sort_key(s))

        # Get starred IDs for star icon display
        starred_ids = set(bookmark.get_starred([s.id for s in sessions]))

        for s in sessions:
            is_active = s.id == current_sid
            is_starred = s.id in starred_ids
            star_icon = "⭐" if is_starred else "☆"
            label = f"{star_icon} {s.name[:38]}" if is_starred else s.name[:40]
            label = label + ("..." if len(label) > 40 else "")

            cols = st.columns([5, 1])
            with cols[0]:
                btn_type = "primary" if is_active else "secondary"
                if st.button(
                    label,
                    key=f"session_{s.id}",
                    use_container_width=True,
                    type=btn_type,
                ):
                    from handlers.streaming import switch_session
                    switch_session(s.id)
                    st.rerun()
            with cols[1]:
                if st.button(
                    star_icon,
                    key=f"star_{s.id}",
                    help="⭐ Ghim / ☆ Bỏ ghim" if is_starred else "☆ Ghim session này",
                    use_container_width=True,
                ):
                    bookmark.toggle(s.id)
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Model Provider ──
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("<h3>🧠 Model</h3>", unsafe_allow_html=True)

        # Model parameter sliders (Feature 175)
        from ui.model_sliders import render_model_sliders
        render_model_sliders()

        providers = ["mock", "ollama", "openai", "gemini"]
        current_provider = st.session_state.get("provider", "mock")
        selected = st.selectbox(
            "Provider",
            options=providers,
            index=providers.index(current_provider) if current_provider in providers else 0,
            format_func=lambda x: x.upper(),
            key="provider_selector",
            label_visibility="collapsed",
        )
        if selected != current_provider:
            from handlers.streaming import switch_provider
            switch_provider(selected)
            st.rerun()

        # Response mode
        st.radio(
            "Mode",
            options=["stream", "async"],
            index=0 if st.session_state.get("response_mode", "stream") == "stream" else 1,
            format_func=lambda x: {"stream": "🎯 Stream", "async": "⚡ Async"}.get(x, x),
            key="response_mode_radio",
            horizontal=True,
            label_visibility="collapsed",
        )

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Persona / System Prompt ──
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("<h3>🎭 Persona</h3>", unsafe_allow_html=True)

        personas = {
            "default": "🤖 Default",
            "expert": "👨‍💻 Code Expert",
            "teacher": "👩‍🏫 Teacher",
            "writer": "✍️ Writer",
            "friend": "💬 Friend",
        }
        current_persona = st.session_state.get("persona", "default")
        persona_keys = list(personas.keys())
        persona_idx = persona_keys.index(current_persona) if current_persona in persona_keys else 0
        selected_persona = st.selectbox(
            "Persona",
            options=persona_keys,
            index=persona_idx,
            format_func=lambda x: personas.get(x, x),
            key="persona_selector",
            label_visibility="collapsed",
        )
        if selected_persona != current_persona:
            st.session_state.persona = selected_persona
            # Set persona prompt
            persona_prompts = {
                "default": "",
                "expert": "You are an expert software engineer. Provide detailed, technical answers with code examples.",
                "teacher": "You are a patient teacher. Explain concepts step by step with simple language.",
                "writer": "You are a professional writer. Respond with eloquent, well-structured prose.",
                "friend": "You are a friendly companion. Chat casually and warmly.",
            }
            st.session_state.persona_prompt = persona_prompts.get(selected_persona, "")
            st.rerun()

        if selected_persona == "default":
            custom_prompt = st.text_area(
                "Custom Prompt",
                value=st.session_state.get("custom_prompt", ""),
                placeholder="Hệ thống prompt tùy chỉnh...",
                key="custom_prompt_area",
                label_visibility="collapsed",
                max_chars=500,
                height=80,
            )
            if custom_prompt != st.session_state.get("custom_prompt", ""):
                st.session_state.custom_prompt = custom_prompt

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Model Parameters — moved to render_model_sliders() (Feature 175) ──

        # ── Dashboard & Tools ──
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("<h3>📊 Tools</h3>", unsafe_allow_html=True)

        if st.button("📊 Token Dashboard", key="dashboard_btn", use_container_width=True):
            st.session_state.show_dashboard = True
            st.rerun()

        if st.button("💾 Code Vault", key="vault_btn", use_container_width=True):
            st.session_state.show_vault = True
            st.rerun()

        render_benchmark_ui(st.session_state.model_router)
        render_db_export_import_ui()

        # Export chat
        current_sid = st.session_state.get("session_id", "")
        current_msgs = st.session_state.get("messages", [])
        render_export_buttons(current_sid, current_msgs)

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Preferences ──
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("<h3>👤 Preferences</h3>", unsafe_allow_html=True)

        current_name = st.session_state.get("preferences", {}).get("user_name", "")
        new_name = st.text_input(
            "Tên của bạn",
            value=current_name,
            placeholder="Nhập tên...",
            key="user_name_input",
            label_visibility="collapsed",
        )
        if new_name != current_name:
            st.session_state.memory.save_preference("user_name", new_name)
            st.session_state.preferences = st.session_state.memory.get_all_preferences()
            st.rerun()

        # Language
        current_lang = st.session_state.get("preferences", {}).get("language", "vi")
        lang = st.selectbox(
            "Ngôn ngữ",
            options=["vi", "en", "ja", "ko", "zh"],
            index=["vi", "en", "ja", "ko", "zh"].index(current_lang) if current_lang in ["vi", "en", "ja", "ko", "zh"] else 0,
            format_func=lambda x: {"vi": "Tiếng Việt", "en": "English", "ja": "日本語", "ko": "한국어", "zh": "中文"}.get(x, x),
            key="lang_selector",
            label_visibility="collapsed",
        )
        if lang != current_lang:
            st.session_state.memory.save_preference("language", lang)
            st.session_state.preferences = st.session_state.memory.get_all_preferences()

        # Theme
        current_theme = st.session_state.get("theme", "dark")
        theme_options = ["dark", "light"]
        theme_idx = theme_options.index(current_theme) if current_theme in theme_options else 0
        selected_theme = st.selectbox(
            "Theme",
            options=theme_options,
            index=theme_idx,
            format_func=lambda x: {"dark": "🌙 Tối", "light": "☀️ Sáng"}.get(x, x),
            key="theme_selector",
            label_visibility="collapsed",
        )
        if selected_theme != current_theme:
            st.session_state.memory.save_preference("theme", selected_theme)
            st.session_state.theme = selected_theme
            st.rerun()

        # Code syntax theme picker (Feature 170)
        from ui.code_theme_picker import render_code_theme_picker
        render_code_theme_picker()

        # Reset preferences
        if st.button("🔄 Quên Preferences", key="reset_prefs", use_container_width=True):
            st.session_state.memory.delete_preference("user_name")
            st.session_state.memory.delete_preference("language")
            st.session_state.preferences = st.session_state.memory.get_all_preferences()
            st.session_state.success = "🔄 Đã reset preferences!"
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Health Check ──
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("<h3>🔌 Health Check</h3>", unsafe_allow_html=True)
        if st.button("🔄 Check", key="health_btn", use_container_width=True):
            model_router = st.session_state.model_router
            results = model_router.check_all()
            for prov, status in results.items():
                emoji = "✅" if status.get("ok") else "❌"
                latency = status.get("latency_ms", 0)
                error = status.get("error")
                st.markdown(
                    f'<div class="health-row">'
                    f'<span class="health-info">{emoji} <b>{prov.upper()}</b></span>'
                    f'<span class="health-latency">{latency:.0f}ms</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if error:
                    st.markdown(
                        f'<div class="health-error">{error}</div>',
                        unsafe_allow_html=True,
                    )

        # Offline mode toggle (Feature 80)
        offline = st.toggle(
            "📡 Offline Mode",
            value=st.session_state.get("offline_mode", False),
            key="offline_toggle",
            help="Chỉ cho phép model local (Mock/Ollama)",
        )
        st.session_state.offline_mode = offline

        # Full-screen mode (Feature 49)
        fullscreen = st.toggle(
            "🖥️ Full-screen",
            value=st.session_state.get("fullscreen_mode", False),
            key="fullscreen_toggle",
        )
        st.session_state.fullscreen_mode = fullscreen

        # Audio completion notifier toggle (Feature: Completion Sound)
        from ui.audio_notifier import render_audio_toggle
        render_audio_toggle()

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Session info ──
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("<h3>ℹ️ Info</h3>", unsafe_allow_html=True)

        current_sid = st.session_state.get("session_id", "")
        msg_count = len(st.session_state.get("messages", []))
        st.caption(f"Session: {current_sid[:8]}...")
        st.caption(f"Messages: {msg_count}")
        st.caption(f"Provider: {st.session_state.get('provider', 'mock').upper()}")

        # Session tags
        if st.session_state.get("messages"):
            contents = [m.get("content", "") for m in st.session_state.messages if m.get("content")]
            tags = detect_session_tags(contents)
            st.markdown(render_session_tags(tags), unsafe_allow_html=True)

        # Keyboard shortcuts
        st.markdown(
            '<div style="font-size:0.7rem;color:#666;line-height:1.6;padding:0.3rem 0;">'
            '<div><kbd>Ctrl</kbd>+<kbd>Enter</kbd> Gửi</div>'
            '<div><kbd>Ctrl</kbd>+<kbd>N</kbd> Session mới</div>'
            '<div><kbd>Esc</kbd> Hủy edit</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        # System resource indicator (Feature: RAM/CPU Monitor)
        sys_stats = get_system_stats()
        sys_html = render_stats_html(sys_stats)
        if sys_html:
            st.markdown(sys_html, unsafe_allow_html=True)

        # Version
        st.caption("Project Atlas v0.7.0-alpha")
        st.markdown("</div>", unsafe_allow_html=True)
