"""
Personal AI Assistant - Streamlit Web UI

A modern, beautiful chat interface that replaces the CLI.
Built with Streamlit, integrates Core → Settings → Memory → Model Router.

Run with: streamlit run app.py
"""

import asyncio
import time
from pathlib import Path

import streamlit as st

from src.core import (
    AssistantError,
    ConfigurationError,
    ModelConnectionError,
    format_timestamp,
)
from src.knowledge import create_knowledge_base
from src.memory import Memory
from src.model_router import ModelRouter, ModelResponse
from src.plugin import PluginLoader
from src.settings import load_settings
from src.workflow import Workflow

# ── Page config MUST be the first Streamlit command ──
st.set_page_config(
    page_title="Personal AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# Custom CSS
# ============================================================

CUSTOM_CSS = """
<style>
    /* ── Global ── */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
        max-width: 900px;
    }

    /* ── Chat header ── */
    .chat-header {
        text-align: center;
        padding: 1rem 0 0.5rem 0;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        margin-bottom: 1rem;
    }
    .chat-header h1 {
        font-size: 1.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .chat-header p {
        font-size: 0.85rem;
        color: #888;
        margin-top: 0;
    }

    /* ── Chat messages container (scrollable) ── */
    .chat-messages {
        max-height: 60vh;
        overflow-y: auto;
        padding: 0.5rem 1rem;
        margin-bottom: 0.5rem;
        border-radius: 12px;
        background: rgba(128, 128, 128, 0.02);
        scroll-behavior: smooth;
    }

    /* ── Message bubbles ── */
    .message-row {
        display: flex;
        margin-bottom: 1rem;
        animation: fadeIn 0.3s ease-in;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .message-row.user {
        justify-content: flex-end;
    }
    .message-row.assistant {
        justify-content: flex-start;
    }

    .message-bubble {
        max-width: 80%;
        padding: 0.75rem 1rem;
        border-radius: 18px;
        position: relative;
        line-height: 1.5;
        font-size: 0.95rem;
        word-wrap: break-word;
    }
    .message-bubble.user {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-bottom-right-radius: 4px;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
    }
    .message-bubble.assistant {
        background: #2d2d3f;
        color: #e0e0e0;
        border-bottom-left-radius: 4px;
        border: 1px solid rgba(128, 128, 128, 0.15);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    }

    .message-avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1rem;
        margin: 0 0.5rem;
        flex-shrink: 0;
    }
    .message-avatar.user {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        order: 2;
    }
    .message-avatar.assistant {
        background: #2d2d3f;
        border: 1px solid rgba(128, 128, 128, 0.2);
        color: #667eea;
        order: -1;
    }

    /* ── Provider badge ── */
    .provider-badge {
        display: inline-block;
        padding: 0.15rem 0.5rem;
        border-radius: 10px;
        font-size: 0.7rem;
        font-weight: 600;
        margin-left: 0.5rem;
    }
    .provider-badge.mock {
        background: #ff6b6b22;
        color: #ff6b6b;
        border: 1px solid #ff6b6b44;
    }
    .provider-badge.ollama {
        background: #4ecdc422;
        color: #4ecdc4;
        border: 1px solid #4ecdc444;
    }
    .provider-badge.openai {
        background: #45b7d122;
        color: #45b7d1;
        border: 1px solid #45b7d144;
    }

    /* ── Input area ── */
    .input-container {
        border-top: 1px solid rgba(128, 128, 128, 0.15);
        padding-top: 0.75rem;
        margin-top: 0.5rem;
    }

    /* ── Sidebar sections ── */
    .sidebar-section {
        margin-bottom: 1.5rem;
    }
    .sidebar-section h3 {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #888;
        margin-bottom: 0.75rem;
        border-bottom: 1px solid rgba(128, 128, 128, 0.1);
        padding-bottom: 0.4rem;
    }

    /* ── Session button styling ── */
    div[data-testid="stButton"] button.session-btn {
        text-align: left;
        font-size: 0.85rem;
        padding: 0.4rem 0.7rem;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 8px;
        transition: all 0.2s;
        justify-content: flex-start;
    }
    div[data-testid="stButton"] button.session-btn:hover {
        background: rgba(102, 126, 234, 0.1);
        border-color: rgba(102, 126, 234, 0.2);
    }
    div[data-testid="stButton"] button.session-btn.active {
        background: rgba(102, 126, 234, 0.15);
        border-color: rgba(102, 126, 234, 0.3);
        color: #667eea;
        font-weight: 600;
    }

    /* ── Stat card ── */
    .stat-card {
        background: rgba(128, 128, 128, 0.05);
        border-radius: 10px;
        padding: 0.75rem;
        text-align: center;
        border: 1px solid rgba(128, 128, 128, 0.1);
    }
    .stat-card .stat-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #667eea;
    }
    .stat-card .stat-label {
        font-size: 0.7rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* ── Toast notifications ── */
    .toast-container {
        margin-bottom: 0.75rem;
    }
    .toast-error {
        background: rgba(255, 107, 107, 0.1);
        border: 1px solid rgba(255, 107, 107, 0.3);
        border-radius: 10px;
        padding: 0.75rem 1rem;
        color: #ff6b6b;
        font-size: 0.9rem;
        margin-bottom: 0.5rem;
    }
    .toast-success {
        background: rgba(78, 205, 196, 0.1);
        border: 1px solid rgba(78, 205, 196, 0.3);
        border-radius: 10px;
        padding: 0.75rem 1rem;
        color: #4ecdc4;
        font-size: 0.9rem;
        margin-bottom: 0.5rem;
    }

    /* ── Model response markdown ── */
    .message-bubble.assistant p { margin-bottom: 0.4rem; }
    .message-bubble.assistant code {
        background: rgba(128, 128, 128, 0.15);
        padding: 0.15rem 0.35rem;
        border-radius: 4px;
        font-size: 0.85em;
    }
    .message-bubble.assistant pre {
        background: rgba(0, 0, 0, 0.3);
        padding: 0.75rem;
        border-radius: 8px;
        overflow-x: auto;
    }

    /* ── Welcome message ── */
    .welcome-msg {
        text-align: center;
        padding: 3rem 1rem;
        color: #666;
    }
    .welcome-msg .emoji { font-size: 4rem; margin-bottom: 1rem; }
    .welcome-msg .title {
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        color: #e0e0e0;
    }
    .welcome-msg .subtitle { font-size: 0.9rem; }

    /* ── Auto-scroll anchor ── */
    #scroll-anchor {
        height: 1px;
    }
</style>"""


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

        # Get or create active session
        sessions = memory.list_sessions(limit=1)
        if sessions:
            session_id = sessions[0].id
        else:
            session_id = memory.create_session(name="Main Chat")

        # Initialize Plugin Loader
        plugin_loader = PluginLoader(plugin_package="src.plugins")
        plugin_loader.discover()

        # Initialize Knowledge Base
        knowledge_base = create_knowledge_base(path="data/knowledge")

        # Initialize Workflow (central orchestrator)
        workflow = Workflow(
            memory=memory,
            model_router=model_router,
            plugin_loader=plugin_loader,
            knowledge_base=knowledge_base,
            max_context_messages=settings.max_context_messages,
        )

        st.session_state.initialized = True
        st.session_state.settings = settings
        st.session_state.memory = memory
        st.session_state.model_router = model_router
        st.session_state.plugin_loader = plugin_loader
        st.session_state.knowledge_base = knowledge_base
        st.session_state.workflow = workflow
        st.session_state.session_id = session_id
        st.session_state.provider = settings.model_provider
        st.session_state.error = None
        st.session_state.success = None

    except ConfigurationError as e:
        st.session_state.initialized = False
        st.session_state.init_error = str(e.message)
    except Exception as e:
        st.session_state.initialized = False
        st.session_state.init_error = str(e)


def refresh_messages():
    """Load messages from memory into session state for the current session."""
    if "memory" not in st.session_state or "session_id" not in st.session_state:
        st.session_state.messages = []
        return

    memory = st.session_state.memory
    session_id = st.session_state.session_id
    raw_messages = memory.get_messages(session_id, limit=200)
    st.session_state.messages = [
        {"role": m.role, "content": m.content}
        for m in raw_messages
    ]


def switch_provider(provider: str):
    """Switch the model provider and re-initialize the router."""
    settings = st.session_state.settings
    old_provider = settings.model_provider
    settings.model_provider = provider

    try:
        st.session_state.model_router.__init__(settings)
        st.session_state.provider = provider
        st.session_state.success = f"Switched to {provider.upper()}"
    except (ConfigurationError, AssistantError) as e:
        settings.model_provider = old_provider
        st.session_state.error = f"Failed to switch: {e.message}"


def generate_response(prompt: str):
    """
    Core generation logic (sync) — uses Workflow.process().
    Called inside st.spinner() for visual feedback.
    """
    workflow = st.session_state.workflow
    session_id = st.session_state.session_id
    settings = st.session_state.settings

    try:
        # Execute full workflow
        result = workflow.process(
            user_input=prompt,
            session_id=session_id,
            max_context=settings.max_context_messages,
        )

        # Refresh messages to show new conversation
        refresh_messages()

        # Store display info
        if result.source == "plugin":
            st.session_state.latency = result.latency_ms
            if result.plugin_result and result.plugin_result.success:
                st.session_state.success = f"🧩 Plugin: {result.plugin_result.output}"
        else:
            st.session_state.latency = result.latency_ms

    except ConfigurationError as e:
        st.session_state.error = f"Cấu hình lỗi: {e.message}"
    except ModelConnectionError as e:
        st.session_state.error = f"Kết nối lỗi: {e.message}"
    except AssistantError as e:
        st.session_state.error = f"Lỗi: {e.message}"
    except Exception as e:
        st.session_state.error = f"Lỗi bất ngờ: {e}"


def generate_response_async(prompt: str):
    """
    Core generation logic (async / non-blocking) — uses Workflow.process_async().
    Called inside st.spinner() for visual feedback.

    Uses asyncio.run() to bridge the sync Streamlit world with the async Workflow.
    The API call (aiohttp) runs in the background without blocking the UI thread.
    """
    workflow = st.session_state.workflow
    session_id = st.session_state.session_id
    settings = st.session_state.settings

    try:
        # Execute full workflow asynchronously
        result = asyncio.run(
            workflow.process_async(
                user_input=prompt,
                session_id=session_id,
                max_context=settings.max_context_messages,
            )
        )

        # Refresh messages to show new conversation
        refresh_messages()

        # Store display info
        if result.source == "plugin":
            st.session_state.latency = result.latency_ms
            if result.plugin_result and result.plugin_result.success:
                st.session_state.success = f"🧩 Plugin: {result.plugin_result.output}"
        else:
            st.session_state.latency = result.latency_ms

    except ConfigurationError as e:
        st.session_state.error = f"Cấu hình lỗi: {e.message}"
    except ModelConnectionError as e:
        st.session_state.error = f"Kết nối lỗi: {e.message}"
    except AssistantError as e:
        st.session_state.error = f"Lỗi: {e.message}"
    except Exception as e:
        st.session_state.error = f"Lỗi bất ngờ: {e}"


def handle_user_input(prompt: str):
    """Handle user input: refresh messages, set pending prompt for next render."""
    if not prompt.strip():
        return

    # Refresh current messages
    refresh_messages()

    # Set pending prompt — Workflow processing happens in the NEXT render
    # so the spinner can be shown to the user first
    st.session_state.pending_prompt = prompt


def create_new_session():
    """Create a new chat session and switch to it."""
    name = st.session_state.get("new_session_name", "").strip()
    memory = st.session_state.memory
    new_id = memory.create_session(name=name if name else None)
    st.session_state.session_id = new_id
    st.session_state.new_session_name = ""
    refresh_messages()
    st.session_state.success = "Đã tạo session mới!"


def switch_session(session_id: str):
    """Switch to an existing session."""
    st.session_state.session_id = session_id
    refresh_messages()


def delete_all_sessions():
    """Delete all sessions and create a fresh one."""
    memory = st.session_state.memory
    count = memory.delete_all_sessions()
    new_id = memory.create_session(name="Main Chat")
    st.session_state.session_id = new_id
    refresh_messages()
    st.session_state.success = f"Đã xóa {count} session. Bắt đầu session mới!"
    st.rerun()


# ============================================================
# UI Components
# ============================================================


def render_toasts():
    """Display success/error toast messages at the top of the chat area."""
    col1, col2, col3 = st.columns([1, 6, 1])
    with col2:
        if st.session_state.get("error"):
            st.markdown(
                f'<div class="toast-error">❌ {st.session_state.error}</div>',
                unsafe_allow_html=True,
            )
            st.session_state.error = None

        if st.session_state.get("success"):
            st.markdown(
                f'<div class="toast-success">✅ {st.session_state.success}</div>',
                unsafe_allow_html=True,
            )
            st.session_state.success = None


def render_sidebar():
    """Render the sidebar with settings, sessions, and stats."""
    with st.sidebar:
        # ── App logo ──
        st.markdown(
            """
            <div style="text-align: center; padding: 0.5rem 0 1rem 0;">
                <div style="font-size: 3rem; margin-bottom: 0.3rem;">🤖</div>
                <div style="font-weight: 700; font-size: 1.2rem;
                     background: linear-gradient(135deg, #667eea, #764ba2);
                     -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                    AI Assistant
                </div>
                <div style="font-size: 0.7rem; color: #666;">v0.5.0 · Streamlit UI</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        # ── Provider ──
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("<h3>🤖 Model Provider</h3>", unsafe_allow_html=True)

        current = st.session_state.settings.model_provider
        providers = {
            "mock": "🔌 Mock (Test)",
            "ollama": "🦙 Ollama (Local)",
            "openai": "🔵 OpenAI (API)",
        }

        selected = st.radio(
            "Provider",
            options=list(providers.keys()),
            format_func=lambda x: providers.get(x, x),
            index=list(providers.keys()).index(current) if current in providers else 0,
            label_visibility="collapsed",
            key="provider_selector",
            on_change=lambda: switch_provider(st.session_state.provider_selector),
        )
        st.markdown("</div>", unsafe_allow_html=True)

        # ── Model Info ──
        settings = st.session_state.settings
        router = st.session_state.model_router
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("<h3>📋 Model Info</h3>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="font-size: 0.85rem; background: rgba(128,128,128,0.05);
                 border-radius: 8px; padding: 0.6rem;">
                <div style="margin-bottom: 0.3rem;">
                    <span style="color: #888;">Provider:</span>
                    <span class="provider-badge {settings.model_provider}">
                        {settings.model_provider}
                    </span>
                </div>
                <div><span style="color: #888;">Model:</span> {router.model.model_name}</div>
                <div><span style="color: #888;">Context:</span> {settings.max_context_messages} msgs</div>
                {f'<div><span style="color: #888;">Latency:</span> {st.session_state.get("latency", 0):.0f}ms</div>'
                   if st.session_state.get("latency") else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # ── Sessions ──
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("<h3>💬 Sessions</h3>", unsafe_allow_html=True)

        # New session
        st.text_input(
            "Tên session mới",
            placeholder="Nhập tên + Enter...",
            key="new_session_name",
            on_change=create_new_session,
            label_visibility="collapsed",
        )

        # Session list as buttons
        memory = st.session_state.memory
        sessions = memory.list_sessions(limit=15)
        current_id = st.session_state.session_id

        for s in sessions:
            is_active = s.id == current_id
            label = f"{'◀ ' if is_active else ''}{s.name} ({s.message_count})"
            btn_key = f"switch_{s.id}"

            if st.button(
                label,
                key=btn_key,
                use_container_width=True,
                type="secondary" if not is_active else "primary",
                disabled=is_active,
            ):
                switch_session(s.id)
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Danger zone ──
        if st.button("🗑️ Xóa tất cả sessions", use_container_width=True):
            delete_all_sessions()

        st.divider()

        # ── Knowledge Base ──
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("<h3>📚 Knowledge Base</h3>", unsafe_allow_html=True)

        kb = st.session_state.knowledge_base

        if not kb.available:
            st.markdown(
                '<div style="font-size: 0.85rem; color: #ff6b6b;">⚠️ ChromaDB chưa được cài đặt.</div>'
                '<div style="font-size: 0.8rem; color: #888; margin-top: 0.3rem;">'
                'pip install chromadb để dùng vector search, hoặc dùng keyword search mặc định.'
                '</div>',
                unsafe_allow_html=True,
            )

        # Upload file section
        st.markdown("<p style='font-size: 0.8rem; color: #888; margin-bottom: 0.3rem;'>📤 Upload file (.txt)</p>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "Chọn file .txt",
            type=["txt"],
            label_visibility="collapsed",
            key="kb_file_uploader",
        )

        if uploaded_file is not None:
            # Prevent re-processing the same file on every rerun
            last_file = st.session_state.get("kb_last_file", "")
            if uploaded_file.name != last_file:
                try:
                    text_content = uploaded_file.read().decode("utf-8")
                    if text_content.strip():
                        doc_id = kb.add_text(uploaded_file.name, text_content)
                        if doc_id:
                            st.session_state.success = f"📚 Đã thêm '{uploaded_file.name}' vào Knowledge Base!"
                            st.session_state.kb_last_file = uploaded_file.name
                        else:
                            st.session_state.error = f"Không thể thêm '{uploaded_file.name}'"
                    else:
                        st.session_state.error = "File rỗng!"
                except Exception as e:
                    st.session_state.error = f"Lỗi đọc file: {e}"
                st.rerun()

        # Document list
        docs = kb.list_documents()
        if docs:
            st.markdown(
                f"<p style='font-size: 0.8rem; color: #888; margin: 0.5rem 0 0.3rem 0;'>📄 Tài liệu ({len(docs)}):</p>",
                unsafe_allow_html=True,
            )
            for doc in docs:
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.markdown(
                        f'<div style="font-size: 0.8rem; padding: 0.2rem 0;">'
                        f'📄 {doc.filename}<br>'
                        f'<span style="color: #666;">{doc.chunk_count} chunks · {doc.char_count} chars</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with col_b:
                    if st.button("🗑️", key=f"del_doc_{doc.id}", help=f"Xóa {doc.filename}"):
                        kb.delete_document(doc.id)
                        st.session_state.success = f"Đã xóa '{doc.filename}'"
                        st.rerun()
        else:
            st.markdown(
                '<div style="font-size: 0.85rem; color: #666;">Chưa có tài liệu nào. Upload file .txt ở trên.</div>',
                unsafe_allow_html=True,
            )

        # Knowledge search
        st.markdown(
            "<p style='font-size: 0.8rem; color: #888; margin: 0.5rem 0 0.3rem 0;'>🔍 Search</p>",
            unsafe_allow_html=True,
        )
        kb_query = st.text_input(
            "Tìm kiếm",
            placeholder="Nhập từ khóa...",
            label_visibility="collapsed",
            key="kb_search_input",
        )
        if kb_query:
            results = kb.search(kb_query, n_results=3)
            if results:
                for r in results:
                    preview = r.content[:120].replace("\n", " ")
                    st.markdown(
                        f'<div style="font-size: 0.8rem; padding: 0.3rem; '
                        f'background: rgba(128,128,128,0.05); border-radius: 6px; '
                        f'margin-bottom: 0.3rem;">'
                        f'<span style="color: #888;">📄 {r.filename}</span> '
                        f'<span style="color: #4ecdc4; font-size: 0.7rem;">(score: {r.score:.2f})</span><br>'
                        f'{preview}...'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    '<div style="font-size: 0.8rem; color: #666;">Không tìm thấy kết quả.</div>',
                    unsafe_allow_html=True,
                )

        # KB stats
        kb_stats = kb.get_stats()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                f'<div class="stat-card" style="padding: 0.5rem;">'
                f'<div class="stat-value" style="font-size: 1.2rem;">{kb_stats["documents"]}</div>'
                f'<div class="stat-label">Documents</div></div>',
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                f'<div class="stat-card" style="padding: 0.5rem;">'
                f'<div class="stat-value" style="font-size: 1.2rem;">{kb_stats["chunks"]}</div>'
                f'<div class="stat-label">Chunks</div></div>',
                unsafe_allow_html=True,
            )

        # Delete all button
        if docs and st.button("🗑️ Xóa tất cả tài liệu", use_container_width=True):
            count = kb.delete_all()
            st.session_state.success = f"Đã xóa {count} chunks!"
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # ── Plugins ──
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("<h3>🧩 Plugins</h3>", unsafe_allow_html=True)

        plugin_loader = st.session_state.plugin_loader
        plugins = plugin_loader.list_plugins()

        if not plugins:
            st.markdown(
                '<div style="font-size: 0.85rem; color: #666;">Không có plugin nào.</div>',
                unsafe_allow_html=True,
            )
        else:
            for p in plugins:
                st.markdown(
                    f'<div style="font-size: 0.85rem; padding: 0.3rem 0;">'
                    f'<strong>{p["name"]}</strong>: {p["description"]}</div>',
                    unsafe_allow_html=True,
                )

            # Plugin executor
            plugin_names = [p["name"] for p in plugins]
            selected_plugin = st.selectbox(
                "Chọn plugin",
                options=plugin_names,
                label_visibility="collapsed",
                key="plugin_selector",
            )

            plugin_input = st.text_input(
                "Input",
                placeholder='VD: 2 + 3',
                key="plugin_input",
                label_visibility="collapsed",
            )

            if st.button("🚀 Run Plugin", use_container_width=True, type="primary"):
                if plugin_input.strip():
                    try:
                        result = plugin_loader.execute(selected_plugin, plugin_input)
                        if result.success:
                            st.session_state.success = f"🧩 {selected_plugin}: {result.output}"
                        else:
                            st.session_state.error = f"🧩 {selected_plugin} lỗi: {result.error}"
                    except Exception as e:
                        st.session_state.error = f"🧩 Plugin error: {e}"
                else:
                    st.session_state.error = "Vui lòng nhập input cho plugin!"
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        st.divider()

        # ── Memory Stats ──
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown("<h3>📊 Memory Stats</h3>", unsafe_allow_html=True)

        stats = memory.get_total_stats()
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                f'<div class="stat-card"><div class="stat-value">{stats["sessions"]}</div>'
                f'<div class="stat-label">Sessions</div></div>',
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                f'<div class="stat-card"><div class="stat-value">{stats["messages"]}</div>'
                f'<div class="stat-label">Messages</div></div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)


def render_chat():
    """Render the main chat area with header, messages, and input."""
    # ── Toasts at top ──
    render_toasts()

    # ── Header ──
    provider_emoji = {
        "mock": "🔌",
        "ollama": "🦙",
        "openai": "🔵",
    }.get(st.session_state.provider, "🤖")

    session = st.session_state.memory.get_session(st.session_state.session_id)
    session_name = session.name if session else "Chat"

    st.markdown(
        f"""
        <div class="chat-header">
            <h1>🤖 Personal AI Assistant</h1>
            <p>
                {provider_emoji} {st.session_state.provider.upper()} ·
                {st.session_state.model_router.model.model_name} ·
                📝 {session_name}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Chat messages (scrollable) ──
    st.markdown('<div class="chat-messages">', unsafe_allow_html=True)

    messages = st.session_state.get("messages", [])

    if not messages:
        st.markdown(
            """
            <div class="welcome-msg">
                <div class="emoji">👋</div>
                <div class="title">Chào mừng bạn đến với Personal AI Assistant!</div>
                <div class="subtitle">
                    Hãy gửi tin nhắn để bắt đầu trò chuyện.<br>
                    Hiện tại: <strong>Mock mode</strong> —
                    cấu hình .env để dùng Ollama hoặc OpenAI.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            avatar = "👤" if role == "user" else "🤖"

            st.markdown(
                f"""
                <div class="message-row {role}">
                    <div class="message-avatar {role}">{avatar}</div>
                    <div class="message-bubble {role}">
                        {content}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Auto-scroll anchor
    st.markdown('<div id="scroll-anchor"></div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)  # close chat-messages

    # ── Handle pending prompt (generation on the second render) ──
    if st.session_state.get("pending_prompt"):
        prompt = st.session_state.pop("pending_prompt")
        with st.spinner("🤔 Đang suy nghĩ... [async]"):
            generate_response_async(prompt)
        st.rerun()

    # ── Input area ──
    st.markdown('<div class="input-container">', unsafe_allow_html=True)

    disabled = st.session_state.get("pending_prompt") is not None
    prompt = st.chat_input(
        "Nhập tin nhắn của bạn..." if not disabled else "Đang xử lý...",
        key="chat_input",
        disabled=disabled,
    )

    if prompt:
        handle_user_input(prompt)
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# Main App
# ============================================================


def main():
    """Main entry point for the Streamlit app."""
    # Apply custom CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Auto-scroll script (separate injection for reliability)
    st.markdown(
        """
        <script>
        function scrollToBottom() {
            const el = document.querySelector('.chat-messages');
            if (el) el.scrollTop = el.scrollHeight;
        }
        window.addEventListener('load', scrollToBottom);
        const observer = new MutationObserver(scrollToBottom);
        const target = document.querySelector('.chat-messages');
        if (target) observer.observe(target, { childList: true, subtree: true });
        </script>
        """,
        unsafe_allow_html=True,
    )

    # Initialize backend (once)
    init_backend()

    # Check initialization
    if not st.session_state.get("initialized", False):
        error_msg = st.session_state.get("init_error", "Unknown initialization error")
        st.markdown(
            f"""
            <div style="text-align: center; padding: 4rem 1rem;">
                <div style="font-size: 4rem; margin-bottom: 1rem;">⚠️</div>
                <div style="font-size: 1.2rem; font-weight: 600; color: #ff6b6b;
                     margin-bottom: 0.5rem;">
                    Không thể khởi tạo ứng dụng
                </div>
                <div style="font-size: 0.9rem; color: #888;">{error_msg}</div>
                <div style="margin-top: 1.5rem; font-size: 0.85rem; color: #666;">
                    💡 Tạo file .env từ .env.example và cấu hình đúng.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Render layout
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
