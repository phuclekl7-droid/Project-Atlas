"""
Model Sliders (Feature 175: Thanh Trượt Model Parameters)

Adds a collapsible expander with three sliders for LLM parameters:
  - Temperature (0.0 - 2.0): Creativity
  - Top P (0.0 - 1.0): Word diversity
  - Max Tokens (100 - 8000): Max response length

These values override default configuration when calling the API.

Usage in sidebar:
    from ui.model_sliders import render_model_sliders
    render_model_sliders()
"""

import streamlit as st


def render_model_sliders() -> None:
    """
    Render the model parameter sliders inside an expander.

    Reads/writes to st.session_state.model_params dict.
    Keys stored: temperature, top_p, max_tokens.
    """
    # Ensure default values
    if "model_params" not in st.session_state:
        st.session_state.model_params = {
            "temperature": 0.7,
            "top_p": 0.9,
            "max_tokens": 2048,
        }

    params = st.session_state.model_params

    with st.expander("⚙️ Thông số Model", expanded=False):
        # Temperature
        temperature = st.slider(
            "🎯 Temperature",
            min_value=0.0,
            max_value=2.0,
            value=float(params.get("temperature", 0.7)),
            step=0.05,
            key="ms_temp",
            help="Độ sáng tạo: 0 = luôn chọn từ có xác suất cao nhất, 2 = rất ngẫu nhiên",
        )

        # Top P (nucleus sampling)
        top_p = st.slider(
            "📊 Top P",
            min_value=0.0,
            max_value=1.0,
            value=float(params.get("top_p", 0.9)),
            step=0.05,
            key="ms_topp",
            help="Độ đa dạng từ ngữ: 0.1 = chỉ chọn từ top 10%, 1.0 = tất cả",
        )

        # Max Tokens
        max_tokens = st.slider(
            "📏 Max Tokens",
            min_value=100,
            max_value=8000,
            value=int(params.get("max_tokens", 2048)),
            step=100,
            key="ms_maxtokens",
            help="Độ dài tối đa câu trả lời (tokens)",
        )

        # Update session state
        st.session_state.model_params = {
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }

        # Show description
        st.caption(
            f"Temperature: **{temperature:.2f}** · "
            f"Top P: **{top_p:.2f}** · "
            f"Max: **{max_tokens:,}** tokens"
        )

        # Preset buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🎯 Chính xác", key="preset_precise", use_container_width=True):
                st.session_state.model_params = {"temperature": 0.1, "top_p": 0.3, "max_tokens": 1024}
                st.rerun()
        with col2:
            if st.button("⚖️ Cân bằng", key="preset_balanced", use_container_width=True):
                st.session_state.model_params = {"temperature": 0.7, "top_p": 0.9, "max_tokens": 2048}
                st.rerun()
        with col3:
            if st.button("🎨 Sáng tạo", key="preset_creative", use_container_width=True):
                st.session_state.model_params = {"temperature": 1.5, "top_p": 0.95, "max_tokens": 4096}
                st.rerun()


def get_model_params() -> dict:
    """
    Get the current model parameters from session state.

    Returns:
        Dict with keys: temperature, top_p, max_tokens
        Falls back to defaults if not set.
    """
    defaults = {"temperature": 0.7, "top_p": 0.9, "max_tokens": 2048}
    if "model_params" not in st.session_state:
        return dict(defaults)
    params = st.session_state.model_params
    return {
        "temperature": float(params.get("temperature", defaults["temperature"])),
        "top_p": float(params.get("top_p", defaults["top_p"])),
        "max_tokens": int(params.get("max_tokens", defaults["max_tokens"])),
    }


def validate_params(params: dict) -> dict:
    """
    Validate and clamp model parameters to acceptable ranges.

    Args:
        params: Dict with optional temperature, top_p, max_tokens

    Returns:
        Dict with clamped values
    """
    result = {}
    t = params.get("temperature", 0.7)
    result["temperature"] = max(0.0, min(2.0, float(t)))

    p = params.get("top_p", 0.9)
    result["top_p"] = max(0.0, min(1.0, float(p)))

    m = params.get("max_tokens", 2048)
    result["max_tokens"] = max(100, min(8000, int(m)))

    return result
