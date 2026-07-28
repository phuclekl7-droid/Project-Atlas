"""
Personal AI Assistant - Streamlit Web UI

A modern, beautiful chat interface that replaces the CLI.
Built with Streamlit, integrates Core → Settings → Memory → Model Router.

Run with: streamlit run app.py

Architecture:
  - app.py: Thin entry point (init_backend, main, CSS)
  - ui/sidebar.py: Sidebar rendering
  - ui/chat.py: Chat interface, dashboard, vault
  - handlers/streaming.py: Response generation, CRUD, session management
  - utils/prompt.py: Prompt enhancement, streaming fix, session tagging, cost display
  - src/features.py: Standalone UI features (LaTeX, export, search, etc.)
"""

import streamlit as st

from src.core import ConfigurationError
from src.core.image_utils import ImageStore
from src.knowledge import create_knowledge_base
from src.memory import Memory
from src.model_router import ModelRouter
from src.plugin import PluginLoader
from src.settings import load_settings
from src.workflow import Workflow
from src.features import get_katex_html

from ui.styles import CUSTOM_CSS
from ui.sidebar import render_sidebar
from ui.chat import render_toasts, render_chat_interface, render_dashboard, render_vault_page


# ── Page config MUST be the first Streamlit command ──
st.set_page_config(
    page_title="Personal AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CUSTOM_CSS imported from ui/styles.py (~400 lines moved)
# ============================================================


# ============================================================
# Keyboard Shortcuts (Feature 161) — JavaScript injection
# ============================================================

KEYBOARD_SHORTCUTS_JS = """
<script>
(function() {
    'use strict';
    // Guard: prevent re-initialization on Streamlit reruns
    if (window.__shortcutsInitialized) return;
    window.__shortcutsInitialized = true;

    // Debounce utility to avoid double-fires on fast rerenders
    var lastActionTime = 0;
    function canAct() {
        var now = Date.now();
        if (now - lastActionTime < 500) return false;
        lastActionTime = now;
        return true;
    }

    document.addEventListener('keydown', function(e) {
        var tag = (e.target || document.activeElement).tagName || '';
        var isInput = (tag === 'INPUT' || tag === 'TEXTAREA');

        // ── Ctrl+Enter : Submit chat message ──
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            if (isInput) {
                e.preventDefault();
                var textarea = document.querySelector('textarea[data-testid="stChatInputTextArea"]');
                if (textarea) {
                    var form = textarea.closest('form');
                    if (form) {
                        var submitBtn = form.querySelector('button[kind="secondaryFormSubmit"]') || form.querySelector('button');
                        if (submitBtn) submitBtn.click();
                    }
                }
            }
        }

        // ── Ctrl+N : New Session ──
        if (e.key === 'n' && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
            e.preventDefault();
            if (!canAct()) return;
            var buttons = document.querySelectorAll('button');
            for (var i = 0; i < buttons.length; i++) {
                var btn = buttons[i];
                if (btn.textContent.indexOf('New Session') !== -1 ||
                    btn.textContent.indexOf('\u2728') !== -1) {
                    btn.click();
                    break;
                }
            }
        }

        // ── Escape : Cancel edit ──
        if (e.key === 'Escape' && !isInput) {
            if (!canAct()) return;
            var buttons = document.querySelectorAll('button');
            for (var i = 0; i < buttons.length; i++) {
                var btn = buttons[i];
                var txt = btn.textContent || '';
                if (txt.indexOf('H\u1ee7y') !== -1 || txt.indexOf('Cancel') !== -1) {
                    btn.click();
                    break;
                }
            }
        }
    });
})();
</script>
"""


# ============================================================
# Backend Initialization
# ============================================================


def init_backend():
    """Initialize settings, memory, and model router. Store in session state."""
    if "initialized" in st.session_state:
        return

    try:
        settings = load_settings()
        memory = Memory(db_path=settings.memory_path)
        model_router = ModelRouter(settings)

        sessions = memory.list_sessions(limit=1)
        if sessions:
            session_id = sessions[0].id
        else:
            session_id = memory.create_session(name="Main Chat")

        plugin_loader = PluginLoader(plugin_package="src.plugins")
        plugin_loader.discover()

        knowledge_base = create_knowledge_base(path="data/knowledge")

        workflow = Workflow(
            memory=memory,
            model_router=model_router,
            plugin_loader=plugin_loader,
            knowledge_base=knowledge_base,
            max_context_messages=settings.max_context_messages,
        )

        image_store = ImageStore(store_path="data/images")

        st.session_state.initialized = True
        st.session_state.settings = settings
        st.session_state.memory = memory
        st.session_state.model_router = model_router
        st.session_state.plugin_loader = plugin_loader
        st.session_state.knowledge_base = knowledge_base
        st.session_state.workflow = workflow
        st.session_state.image_store = image_store
        st.session_state.session_id = session_id
        st.session_state.provider = settings.model_provider
        st.session_state.error = None
        st.session_state.success = None
        st.session_state.undo_stack = []
        st.session_state.pending_image_previews = []
        st.session_state.preferences = memory.get_all_preferences()
        st.session_state.theme = memory.get_preference("theme", "dark")

    except ConfigurationError as e:
        st.session_state.initialized = False
        st.session_state.init_error = str(e.message)
    except Exception as e:
        st.session_state.initialized = False
        st.session_state.init_error = str(e)


# ============================================================
# Main Entry Point
# ============================================================


def main():
    """Main entry point for the Streamlit app."""
    # Check if vault page should be shown (Feature 158)
    if st.session_state.get("show_vault"):
        render_vault_page()
        return

    # Initialize backend on first run
    init_backend()

    # Check initialization
    if not st.session_state.get("initialized", False):
        err = st.session_state.get("init_error", "Unknown error during initialization")
        st.error(f"⚠️ {err}")
        st.info("💡 Please check your configuration in the .env file.")
        return

    # Inject custom CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Full-screen mode CSS injection (Feature 49)
    if st.session_state.get("fullscreen_mode", False):
        st.markdown(
            """<style>
                section[data-testid="stSidebar"] { display: none !important; }
                .main .block-container { max-width: 100% !important; padding: 1rem 3rem !important; }
            </style>""",
            unsafe_allow_html=True,
        )

    # KaTeX Math Rendering (Feature 47)
    st.markdown(get_katex_html(), unsafe_allow_html=True)

    # Keyboard shortcuts injection (Feature 161)
    st.markdown(KEYBOARD_SHORTCUTS_JS, unsafe_allow_html=True)

    # Global keyboard shortcuts (Feature 174)
    from ui.keyboard_shortcuts import get_global_shortcuts_js
    st.markdown(get_global_shortcuts_js(), unsafe_allow_html=True)

    # Audio completion notifier injection (Feature: Completion Sound)
    from ui.audio_notifier import get_ding_html
    st.markdown(get_ding_html(volume=0.5, default_enabled=False), unsafe_allow_html=True)

    # Drag-and-drop image overlay (Feature 172, visual-only)
    from ui.image_dropper import get_drag_drop_html
    st.markdown(get_drag_drop_html(), unsafe_allow_html=True)

    # Code expander CSS (Feature 171)
    from ui.code_expander import CODE_EXPANDER_CSS
    st.markdown(CODE_EXPANDER_CSS, unsafe_allow_html=True)

    # Render sidebar
    render_sidebar()

    # Main chat area
    render_toasts()

    # Dashboard toggle (Feature 3)
    if st.session_state.get("show_dashboard", False):
        render_dashboard()
        if st.button("⬅️ Quay lại Chat", use_container_width=True):
            st.session_state.show_dashboard = False
            st.rerun()
        return

    render_chat_interface()


if __name__ == "__main__":
    main()

