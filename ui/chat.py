"""
Chat UI Module: chat interface, toasts, dashboard, vault, and misc UI helpers.

Extracted from app.py to reduce its size.
"""

import base64
import html
from typing import Optional

import streamlit as st

from src.core import format_timestamp
from src.features import (
    render_export_buttons,
    search_sessions_ui,
    render_code_diff,
    auto_detect_and_render,
)
from src.features.speed_tracker import SpeedTracker
from src.features.table_exporter import TableExporter
from utils.text_metrics import compute_text_metrics, render_metrics_html
from utils.prompt import detect_session_tags, render_session_tags


# ============================================================
# Image preview helpers
# ============================================================


def render_image_previews():
    """Render thumbnail previews of pending images before sending."""
    previews = st.session_state.get("pending_image_previews", [])
    if not previews:
        return

    html_parts = ['<div class="preview-container">']
    for i, (name, b64_thumb) in enumerate(previews):
        safe_name = html.escape(name)
        html_parts.append(
            f'<div class="preview-item">'
            f'<img src="{b64_thumb}" alt="{safe_name}" />'
            f'<span class="preview-name">{safe_name}</span>'
            f'</div>'
        )
    html_parts.append('</div>')
    st.markdown("\n".join(html_parts), unsafe_allow_html=True)


def make_thumbnail_b64(data: bytes, max_size: int = 150) -> str:
    """Create a small base64 thumbnail for preview (just resized via CSS)."""
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:image/png;base64,{b64}"


# ============================================================
# Toast notifications
# ============================================================


def render_toasts():
    """Render success/error toast messages from session state."""
    if st.session_state.get("error"):
        st.markdown(
            f'<div class="toast-container"><div class="toast-error">⚠️ {st.session_state.error}</div></div>',
            unsafe_allow_html=True,
        )
        st.session_state.error = None

    if st.session_state.get("success"):
        st.markdown(
            f'<div class="toast-container"><div class="toast-success">✅ {st.session_state.success}</div></div>',
            unsafe_allow_html=True,
        )
        st.session_state.success = None

    # Undo toast
    if st.session_state.get("show_undo"):
        col_u1, col_u2 = st.columns([5, 1])
        with col_u1:
            st.markdown(
                '<div class="undo-toast"><span class="msg">🗑️ Tin nhắn đã được xóa</span></div>',
                unsafe_allow_html=True,
            )
        with col_u2:
            if st.button("↩️ Undo", key="undo_btn", use_container_width=True):
                from handlers.streaming import undo_delete
                undo_delete()


# ============================================================
# Code Snippet Vault page (Feature 158)
# ============================================================


def render_vault_page():
    """Render the Code Snippet Vault page."""
    st.markdown("# 💾 Code Snippet Vault")
    st.markdown("Các đoạn code bạn đã lưu từ các cuộc trò chuyện.")

    memory = st.session_state.memory

    all_langs = memory.get_snippet_languages()
    lang_options = [""] + all_langs
    lang_labels = {"": "📋 Tất cả ngôn ngữ"}
    for l in all_langs:
        lang_labels[l] = l.capitalize()

    col_f1, col_f2 = st.columns([3, 1])
    with col_f1:
        lang_filter = st.selectbox(
            "🔍 Lọc ngôn ngữ",
            options=lang_options,
            format_func=lambda x: lang_labels.get(x, x),
            key="vault_lang_filter",
            label_visibility="collapsed",
        )
    with col_f2:
        st.markdown("", unsafe_allow_html=True)

    snippets = memory.list_snippets(language=lang_filter if lang_filter else None, limit=100)

    if not snippets:
        st.info("💡 Chưa có snippet nào. Khi AI trả lời có code block, bấm '💾 Save' ở góc để lưu lại.")
        if st.button("⬅️ Quay lại Chat", use_container_width=True):
            st.session_state.show_vault = False
            st.rerun()
        return

    st.markdown(f"📦 **{len(snippets)}** snippets")
    st.divider()

    for s in snippets:
        sid = s["id"]
        lang = s.get("language", "unknown")
        desc = s.get("description", "")
        code = s.get("code", "")
        created = s.get("created_at", "")[:19]
        header = f"📄 {desc[:60]}{'...' if len(desc) > 60 else ''} · `{lang}` · {created}"

        with st.expander(header):
            st.code(code, language=lang or None, line_numbers=True)
            col_x, col_y = st.columns([1, 5])
            with col_x:
                if st.button(f"🗑️ Xóa", key=f"vault_del_{sid}"):
                    memory.delete_snippet(sid)
                    st.session_state.success = f"🗑️ Đã xóa snippet #{sid}"
                    st.rerun()
            with col_y:
                st.markdown(
                    f'<div style="font-size: 0.7rem; color: #888; padding-top: 0.3rem;">'
                    f'ID: {sid} · {created} · {len(code)} chars</div>',
                    unsafe_allow_html=True,
                )

    st.divider()
    if st.button("⬅️ Quay lại Chat", use_container_width=True, type="primary"):
        st.session_state.show_vault = False
        st.rerun()


# ============================================================
# Token Usage Dashboard (Feature 3)
# ============================================================


def render_dashboard():
    """Render Token Usage Analytics dashboard with stats and charts."""
    st.markdown("## 📊 Token Usage Dashboard")

    memory = st.session_state.memory

    total = memory.get_total_cost()
    sessions = memory.list_sessions(limit=100)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f'<div class="stat-card"><div class="stat-value">{total["total_tokens"]:,}</div>'
            f'<div class="stat-label">Total Tokens</div></div>',
            unsafe_allow_html=True,
        )
    with col2:
        cost_usd = total["total_cost_usd"]
        cost_vnd = cost_usd * 25450
        st.markdown(
            f'<div class="stat-card"><div class="stat-value">${cost_usd:.4f}</div>'
            f'<div class="stat-label">Cost (USD)</div></div>',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f'<div class="stat-card"><div class="stat-value">{cost_vnd:,.0f}₫</div>'
            f'<div class="stat-label">Cost (VND)</div></div>',
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f'<div class="stat-card"><div class="stat-value">{len(sessions)}</div>'
            f'<div class="stat-label">Sessions</div></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    st.markdown("### 💰 Provider Cost Breakdown")
    provider_data = total["provider_totals"]
    if provider_data:
        rows = []
        for prov, data in provider_data.items():
            cost = data["cost"]
            emoji = {"openai": "🔵", "gemini": "🟢", "ollama": "🦙", "mock": "🔌"}.get(prov, "❓")
            rows.append(f"| {emoji} **{prov.upper()}** | {data['prompt']:,} | {data['completion']:,} | ${cost:.4f} |")
        st.markdown(
            "| Provider | Prompt Tokens | Completion Tokens | Cost (USD) |\n"
            "|---|---|---|---|\n" + "\n".join(rows)
        )
    else:
        st.info("Chưa có dữ liệu token.")

    st.divider()

    st.markdown("### 📅 Recent Session Activity")
    for s in sessions[:10]:
        cost = memory.get_total_cost(session_id=s.id)
        st.markdown(f"- {s.name}: {s.message_count} msgs, ${cost['total_cost_usd']:.4f}")

    st.caption("💡 Token usage is tracked per message. Local models (Ollama/Mock) are free.")

    current_sid = st.session_state.get("session_id", "")
    current_msgs = st.session_state.get("messages", [])
    render_export_buttons(current_sid, current_msgs)

    search_sessions_ui(memory)


# ============================================================
# Main Chat Interface
# ============================================================


def render_chat_interface():
    """Render the main chat area with messages, input, and image upload."""
    from handlers.streaming import (
        handle_user_input,
        generate_response,
        edit_message,
        cancel_edit,
        delete_message_handler,
        toggle_pin,
        refresh_messages,
    )

    messages = st.session_state.get("messages", [])
    pinned = st.session_state.get("pinned_messages", [])

    # ── Chat header ──
    st.markdown(
        '<div class="chat-header">'
        '<h1>🤖 Personal AI Assistant</h1>'
        '<p>Project Atlas · AI Trợ lý cá nhân thông minh</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Clear chat button (Feature 169)
    col_header, col_actions = st.columns([4, 2])
    with col_actions:
        col_clr, col_pdf = st.columns([1, 1])
        with col_clr:
            if st.button("🧹 Clear Chat", key="clear_chat_btn", help="Xóa toàn bộ tin nhắn", use_container_width=True):
                from handlers.chat_clearer import clear_active_chat
                memory_local = st.session_state.memory
                sid = st.session_state.session_id
                if clear_active_chat(memory_local, sid):
                    from handlers.streaming import refresh_messages
                    refresh_messages()
                    st.session_state.success = "🧹 Đã xóa toàn bộ tin nhắn!"
                    st.rerun()

    # ── Pinned messages section ──
    if pinned:
        st.markdown('<div class="pinned-section">', unsafe_allow_html=True)
        st.markdown(
            '<div class="pinned-header">📌 Đã ghim</div>',
            unsafe_allow_html=True,
        )
        for pm in pinned:
            role_label = "👤" if pm["role"] == "user" else "🤖"
            st.markdown(
                f'<div style="font-size:0.85rem;padding:0.2rem 0;">'
                f'{role_label} {pm["content"][:80]}{"..." if len(pm["content"]) > 80 else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Chat messages ──
    chat_container = st.container()
    with chat_container:
        if not messages:
            st.markdown(
                '<div class="welcome-msg">'
                '<div class="emoji">👋</div>'
                '<div class="title">Xin chào! Tôi là trợ lý AI của bạn</div>'
                '<div class="subtitle">'
                'Tôi có thể giúp bạn trả lời câu hỏi, viết code, tìm kiếm thông tin, '
                'và nhiều hơn thế nữa. Hãy bắt đầu bằng cách nhập tin nhắn bên dưới!'
                '</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            for i, msg in enumerate(messages):
                msg_id = msg.get("id", i)
                role = msg.get("role", "user")
                content = msg.get("content", "")
                provider = msg.get("provider", "")
                is_pinned = msg.get("pinned", 0)
                has_image = msg.get("has_image", False)
                image_paths = msg.get("image_paths", [])
                images_count = msg.get("images_count", 0)

                is_editing = st.session_state.get("editing_msg_id") == msg_id

                if is_editing:
                    # ── Edit mode ──
                    st.markdown('<div class="edit-container">', unsafe_allow_html=True)
                    new_content = st.text_area(
                        "Edit message",
                        value=content,
                        key=f"edit_area_{msg_id}",
                        label_visibility="collapsed",
                    )
                    st.markdown('<div class="edit-actions">', unsafe_allow_html=True)
                    col_s, col_c = st.columns([1, 1])
                    with col_s:
                        if st.button("💾 Lưu", key=f"save_{msg_id}", use_container_width=True):
                            edit_message(msg_id, new_content)
                            st.rerun()
                    with col_c:
                        if st.button("❌ Hủy", key=f"cancel_{msg_id}", use_container_width=True):
                            cancel_edit()
                            st.rerun()
                    st.markdown("</div></div>", unsafe_allow_html=True)
                else:
                    # ── Normal message display ──
                    avatar = "👤" if role == "user" else st.session_state.get("bot_avatar", "🤖")
                    with st.chat_message(role, avatar=avatar):
                        if has_image and image_paths:
                            img_class = "img-single" if len(image_paths) == 1 else "img-multi"
                            imgs_html = '<div class="message-image-grid">'
                            for ip in image_paths:
                                try:
                                    with open(ip, "rb") as img_f:
                                        img_b64 = base64.b64encode(img_f.read()).decode()
                                        imgs_html += (
                                            f'<img class="{img_class}" '
                                            f'src="data:image/png;base64,{img_b64}" alt="uploaded image" />'
                                        )
                                except Exception:
                                    pass
                            imgs_html += "</div>"
                            if images_count > 1:
                                imgs_html += f'<span class="image-count-badge">+{images_count} ảnh</span>'
                            st.markdown(imgs_html, unsafe_allow_html=True)

                        # Code block expander (Feature 171): Replace long code blocks BEFORE rendering
                        rendered_content = content
                        if role == "assistant" and content:
                            from ui.code_expander import wrap_code_block as _wrap_code
                            import re as _re
                            def _expand_long(m):
                                lang = m.group(1)
                                code = m.group(2)
                                if len(code.split('\n')) > 25:
                                    return _wrap_code(code, lang)
                                return m.group(0)
                            rendered_content = _re.sub(
                                r'```(\w*)\n(.*?)```',
                                _expand_long,
                                content,
                                flags=_re.DOTALL,
                            )
                            if rendered_content != content:
                                content = rendered_content

                        # Message content
                        st.markdown(content, unsafe_allow_html=True)

                        # Action buttons row
                        col_a1, col_a2, col_a3, col_a4, col_a5 = st.columns([1, 1, 1, 1, 6])

                        if is_pinned:
                            pin_icon = "📌"
                        else:
                            pin_icon = "📍"
                        with col_a1:
                            if st.button(pin_icon, key=f"pin_{msg_id}", help="Ghim/bỏ ghim"):
                                toggle_pin(msg_id)
                                st.rerun()

                        with col_a2:
                            if st.button("✏️", key=f"edit_{msg_id}", help="Sửa tin nhắn"):
                                st.session_state.editing_msg_id = msg_id
                                st.rerun()

                        with col_a3:
                            if st.button("🗑️", key=f"del_{msg_id}", help="Xóa tin nhắn"):
                                delete_message_handler(msg_id)
                                st.rerun()

                        with col_a4:
                            if role == "assistant" and content:
                                if st.button("🔊", key=f"tts_{msg_id}", help="Đọc to"):
                                    safe_content = content.replace("`", "\\`").replace("'", "\\'").replace('"', '\\"')
                                    st.markdown(
                                        f'<script>'
                                        f'var msg = new SpeechSynthesisUtterance("{safe_content[:500]}");'
                                        f'msg.lang = "vi-VN";'
                                        f'speechSynthesis.speak(msg);'
                                        f'</script>',
                                        unsafe_allow_html=True,
                                    )

                        # Speed tracker badge (assistant messages only, last msg)
                        if role == "assistant":
                            is_last = (i == len(messages) - 1)
                            if is_last:
                                speed_html = st.session_state.get("last_speed_html", "")
                                if speed_html:
                                    st.markdown(speed_html, unsafe_allow_html=True)

                        # Text metrics for long messages (Feature 168)
                        if role == "assistant" and content and len(content) > 100:
                            metrics = compute_text_metrics(content)
                            metrics_html = render_metrics_html(metrics)
                            if metrics_html:
                                st.markdown(metrics_html, unsafe_allow_html=True)

                        # Table exporter for assistant messages (Feature 167)
                        if role == "assistant" and content:
                            exporter = TableExporter()
                            tables = exporter.extract_tables(content)
                            if tables:
                                download_html = exporter.render_download_html(tables)
                                if download_html:
                                    st.markdown(download_html, unsafe_allow_html=True)

                        # Provider badge (assistant messages only)
                        if role == "assistant" and provider:
                            st.markdown(
                                f'<span class="provider-badge {provider}">{provider.upper()}</span>',
                                unsafe_allow_html=True,
                            )

    # ── Prompt Picker (Feature: Quick Prompt Templates 1-Click) ──
    from ui.prompt_picker import render_prompt_picker
    render_prompt_picker()

    # Auto-submit prompt from picker if triggered
    trigger = st.session_state.get("prompt_picker_trigger", "")
    if trigger:
        st.session_state.prompt_picker_trigger = ""  # Clear trigger
        handle_user_input(trigger, images_data=None)
        generate_response(trigger)
        st.rerun()

    # ── Input area ──
    st.markdown('<div class="input-container">', unsafe_allow_html=True)

    # Image upload / drag-and-drop
    uploaded_files = st.file_uploader(
        "📷 Upload ảnh",
        type=["png", "jpg", "jpeg", "gif", "webp", "bmp"],
        accept_multiple_files=True,
        key="chat_image_upload",
        label_visibility="collapsed",
    )

    if uploaded_files:
        images_data = []
        for uf in uploaded_files:
            images_data.append((uf.name, uf.getvalue()))
        st.session_state.uploaded_images_data = images_data
        st.markdown(
            f'<div style="font-size:0.8rem;color:#888;padding:0.2rem 0;">'
            f'📷 {len(images_data)} ảnh đã chọn'
            f'</div>',
            unsafe_allow_html=True,
        )

    render_image_previews()

    # Keyboard shortcut hint
    st.markdown(
        '<div style="font-size:0.65rem;color:#555;text-align:right;padding:0.1rem 0.3rem;">'
        '<kbd style="background:rgba(128,128,128,0.1);padding:0.05rem 0.3rem;border-radius:3px;font-size:0.6rem;">Ctrl+Enter</kbd> gửi '
        '<kbd style="background:rgba(128,128,128,0.1);padding:0.05rem 0.3rem;border-radius:3px;font-size:0.6rem;">Ctrl+N</kbd> session mới '
        '<kbd style="background:rgba(128,128,128,0.1);padding:0.05rem 0.3rem;border-radius:3px;font-size:0.6rem;">Esc</kbd> hủy'
        '</div>',
        unsafe_allow_html=True,
    )

    # Text input + send
    prompt = st.chat_input(
        placeholder="Nhập tin nhắn... (Ctrl+Enter để gửi)",
        key="chat_input_main",
    )

    if prompt:
        images_data = st.session_state.pop("uploaded_images_data", None)
        handle_user_input(prompt, images_data=images_data)
        generate_response(prompt)
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
