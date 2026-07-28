"""
Streaming & Handler Module: response generation, session management, message CRUD.

Extracted from app.py to reduce its size. All functions operate on st.session_state.
"""

import asyncio
import time
from pathlib import Path
from typing import Optional

import streamlit as st

from src.core import (
    AssistantError,
    ConfigurationError,
    ModelConnectionError,
)
from src.memory import Message
from src.features.speed_tracker import SpeedTracker
from utils.prompt import enhance_prompt, fix_streaming_render, render_token_cost_html


# ============================================================
# Message Refresh
# ============================================================


def refresh_messages():
    """Load messages from memory into session state for the current session."""
    if "memory" not in st.session_state or "session_id" not in st.session_state:
        st.session_state.messages = []
        return

    memory = st.session_state.memory
    session_id = st.session_state.session_id
    raw_messages = memory.get_messages(session_id, limit=200)

    pinned = memory.get_pinned_messages(session_id)
    st.session_state.pinned_messages = [
        {"id": m.id, "role": m.role, "content": m.content, "provider": getattr(m, "provider", None)}
        for m in pinned
    ]

    st.session_state.messages = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "provider": getattr(m, "provider", None),
            "pinned": getattr(m, "pinned", 0),
            "has_image": hasattr(m, "has_image") and m.has_image(),
            "image_path": m.image_path if hasattr(m, "image_path") else None,
            "image_paths": m.image_paths if hasattr(m, "image_paths") else [],
            "images_count": m.images_count if hasattr(m, "images_count") else 0,
        }
        for m in raw_messages
    ]


# ============================================================
# Provider Switching
# ============================================================


def switch_provider(provider: str):
    """Switch the model provider and re-initialize the router."""
    if st.session_state.get("offline_mode") and provider not in ("mock", "ollama"):
        st.session_state.error = "📡 Không thể chuyển — chế độ Offline đang bật! Tắt Offline Mode trước."
        return

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


# ============================================================
# Response Generation
# ============================================================


def generate_response_stream(prompt: str):
    """
    Streaming mode: renders tokens progressively via Workflow.process_stream().
    """
    workflow = st.session_state.workflow
    session_id = st.session_state.session_id
    settings = st.session_state.settings

    prompt = enhance_prompt(prompt)

    custom_prompt = st.session_state.get("custom_prompt", "")
    if custom_prompt and not st.session_state.get("persona", "default") != "default":
        prompt = f"[{custom_prompt}]\n\n{prompt}"

    persona_prompt = st.session_state.get("persona_prompt", "")
    persona = st.session_state.get("persona", "default")
    if persona != "default" and persona_prompt:
        prompt = f"[{persona_prompt}]\n\n{prompt}"

    model_kwargs = dict(st.session_state.get("model_params", {}) or {})        try:
            start_time = time.time()
            speed_tracker = SpeedTracker()
            speed_tracker.start()

            bot_avatar = st.session_state.get("bot_avatar", "🤖")
            with st.chat_message("assistant", avatar=bot_avatar):
                placeholder = st.empty()
                accumulated = ""

            async def stream_and_display():
                nonlocal accumulated
                async for token in workflow.process_stream(
                    user_input=prompt,
                    session_id=session_id,
                    max_context=settings.max_context_messages,
                    **model_kwargs,
                ):
                    accumulated += token
                    speed_tracker.record_tokens(1)
                    fixed = fix_streaming_render(accumulated)
                    placeholder.markdown(fixed + " ▌")
                speed_tracker.stop()
                placeholder.markdown(fix_streaming_render(accumulated))
                return accumulated

            asyncio.run(stream_and_display())

        elapsed_ms = (time.time() - start_time) * 1000
        st.session_state.latency = elapsed_ms
        # Store speed stats for the badge
        st.session_state.last_speed_html = speed_tracker.get_badge_html()
        refresh_messages()

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
    Async (fast) mode: gets the full response at once via Workflow.process_async().
    """
    workflow = st.session_state.workflow
    session_id = st.session_state.session_id
    settings = st.session_state.settings

    try:
        with st.spinner("⏳ Đang xử lý..."):
            start_time = time.time()

            enhanced_prompt = enhance_prompt(prompt)

            custom_prompt = st.session_state.get("custom_prompt", "")
            if custom_prompt and st.session_state.get("persona", "default") == "default":
                enriched_prompt = f"[{custom_prompt}]\n\n{enhanced_prompt}"
            else:
                enriched_prompt = enhanced_prompt

            persona = st.session_state.get("persona", "default")
            persona_prompt = st.session_state.get("persona_prompt", "")
            if persona != "default" and persona_prompt:
                enriched_prompt = f"[{persona_prompt}]\n\n{enriched_prompt}"

            model_kwargs = dict(st.session_state.get("model_params", {}) or {})

            async def get_response():
                return await workflow.process_async(
                    user_input=enriched_prompt,
                    session_id=session_id,
                    max_context=settings.max_context_messages,
                    **model_kwargs,
                )

            result = asyncio.run(get_response())
            elapsed_ms = (time.time() - start_time) * 1000

        bot_avatar = st.session_state.get("bot_avatar", "🤖")
        if result.source == "llm" and result.response:
            with st.chat_message("assistant", avatar=bot_avatar):
                st.markdown(result.response.text)
                # Show token cost (use shared utility to avoid circular imports)
                cost_html = render_token_cost_html(result.response)
                if cost_html:
                    st.markdown(cost_html, unsafe_allow_html=True)
        elif result.source == "plugin" and result.plugin_result:
            with st.chat_message("assistant", avatar=bot_avatar):
                st.markdown(result.plugin_result.output)

        st.session_state.latency = elapsed_ms
        refresh_messages()

    except ConfigurationError as e:
        st.session_state.error = f"Cấu hình lỗi: {e.message}"
    except ModelConnectionError as e:
        st.session_state.error = f"Kết nối lỗi: {e.message}"
    except AssistantError as e:
        st.session_state.error = f"Lỗi: {e.message}"
    except Exception as e:
        st.session_state.error = f"Lỗi bất ngờ: {e}"


def generate_response(prompt: str):
    """
    Dispatch to streaming or async mode based on user preference.
    """
    mode = st.session_state.get("response_mode", "stream")
    if mode == "async":
        generate_response_async(prompt)
    else:
        generate_response_stream(prompt)


# ============================================================
# User Input Handling
# ============================================================


def handle_user_input(prompt: str, images_data: list[tuple] = None):
    """
    Handle user input with optional images.
    """
    if not prompt.strip() and not images_data:
        return

    memory = st.session_state.memory
    session_id = st.session_state.session_id

    refresh_messages()

    if images_data:
        image_store = st.session_state.image_store
        saved_paths = []
        for filename, image_bytes in images_data:
            saved_path = image_store.save_image(filename, image_bytes)
            if saved_path:
                saved_paths.append(saved_path)

        if saved_paths:
            image_content = Message.make_images_content(saved_paths, prompt)
            memory.add_message(session_id, "user", image_content)
            refresh_messages()
            st.session_state.pending_images = [(p, prompt) for p in saved_paths]
            st.session_state.pending_image_previews = []
            return
        else:
            st.session_state.error = "Không thể lưu ảnh!"
            return

    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.pending_prompt = prompt


# ============================================================
# Session Management
# ============================================================


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
    if "pending_prompt" in st.session_state:
        del st.session_state.pending_prompt
    refresh_messages()


# ============================================================
# Message Edit / Delete / Undo
# ============================================================


def edit_message(message_id: int, new_content: str):
    """Edit a message in the database and refresh the UI."""
    if not new_content or not new_content.strip():
        st.session_state.error = "Nội dung tin nhắn không được để trống!"
        return

    memory = st.session_state.memory
    session_id = st.session_state.session_id

    try:
        updated = memory.update_message(session_id, message_id, new_content.strip())
        if updated:
            st.session_state.success = "✏️ Đã cập nhật tin nhắn"
        else:
            st.session_state.error = "Không tìm thấy tin nhắn để sửa"
    except Exception as e:
        st.session_state.error = f"Lỗi sửa tin nhắn: {e}"

    st.session_state.editing_msg_id = None
    refresh_messages()


def cancel_edit():
    """Cancel the current edit operation."""
    st.session_state.editing_msg_id = None


def delete_message_handler(message_id: int):
    """Delete a message and save it to the undo stack."""
    memory = st.session_state.memory
    session_id = st.session_state.session_id

    try:
        deleted = memory.delete_message(session_id, message_id)
        if deleted:
            for img_path in deleted.image_paths:
                p = Path(img_path)
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass

            undo_stack = st.session_state.get("undo_stack", [])
            undo_stack.append({
                "session_id": session_id,
                "role": deleted.role,
                "content": deleted.content,
            })
            st.session_state.undo_stack = undo_stack[-5:]
            st.session_state.success = "🗑️ Đã xóa tin nhắn"
            st.session_state.show_undo = True
        else:
            st.session_state.error = "Không tìm thấy tin nhắn để xóa"
    except Exception as e:
        st.session_state.error = f"Lỗi xóa tin nhắn: {e}"

    refresh_messages()


def undo_delete():
    """Restore the last deleted message."""
    undo_stack = st.session_state.get("undo_stack", [])
    if not undo_stack:
        return

    last = undo_stack.pop()
    memory = st.session_state.memory

    try:
        memory.add_message(last["session_id"], last["role"], last["content"])
        st.session_state.undo_stack = undo_stack
        st.session_state.success = "↩️ Đã hoàn tác xóa tin nhắn!"
    except Exception as e:
        st.session_state.error = f"Lỗi hoàn tác: {e}"

    st.session_state.show_undo = False
    refresh_messages()


# ============================================================
# Pinned Messages
# ============================================================


def toggle_pin(message_id: int):
    """Pin or unpin a message."""
    memory = st.session_state.memory
    session_id = st.session_state.session_id

    try:
        msg = memory.get_message_by_id(session_id, message_id)
        if msg is None:
            st.session_state.error = "Không tìm thấy tin nhắn!"
            return

        if msg.pinned:
            memory.unpin_message(session_id, message_id)
            st.session_state.success = "📌 Đã bỏ ghim tin nhắn"
        else:
            memory.pin_message(session_id, message_id)
            st.session_state.success = "📌 Đã ghim tin nhắn lên đầu"
    except Exception as e:
        st.session_state.error = f"Lỗi ghim tin nhắn: {e}"

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
